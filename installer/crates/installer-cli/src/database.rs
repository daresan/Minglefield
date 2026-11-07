//! Headless adapter for shared SQLCipher DB verification/copy operations.
//! Never changes Host permissions or silently creates users or sessions.
use minglefield_installer_core::config_v3::{parse_stdin_secrets, DatabaseOptions, StdinSecrets};
use minglefield_installer_core::db_operations::{
    create_new_encrypted_database, create_reviewed_encrypted_database_copy,
    verify_encrypted_database, NEW_ENCRYPTED_DATABASE_CONFIRMATION,
};
use minglefield_installer_core::encrypted_copy_preflight::EXPERIMENTAL_COPY_CONFIRMATION;
use std::env;
use std::path::Path;

#[derive(Default)]
pub struct DatabaseAction {
    pub verify: bool,
    pub copy: bool,
    pub fresh: bool,
    pub input: DatabaseOptions,
    pub stdin: bool,
}

pub fn flag_value(
    args: &mut impl Iterator<Item = String>,
    name: &'static str,
    field: &mut Option<String>,
) -> Result<(), (u8, String)> {
    if field.is_some() {
        return Err((2, format!("duplicate argument: {name}")));
    }
    *field = Some(
        args.next()
            .filter(|value| !value.starts_with("--"))
            .ok_or((2, format!("{name} requires a value")))?,
    );
    Ok(())
}

impl DatabaseAction {
    pub fn active(&self) -> bool {
        self.verify || self.copy || self.fresh
    }

    pub fn parse(
        &mut self,
        argument: &str,
        args: &mut impl Iterator<Item = String>,
    ) -> Result<bool, (u8, String)> {
        // The "=VALUE" form allows passwords that begin with "--" and avoids
        // mistaking the value for a new option. The ordinary two-argument
        // spelling remains supported for compatibility with Bee-style CLIs.
        if let Some((name, value)) = argument.split_once('=') {
            let target = match name {
                "--database" => &mut self.input.database_path,
                "--source-db" => &mut self.input.source_path,
                "--backup-db" => &mut self.input.backup_path,
                "--db-password" => &mut self.input.password.literal,
                "--db-password-file" => &mut self.input.password.file,
                "--new-db-password" => &mut self.input.new_password.literal,
                "--new-db-password-file" => &mut self.input.new_password.file,
                "--confirm-db-copy" => &mut self.input.copy_confirmation,
                "--confirm-new-db" => &mut self.input.new_db_confirmation,
                _ => return Ok(false),
            };
            if target.is_some() {
                return Err((2, "duplicate database option".to_owned()));
            }
            *target = Some(value.to_owned());
            return Ok(true);
        }
        match argument {
            "--verify-encrypted-db" if !self.verify => self.verify = true,
            "--create-encrypted-copy" if !self.copy => self.copy = true,
            "--create-new-encrypted-db" if !self.fresh => self.fresh = true,
            "--secrets-stdin" if !self.stdin => self.stdin = true,
            "--verify-encrypted-db"
            | "--create-encrypted-copy"
            | "--create-new-encrypted-db"
            | "--secrets-stdin" => {
                return Err((2, "duplicate database action flag".to_owned()));
            }
            "--database" => flag_value(args, "--database", &mut self.input.database_path)?,
            "--source-db" => flag_value(args, "--source-db", &mut self.input.source_path)?,
            "--backup-db" => flag_value(args, "--backup-db", &mut self.input.backup_path)?,
            "--db-password" => flag_value(args, "--db-password", &mut self.input.password.literal)?,
            "--db-password-file" => {
                flag_value(args, "--db-password-file", &mut self.input.password.file)?;
            }
            "--new-db-password" => {
                flag_value(
                    args,
                    "--new-db-password",
                    &mut self.input.new_password.literal,
                )?;
            }
            "--new-db-password-file" => {
                flag_value(
                    args,
                    "--new-db-password-file",
                    &mut self.input.new_password.file,
                )?;
            }
            "--confirm-db-copy" => {
                flag_value(args, "--confirm-db-copy", &mut self.input.copy_confirmation)?;
            }
            "--confirm-new-db" => {
                flag_value(
                    args,
                    "--confirm-new-db",
                    &mut self.input.new_db_confirmation,
                )?;
            }
            "--schema-add" => {
                let value = args
                    .next()
                    .filter(|value| !value.starts_with("--"))
                    .ok_or((2, "--schema-add requires a registry identifier".to_owned()))?;
                if self.input.schema_additions.contains(&value) {
                    return Err((2, "duplicate requested schema addition".to_owned()));
                }
                self.input.schema_additions.push(value);
            }
            _ => return Ok(false),
        }
        Ok(true)
    }

    /// DB paths/config version are common with the GUI-facing core contract.
    /// The CLI only resolves secrets immediately before an actual DB action.
    pub fn execute(&self, base: Option<&DatabaseOptions>, json: bool) -> Result<(), (u8, String)> {
        let selected = u8::from(self.verify) + u8::from(self.copy) + u8::from(self.fresh);
        if selected != 1 {
            return Err((2, "select exactly one database operation".to_owned()));
        }
        let mut db = base.cloned().unwrap_or_default();
        db.override_with(self.input.clone());
        if self.verify
            && (db.source_path.is_some()
                || db.backup_path.is_some()
                || db.new_password.literal.is_some()
                || db.new_password.file.is_some()
                || db.copy_confirmation.is_some()
                || db.new_db_confirmation.is_some()
                || !db.schema_additions.is_empty())
        {
            return Err((
                2,
                "unexpected database-copy options for read-only verification".into(),
            ));
        }
        if self.copy && db.copy_confirmation.as_deref() != Some(EXPERIMENTAL_COPY_CONFIRMATION) {
            return Err((2, "explicit --confirm-db-copy approval is required".into()));
        }
        if self.copy && db.new_db_confirmation.is_some() {
            return Err((2, "new database creation options conflict with copy".into()));
        }
        if self.fresh {
            if db.source_path.is_some()
                || db.backup_path.is_some()
                || db.password.literal.is_some()
                || db.password.file.is_some()
                || db.copy_confirmation.is_some()
                || !db.schema_additions.is_empty()
            {
                return Err((
                    2,
                    "fresh database creation cannot import sources or existing ownership".into(),
                ));
            }
            if db.new_db_confirmation.as_deref() != Some(NEW_ENCRYPTED_DATABASE_CONFIRMATION) {
                return Err((2, "explicit --confirm-new-db approval is required".into()));
            }
        }
        let input = if self.stdin {
            parse_stdin_secrets(std::io::stdin().lock())
                .map_err(|_| (3, "secrets stdin rejected".to_owned()))?
        } else {
            StdinSecrets {
                db_password: None,
                new_db_password: None,
                login_password: None,
            }
        };
        if input.login_password.is_some() {
            return Err((2, "login password requires a local Host setup action".to_owned()));
        }
        let destination = db.database_path.as_deref().ok_or((
            2,
            "--database is required for database operations".to_owned(),
        ))?;
        if self.fresh {
            if input.db_password.is_some() {
                return Err((
                    3,
                    "old database password is not accepted for a fresh DB".into(),
                ));
            }
            let new_password = db
                .new_password
                .resolve(
                    env::var("MINGLEFIELD_NEW_DB_PASSWORD").ok(),
                    input.new_db_password.as_deref(),
                )
                .map_err(|_| {
                    (
                        3,
                        "conflicting or invalid new database password source".to_owned(),
                    )
                })?
                .ok_or((3, "new SQLCipher database password is required".to_owned()))?;
            let created = create_new_encrypted_database(
                Path::new(destination),
                &new_password,
                NEW_ENCRYPTED_DATABASE_CONFIRMATION,
            )
            .map_err(|_| (4, "fresh encrypted database creation rejected".to_owned()))?;
            if json {
                println!(
                    "{{\"schema_version\":1,\"status\":\"{}\",\"exit_code\":0,\"encrypted_database_verified\":true,\"host_provisioning_enabled\":false,\"application_launch_enabled\":false,\"full_installation_completed\":false}}",
                    created.status
                );
            } else {
                println!("New SQLCipher database created; no user or Host provisioned");
            }
            return Ok(());
        }
        let key = db
            .password
            .resolve(
                env::var("MINGLEFIELD_DB_PASSWORD").ok(),
                input.db_password.as_deref(),
            )
            .map_err(|_| {
                (
                    3,
                    "conflicting or invalid database password source".to_owned(),
                )
            })?;

        if self.verify {
            if input.new_db_password.is_some() {
                return Err((
                    3,
                    "new database password must not be supplied for verification".into(),
                ));
            }
            let key = key.ok_or((3, "SQLCipher database password is required".to_owned()))?;
            let report = verify_encrypted_database(Path::new(destination), &key)
                .map_err(|_| (4, "encrypted database verification rejected".to_owned()))?;
            if json {
                println!(
                    "{{\"schema_version\":1,\"status\":\"encrypted_database_verified\",\"exit_code\":0,\"database_encrypted\":true,\"integrity_verified\":true,\"tables\":{},\"schema_entries\":{},\"alpha_users_table_present\":{},\"database_modified\":false,\"host_provisioning_enabled\":false}}",
                    report.tables, report.schema_entries, report.alpha_users_table_present
                );
            } else {
                println!(
                    "Encrypted database verified (read-only): {} tables; no Host change",
                    report.tables
                );
            }
            return Ok(());
        }
        let source = db.source_path.as_deref().ok_or((
            2,
            "--source-db is required for encrypted-copy publication".to_owned(),
        ))?;
        let backup = db.backup_path.as_deref().ok_or((
            2,
            "--backup-db is required for encrypted-copy publication".to_owned(),
        ))?;
        let new_key = db
            .new_password
            .resolve(
                env::var("MINGLEFIELD_NEW_DB_PASSWORD").ok(),
                input.new_db_password.as_deref(),
            )
            .map_err(|_| {
                (
                    3,
                    "conflicting or invalid new database password source".to_owned(),
                )
            })?
            .ok_or((3, "new SQLCipher database password is required".to_owned()))?;
        let report = create_reviewed_encrypted_database_copy(
            Path::new(source),
            Path::new(destination),
            Path::new(backup),
            key.as_deref().unwrap_or(""),
            &new_key,
            &db.schema_additions,
            EXPERIMENTAL_COPY_CONFIRMATION,
        )
        .map_err(|_| {
            (
                4,
                "reviewed encrypted database publication rejected".to_owned(),
            )
        })?;
        if !report.encrypted_destination_verified
            || !report.full_disk_copy_verified
            || !report.destination_created
            || !report.temporary_files_removed
        {
            return Err((
                4,
                "published ciphertext did not pass verification".to_owned(),
            ));
        }
        // The publication operation identity is a non-secret receipt, NOT
        // a newly minted Host ID. The separate first-run contract governs
        // whether activation is appropriate for a genuinely new Host.
        let operation_id = report.recovery_operation_id.as_deref().ok_or((
            4,
            "published ciphertext is missing its recovery operation receipt".to_owned(),
        ))?;
        if operation_id.len() != 32
            || !operation_id
                .bytes()
                .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
        {
            return Err((
                4,
                "published ciphertext operation receipt invalid".to_owned(),
            ));
        }
        if json {
            println!(
                "{{\"schema_version\":1,\"status\":\"experimental_encrypted_copy_created\",\"exit_code\":0,\"destination_created\":true,\"ciphertext_verified\":true,\"checked_rows\":{},\"checked_tables\":{},\"checked_schema_entries\":{},\"recovery_operation_id\":\"{}\",\"host_provisioning_enabled\":false,\"application_launch_enabled\":false,\"full_installation_completed\":false}}",
                report.rows_checked,
                report.tables_checked,
                report.schema_entries_checked,
                operation_id
            );
        } else {
            println!(
                "Verified encrypted database copy created ({} tables); no Host provisioned",
                report.tables_checked
            );
        }
        Ok(())
    }

    pub fn has_unbound_inputs(&self) -> bool {
        self.input.has_any() || self.stdin
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_bee_style_values_and_rejects_duplicates() {
        let mut db = DatabaseAction::default();
        assert!(db
            .parse("--verify-encrypted-db", &mut std::iter::empty())
            .unwrap());
        assert!(db
            .parse("--db-password", &mut ["private".to_owned()].into_iter())
            .unwrap());
        assert_eq!(db.input.password.literal.as_deref(), Some("private"));
        assert_eq!(
            db.parse("--db-password", &mut ["ignored".to_owned()].into_iter())
                .unwrap_err()
                .0,
            2
        );
        assert!(!db.parse("--unknown", &mut std::iter::empty()).unwrap());
    }

    #[test]
    fn accepts_equals_secrets_beginning_with_option_prefix() {
        let mut db = DatabaseAction::default();
        assert!(db
            .parse("--db-password=--LeadingDash9!", &mut std::iter::empty())
            .unwrap());
        assert_eq!(
            db.input.password.literal.as_deref(),
            Some("--LeadingDash9!")
        );
    }

    #[test]
    fn fresh_database_without_exact_approval_cannot_touch_destination() {
        let mut db = DatabaseAction {
            fresh: true,
            ..DatabaseAction::default()
        };
        db.input.database_path = Some("/definitely/not/created/first-run.db".to_owned());
        db.input.new_password.literal = Some("NewCipherPassword9!".to_owned());
        assert_eq!(db.execute(None, true).unwrap_err().0, 2);
    }

    #[test]
    fn refuses_multiple_database_operations() {
        let db = DatabaseAction {
            fresh: true,
            verify: true,
            ..DatabaseAction::default()
        };
        assert_eq!(db.execute(None, true).unwrap_err().0, 2);
    }

    #[test]
    fn copy_without_explicit_approval_does_not_touch_a_database() {
        let mut db = DatabaseAction {
            copy: true,
            ..DatabaseAction::default()
        };
        db.input.database_path = Some("/does/not/exist".to_owned());
        assert_eq!(db.execute(None, true).unwrap_err().0, 2);
    }
}
