//! One bounded headless same-process installation and *new* local Host setup.
//! This is NOT a generic way to claim an existing database or remote Host.
//! Each invocation must verify the managed Alpha application, exclusively
//! create a new SQLCipher target, and use its private installed first-run
//! admission worker. No separate or reusable "authorize an old DB" command.
use crate::database::{flag_value, DatabaseAction};
use minglefield_installer_core::config_v3::{
    parse_stdin_secrets, DatabaseOptions, LocalHostOptions,
};
use minglefield_installer_core::database_password::validate_new_database_password;
use minglefield_installer_core::db_operations::{
    create_new_encrypted_database, NEW_ENCRYPTED_DATABASE_CONFIRMATION,
};
use minglefield_installer_core::local_first_run_worker::{
    run_verified_local_first_run_worker, valid_login_name, validate_local_credentials,
    LOCAL_ADMIN_CONFIRMATION,
};
use minglefield_installer_core::managed_alpha_install::{
    install_from_verified_root, verified_inventory, verify_installed_application,
};
use std::env;
use std::io::{Read, Write};
use std::path::Path;
use std::process::{Command, Stdio};

#[derive(Default)]
pub struct LocalSetupAction {
    pub enabled: bool,
    pub verify_native_start: bool,
    pub input: LocalHostOptions,
}

impl LocalSetupAction {
    pub fn parse(
        &mut self,
        argument: &str,
        args: &mut impl Iterator<Item = String>,
    ) -> Result<bool, (u8, String)> {
        if let Some((name, value)) = argument.split_once('=') {
            let target = match name {
                "--login-user-id" => &mut self.input.login_user_id,
                "--local-host-id" => &mut self.input.local_host_id,
                "--login-password" => &mut self.input.login_password.literal,
                "--login-password-file" => &mut self.input.login_password.file,
                "--confirm-local-admin" => &mut self.input.confirmation,
                _ => return Ok(false),
            };
            if target.is_some() {
                return Err((2, "duplicate local setup option".into()));
            }
            *target = Some(value.to_owned());
            return Ok(true);
        }
        match argument {
            "--verify-native-start" if !self.verify_native_start => {
                self.verify_native_start = true;
            }
            "--verify-native-start" => {
                return Err((2, "duplicate --verify-native-start".into()));
            }
            "--login-user-id" => {
                flag_value(args, "--login-user-id", &mut self.input.login_user_id)?;
            }
            "--local-host-id" => {
                flag_value(args, "--local-host-id", &mut self.input.local_host_id)?;
            }
            "--login-password" => {
                flag_value(
                    args,
                    "--login-password",
                    &mut self.input.login_password.literal,
                )?;
            }
            "--login-password-file" => {
                flag_value(
                    args,
                    "--login-password-file",
                    &mut self.input.login_password.file,
                )?;
            }
            "--confirm-local-admin" => {
                flag_value(args, "--confirm-local-admin", &mut self.input.confirmation)?;
            }
            _ => return Ok(false),
        }
        Ok(true)
    }

    /// Explicit consent plus all required credentials are resolved before
    /// filesystem writes. The only final Host authority is the real
    /// installed admission/Host policy, invoked after current-session proof.
    #[allow(clippy::too_many_arguments)]
    pub fn execute(
        &self,
        package: &Path,
        install_dir: &Path,
        expected_inventory_sha256: &str,
        file_confirmation: Option<&str>,
        db_action: &DatabaseAction,
        db_config: Option<&DatabaseOptions>,
        host_config: Option<&LocalHostOptions>,
        json: bool,
    ) -> Result<(), (u8, String)> {
        if !self.enabled
            || !db_action.fresh
            || db_action.verify
            || db_action.copy
            || file_confirmation != Some("INSTALL MINGLEFIELD ALPHA FILES")
        {
            return Err((
                2,
                "full fresh local setup requires file, fresh DB and local Host approval".into(),
            ));
        }
        let mut db = db_config.cloned().unwrap_or_default();
        db.override_with(db_action.input.clone());
        let mut host = host_config.cloned().unwrap_or_default();
        host.override_with(self.input.clone());
        if db.source_path.is_some()
            || db.backup_path.is_some()
            || db.password.literal.is_some()
            || db.password.file.is_some()
            || db.copy_confirmation.is_some()
            || !db.schema_additions.is_empty()
        {
            return Err((
                2,
                "local setup cannot import an existing database or Host".into(),
            ));
        }
        if db.new_db_confirmation.as_deref() != Some(NEW_ENCRYPTED_DATABASE_CONFIRMATION)
            || host.confirmation.as_deref() != Some(LOCAL_ADMIN_CONFIRMATION)
        {
            return Err((
                2,
                "explicit new database and local Host consent required".into(),
            ));
        }
        let database = db
            .database_path
            .as_deref()
            .ok_or((2, "fresh local setup requires --database".to_owned()))?;
        let database = Path::new(database);
        let login_user = host.login_user_id.as_deref().unwrap_or("mingleadmin");
        if !valid_login_name(login_user) {
            return Err((2, "invalid local login user ID".into()));
        }
        if let Some(host_id) = host.local_host_id.as_deref() {
            if !host_id.starts_with("local.") || !valid_login_name(host_id) {
                return Err((2, "invalid explicitly selected local Host ID".into()));
            }
        }
        let frame = if db_action.stdin {
            parse_stdin_secrets(std::io::stdin().lock())
                .map_err(|_| (3, "private secrets stdin rejected".to_owned()))?
        } else {
            minglefield_installer_core::config_v3::StdinSecrets {
                db_password: None,
                new_db_password: None,
                login_password: None,
            }
        };
        if frame.db_password.is_some() {
            return Err((
                2,
                "fresh local Host setup does not accept an old DB key".into(),
            ));
        }
        let cipher_key = db
            .new_password
            .resolve(
                env::var("MINGLEFIELD_NEW_DB_PASSWORD").ok(),
                frame.new_db_password.as_deref(),
            )
            .map_err(|_| (3, "invalid or conflicting new SQLCipher key sources".into()))?
            .ok_or((3, "new SQLCipher database password required".to_owned()))?;
        let login_password = host
            .login_password
            .resolve(
                env::var("MINGLEFIELD_LOGIN_PASSWORD").ok(),
                frame.login_password.as_deref(),
            )
            .map_err(|_| {
                (
                    3,
                    "invalid or conflicting local login secret sources".into(),
                )
            })?
            .ok_or((3, "local login password required".to_owned()))?;
        validate_new_database_password(&cipher_key)
            .map_err(|_| (3, "new SQLCipher key does not meet policy".to_owned()))?;
        validate_local_credentials(
            login_user,
            &login_password,
            &cipher_key,
            LOCAL_ADMIN_CONFIRMATION,
        )
        .map_err(|_| {
            (
                3,
                "independent approved local login credentials required".to_owned(),
            )
        })?;

        // Reject a missing native starter before any fresh DB or file write.
        if self.verify_native_start {
            let native = if cfg!(windows) {
                package.join("Minglefield.exe")
            } else {
                package.join("Minglefield")
            };
            let metadata = std::fs::symlink_metadata(&native)
                .map_err(|_| (4, "native Minglefield application not in package".to_owned()))?;
            if !metadata.is_file() || metadata.file_type().is_symlink() {
                return Err((4, "native Minglefield executable is not a regular file".into()));
            }
        }

        // Preflight the *whole package* before creating an encrypted DB or
        // installing bytes. This digest must be operator trusted; the digest
        // is not a publisher-signature verification.
        verified_inventory(package, expected_inventory_sha256).map_err(|_| {
            (
                4,
                "managed Alpha source inventory verification rejected".to_owned(),
            )
        })?;
        let installed = install_from_verified_root(package, install_dir, expected_inventory_sha256)
            .map_err(|_| {
                (
                    4,
                    "verified local Alpha application install rejected".to_owned(),
                )
            })?;
        let installed_root = Path::new(&installed.install_dir);
        verify_installed_application(installed_root, expected_inventory_sha256).map_err(|_| {
            (
                4,
                "installed Alpha application verification rejected".to_owned(),
            )
        })?;

        // The DB is created EXCLUSIVELY in this invocation. Existing user
        // identities and already-owned Host databases can never enter here.
        create_new_encrypted_database(database, &cipher_key, NEW_ENCRYPTED_DATABASE_CONFIRMATION)
            .map_err(|_| (4, "fresh local SQLCipher creation rejected".to_owned()))?;

        // The first SQLCipher header bytes are a unique, non-secret random
        // salt on a genuinely new database. The derived Host ID is an
        // identifier, never an authorization token or recovery operation ID.
        let local_host_id = match host.local_host_id {
            Some(value) => value,
            None => {
                let mut salt = [0_u8; 16];
                std::fs::File::open(database)
                    .and_then(|mut file| file.read_exact(&mut salt))
                    .map_err(|_| (4, "new SQLCipher header unavailable".to_owned()))?;
                let suffix = salt
                    .iter()
                    .map(|byte| format!("{byte:02x}"))
                    .collect::<String>();
                format!("local.{suffix}")
            }
        };
        // Record exact bytes and recheck immediately before the worker.
        let (before, byte_count) = minglefield_installer_core::integrity::sha256_reader_hex(
            std::fs::File::open(database)
                .map_err(|_| (4, "new SQLCipher target unavailable".to_owned()))?,
        )
        .map_err(|_| (4, "cannot fingerprint fresh SQLCipher target".to_owned()))?;
        if byte_count < 16 {
            return Err((4, "fresh SQLCipher target is incomplete".into()));
        }
        let metadata = std::fs::symlink_metadata(database)
            .map_err(|_| (4, "fresh SQLCipher target unavailable".to_owned()))?;
        if !metadata.is_file() || metadata.file_type().is_symlink() {
            return Err((4, "fresh SQLCipher target type changed".into()));
        }
        let (now, current_bytes) = minglefield_installer_core::integrity::sha256_reader_hex(
            std::fs::File::open(database)
                .map_err(|_| (4, "fresh SQLCipher target unavailable".to_owned()))?,
        )
        .map_err(|_| (4, "fresh SQLCipher target verification failed".to_owned()))?;
        if now != before || current_bytes != byte_count {
            return Err((4, "fresh SQLCipher target changed before first-run".into()));
        }
        let receipt = run_verified_local_first_run_worker(
            installed_root,
            database,
            &cipher_key,
            login_user,
            &login_password,
            &local_host_id,
        )
        .map_err(|_| {
            (
                4,
                "installed local Host first-run authorization rejected".to_owned(),
            )
        })?;
        if self.verify_native_start {
            probe_native_application(installed_root, database, &cipher_key).map_err(|_| {
                (
                    4,
                    "local Host was created, but native startup verification failed; preserve installed data for review"
                        .to_owned(),
                )
            })?;
        }
        if json {
            println!(
                "{{\"schema_version\":1,\"status\":\"local_host_admin_created\",\"login_user_id\":\"{}\",\"local_host_id\":\"{}\",\"remote_host_authority_granted\":false,\"application_files_installed\":true,\"encrypted_database_created\":true,\"native_application_launch_enabled\":{},\"full_installation_completed\":false}}",
                receipt.login_user_id, receipt.local_host_id, self.verify_native_start
            );
        } else {
            println!(
                "Verified local Alpha files and new SQLCipher database installed; local Host {} initialized",
                receipt.local_host_id
            );
        }
        Ok(())
    }
}

/// Launch the installed native starter with the existing private stdin
/// credential contract. Probe loopback readiness, then stop without a browser.
/// A failed post-setup probe never authorizes a replay or removes user data.
fn probe_native_application(
    installed_root: &Path,
    database: &Path,
    cipher_key: &str,
) -> Result<(), &'static str> {
    let native = if cfg!(windows) {
        installed_root.join("Minglefield.exe")
    } else {
        installed_root.join("Minglefield")
    };
    let mut child = Command::new(native)
        .arg("--database")
        .arg(database)
        .arg("--secrets-stdin")
        .arg("--probe-exit")
        .arg("--no-browser")
        .arg("--no-dialog")
        .env_remove("MINGLEFIELD_DB_PASSWORD")
        .env_remove("MINGLEFIELD_NEW_DB_PASSWORD")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "cannot launch installed native application")?;
    let frame = serde_json::json!({
        "db_password": cipher_key,
        "new_db_password": null,
        "login_password": null
    });
    {
        let mut stdin = child.stdin.take().ok_or("native stdin unavailable")?;
        serde_json::to_writer(&mut stdin, &frame)
            .map_err(|_| "cannot deliver native private key frame")?;
        stdin.flush().map_err(|_| "cannot flush private key frame")?;
    }
    let output = child
        .wait_with_output()
        .map_err(|_| "native application verification unavailable")?;
    if !output.status.success() {
        return Err("installed native application failed startup");
    }
    let report: serde_json::Value =
        serde_json::from_slice(&output.stdout).map_err(|_| "invalid native readiness response")?;
    if report.get("status").and_then(serde_json::Value::as_str)
        != Some("native_minglefield_startup_verified")
        || report.get("encryptedDatabase").and_then(serde_json::Value::as_bool) != Some(true)
        || report.get("hostProvisioningEnabled").and_then(serde_json::Value::as_bool) != Some(false)
        || report.get("hostClaimBootstrapEnabled").and_then(serde_json::Value::as_bool)
            != Some(false)
        || report.get("bind").and_then(serde_json::Value::as_str) != Some("127.0.0.1")
    {
        return Err("native application readiness contract rejected");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn refuses_setup_with_no_current_process_install_or_new_db() {
        let setup = LocalSetupAction {
            enabled: true,
            ..LocalSetupAction::default()
        };
        let db = DatabaseAction::default();
        assert_eq!(
            setup
                .execute(
                    Path::new("/missing/package"),
                    Path::new("/missing/application"),
                    &"0".repeat(64),
                    None,
                    &db,
                    None,
                    None,
                    true
                )
                .unwrap_err()
                .0,
            2
        );
    }

    #[test]
    fn canonical_local_password_parameter_supports_leading_dashes() {
        let mut setup = LocalSetupAction::default();
        assert!(setup
            .parse(
                "--login-password=--SensitiveLogin9!",
                &mut std::iter::empty(),
            )
            .unwrap());
        assert_eq!(
            setup.input.login_password.literal.as_deref(),
            Some("--SensitiveLogin9!")
        );
    }
}
