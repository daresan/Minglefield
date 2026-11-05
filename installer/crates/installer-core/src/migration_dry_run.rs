//! Verified, non-persistent migration rehearsal on a consistent SQLite snapshot.
//! This never writes source records or creates the target SQLCipher database.
use crate::sqlite_inspection::{open_inspected_snapshot, SqliteInspection};
use rusqlite::{params, Connection, OptionalExtension};
use std::collections::BTreeSet;
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ReviewCorrection {
    UserDisabled {
        user_id: String,
        before: bool,
        after: bool,
    },
    AgentDisabled {
        agent_id: String,
        user_id: String,
        before: bool,
        after: bool,
    },
    EffectDescription {
        host_id: String,
        effect_id: String,
        before: String,
        after: String,
    },
    GameName {
        project_id: String,
        before: String,
        after: String,
    },
    EffectEnabled {
        host_id: String,
        effect_id: String,
        before: bool,
        after: bool,
    },
    GamePath {
        project_id: String,
        field: GamePathField,
        before: String,
        after: String,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GamePathField {
    RepositoryRoot,
    JobAttachmentsRoot,
    OutputRoot,
}

impl GamePathField {
    fn column(self) -> &'static str {
        match self {
            Self::RepositoryRoot => "repository_root",
            Self::JobAttachmentsRoot => "job_attachments_root",
            Self::OutputRoot => "output_root",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TableRowCount {
    pub table: String,
    pub rows: u64,
}

/// Schema-only field inventory. Column names are never accompanied by row
/// values, credential material or arbitrary JSON configuration.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TableFieldCoverage {
    pub table: String,
    pub columns: Vec<String>,
    pub staged_editable_columns: Vec<String>,
    pub protected_columns: Vec<String>,
}

fn staged_columns(table: &str) -> &'static [&'static str] {
    match table {
        "alpha_users" | "alpha_agents" => &["disabled"],
        "sec01_host_effect_definitions" => &["description", "enabled"],
        "alpha_game_projects" => &[
            "name",
            "repository_root",
            "job_attachments_root",
            "output_root",
        ],
        _ => &[],
    }
}

fn field_coverage(inspection: &SqliteInspection) -> Vec<TableFieldCoverage> {
    inspection
        .tables
        .iter()
        .map(|table| {
            let allowed = staged_columns(&table.name);
            let staged_editable_columns = table
                .columns
                .iter()
                .filter(|column| allowed.contains(&column.as_str()))
                .cloned()
                .collect();
            let protected_columns = table
                .columns
                .iter()
                .filter(|column| !allowed.contains(&column.as_str()))
                .cloned()
                .collect();
            TableFieldCoverage {
                table: table.name.clone(),
                columns: table.columns.clone(),
                staged_editable_columns,
                protected_columns,
            }
        })
        .collect()
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MigrationDryRun {
    pub tables: Vec<TableRowCount>,
    pub field_coverage: Vec<TableFieldCoverage>,
    pub schema_objects: usize,
    pub verified_changes: usize,
    pub source_records_written: bool,
    pub destination_created: bool,
    pub execution_enabled: bool,
}

const REQUIRED: &[(&str, &[&str])] = &[
    (
        "alpha_invites",
        &[
            "invitation_hash",
            "user_id",
            "expires_at",
            "redeemed",
            "revoked",
        ],
    ),
    ("alpha_users", &["user_id", "disabled"]),
    ("alpha_agents", &["agent_id", "user_id", "disabled"]),
    (
        "alpha_sessions",
        &["token_hash", "user_id", "expires_at", "revoked"],
    ),
    (
        "alpha_jobs",
        &["job_id", "user_id", "agent_id", "idempotency_key", "action"],
    ),
    ("alpha_passwords", &["user_id", "salt", "password_hash"]),
    (
        "alpha_agent_grants",
        &["agent_id", "grantee_user_id", "action", "revoked"],
    ),
];

fn validate_alpha_schema(snapshot: &SqliteInspection) -> Result<(), String> {
    for &(name, columns) in REQUIRED {
        let Some(table) = snapshot.tables.iter().find(|t| t.name == name) else {
            return Err(format!("Required Alpha table missing: {name}"));
        };
        if columns
            .iter()
            .any(|column| !table.columns.iter().any(|found| found == column))
        {
            return Err(format!(
                "Required Alpha table has incompatible columns: {name}"
            ));
        }
    }
    Ok(())
}

fn table_counts(
    db: &Connection,
    snapshot: &SqliteInspection,
) -> Result<Vec<TableRowCount>, String> {
    snapshot
        .tables
        .iter()
        .map(|table| {
            let escaped = table.name.replace('"', "\"\"");
            let sql = format!("SELECT count(*) FROM \"{escaped}\"");
            let rows: i64 = db
                .query_row(&sql, [], |row| row.get(0))
                .map_err(|_| "Unable to count all existing application tables")?;
            let rows = u64::try_from(rows).map_err(|_| "Invalid table row count")?;
            Ok(TableRowCount {
                table: table.name.clone(),
                rows,
            })
        })
        .collect()
}

fn valid_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .bytes()
            .all(|ch| ch.is_ascii_alphanumeric() || b"._-".contains(&ch))
}

fn valid_game_path(value: &str) -> bool {
    let bytes = value.as_bytes();
    let drive_absolute = bytes.len() >= 3
        && bytes[0].is_ascii_alphabetic()
        && bytes[1] == b':'
        && (bytes[2] == b'\\' || bytes[2] == b'/');
    let portable_absolute = value.starts_with('/') || value.starts_with("\\\\") || drive_absolute;
    !value.is_empty()
        && value.len() <= 1024
        && !value.contains('\0')
        && portable_absolute
        && !value.split(['/', '\\']).any(|part| part == "..")
}

fn verify_correction(correction: &ReviewCorrection) -> Result<(u8, String, String), String> {
    match correction {
        ReviewCorrection::UserDisabled {
            user_id,
            before,
            after,
        } => {
            if !valid_id(user_id) || before == after {
                return Err("Invalid user review correction".to_owned());
            }
            Ok((0, user_id.clone(), String::new()))
        }
        ReviewCorrection::AgentDisabled {
            agent_id,
            user_id,
            before,
            after,
        } => {
            if !valid_id(agent_id) || !valid_id(user_id) || before == after {
                return Err("Invalid Alpha agent correction".to_owned());
            }
            Ok((5, agent_id.clone(), String::new()))
        }
        ReviewCorrection::EffectDescription {
            host_id,
            effect_id,
            before,
            after,
        } => {
            if !valid_id(host_id)
                || !valid_id(effect_id)
                || before == after
                || before.chars().count() > 256
                || after.chars().count() > 256
                || before.contains('\0')
                || after.contains('\0')
            {
                return Err("Invalid effect review correction".to_owned());
            }
            Ok((1, host_id.clone(), effect_id.clone()))
        }
        ReviewCorrection::GameName {
            project_id,
            before,
            after,
        } => {
            if !valid_id(project_id)
                || before == after
                || after.trim() != after
                || after.is_empty()
                || after.chars().count() > 120
                || before.chars().count() > 120
                || before.contains('\0')
                || after.contains('\0')
            {
                return Err("Invalid project review correction".to_owned());
            }
            Ok((2, project_id.clone(), String::new()))
        }
        ReviewCorrection::EffectEnabled {
            host_id,
            effect_id,
            before,
            after,
        } => {
            if !valid_id(host_id) || !valid_id(effect_id) || before == after {
                return Err("Invalid effect activation correction".to_owned());
            }
            Ok((3, host_id.clone(), effect_id.clone()))
        }
        ReviewCorrection::GamePath {
            project_id,
            field,
            before,
            after,
        } => {
            if !valid_id(project_id)
                || before == after
                || !valid_game_path(before)
                || !valid_game_path(after)
            {
                return Err("Invalid game project path correction".to_owned());
            }
            Ok((4, project_id.clone(), field.column().to_owned()))
        }
    }
}

fn apply_verified_change(db: &Connection, correction: &ReviewCorrection) -> Result<(), String> {
    match correction {
        ReviewCorrection::UserDisabled {
            user_id,
            before,
            after,
        } => {
            let actual: Option<i64> = db
                .query_row(
                    "SELECT disabled FROM alpha_users WHERE user_id=?1",
                    [user_id],
                    |r| r.get(0),
                )
                .optional()
                .map_err(|_| "Cannot verify staged user")?;
            if actual != Some(i64::from(*before)) {
                return Err("Staged user value is stale or invalid".to_owned());
            }
            let changed = db
                .execute(
                    "UPDATE alpha_users SET disabled=?1 WHERE user_id=?2 AND disabled=?3",
                    params![i64::from(*after), user_id, i64::from(*before)],
                )
                .map_err(|_| "Cannot simulate staged user correction")?;
            if changed != 1 {
                return Err("Staged user was not updated in snapshot".to_owned());
            }
        }
        ReviewCorrection::AgentDisabled {
            agent_id,
            user_id,
            before,
            after,
        } => {
            let actual: Option<i64> = db
                .query_row(
                    "SELECT disabled FROM alpha_agents WHERE agent_id=?1 AND user_id=?2",
                    params![agent_id, user_id],
                    |r| r.get(0),
                )
                .optional()
                .map_err(|_| "Cannot verify staged Alpha agent")?;
            if actual != Some(i64::from(*before)) {
                return Err("Staged Alpha agent status or owner is stale".to_owned());
            }
            let changed = db.execute(
                "UPDATE alpha_agents SET disabled=?1 WHERE agent_id=?2 AND user_id=?3 AND disabled=?4",
                params![i64::from(*after), agent_id, user_id, i64::from(*before)],
            ).map_err(|_| "Cannot rehearse Alpha agent status")?;
            if changed != 1 {
                return Err("Alpha agent rehearsal update failed".to_owned());
            }
        }
        ReviewCorrection::EffectDescription {
            host_id,
            effect_id,
            before,
            after,
        } => {
            let actual: Option<String> = db.query_row(
                "SELECT description FROM sec01_host_effect_definitions WHERE host_id=?1 AND effect_id=?2",
                params![host_id, effect_id], |r| r.get(0),
            ).optional().map_err(|_| "Cannot verify staged effect")?;
            if actual.as_deref() != Some(before.as_str()) {
                return Err("Staged effect description is stale".to_owned());
            }
            let changed = db.execute(
                "UPDATE sec01_host_effect_definitions SET description=?1 WHERE host_id=?2 AND effect_id=?3 AND description=?4",
                params![after, host_id, effect_id, before],
            ).map_err(|_| "Cannot simulate staged effect correction")?;
            if changed != 1 {
                return Err("Staged effect was not updated in snapshot".to_owned());
            }
        }
        ReviewCorrection::GameName {
            project_id,
            before,
            after,
        } => {
            let actual: Option<String> = db
                .query_row(
                    "SELECT name FROM alpha_game_projects WHERE project_id=?1",
                    [project_id],
                    |r| r.get(0),
                )
                .optional()
                .map_err(|_| "Cannot verify staged project")?;
            if actual.as_deref() != Some(before.as_str()) {
                return Err("Staged project name is stale".to_owned());
            }
            let changed = db
                .execute(
                    "UPDATE alpha_game_projects SET name=?1 WHERE project_id=?2 AND name=?3",
                    params![after, project_id, before],
                )
                .map_err(|_| "Cannot simulate staged project correction")?;
            if changed != 1 {
                return Err("Staged project was not updated in snapshot".to_owned());
            }
        }
        ReviewCorrection::EffectEnabled {
            host_id,
            effect_id,
            before,
            after,
        } => {
            let actual: Option<i64> = db.query_row(
                "SELECT enabled FROM sec01_host_effect_definitions WHERE host_id=?1 AND effect_id=?2",
                params![host_id, effect_id], |r| r.get(0),
            ).optional().map_err(|_| "Cannot verify staged effect activation")?;
            if actual != Some(i64::from(*before)) {
                return Err("Staged effect activation is stale or invalid".to_owned());
            }
            let changed = db.execute(
                "UPDATE sec01_host_effect_definitions SET enabled=?1 WHERE host_id=?2 AND effect_id=?3 AND enabled=?4",
                params![i64::from(*after), host_id, effect_id, i64::from(*before)],
            ).map_err(|_| "Cannot simulate effect activation")?;
            if changed != 1 {
                return Err("Staged effect activation update failed".to_owned());
            }
        }
        ReviewCorrection::GamePath {
            project_id,
            field,
            before,
            after,
        } => {
            let column = field.column();
            let sql = format!("SELECT {column} FROM alpha_game_projects WHERE project_id=?1");
            let actual: Option<String> = db
                .query_row(&sql, [project_id], |r| r.get(0))
                .optional()
                .map_err(|_| "Cannot verify staged game path")?;
            if actual.as_deref() != Some(before.as_str()) {
                return Err("Staged game path is stale".to_owned());
            }
            let sql = format!(
                "UPDATE alpha_game_projects SET {column}=?1 WHERE project_id=?2 AND {column}=?3"
            );
            let changed = db
                .execute(&sql, params![after, project_id, before])
                .map_err(|_| "Cannot simulate staged game path")?;
            if changed != 1 {
                return Err("Staged game path update failed".to_owned());
            }
        }
    }
    Ok(())
}

/// Re-read the real source through a verified in-memory snapshot, assert the
/// expected original values, simulate only approved corrections and roll back
/// that temporary transaction. Unknown tables are accounted for, not omitted.
pub fn rehearse_migration(
    source: &Path,
    existing_password: &str,
    corrections: &[ReviewCorrection],
) -> Result<MigrationDryRun, String> {
    if corrections.len() > 1500 {
        return Err("Too many staged corrections".to_owned());
    }
    let (mut snapshot_db, inspection) = open_inspected_snapshot(source, existing_password)
        .map_err(|_| "Selected database could not be verified")?;
    if !inspection.integrity_ok || inspection.foreign_key_violations != 0 {
        return Err("Database integrity or foreign-key validation failed".to_owned());
    }
    validate_alpha_schema(&inspection)?;
    let original_counts = table_counts(&snapshot_db, &inspection)?;
    let mut identities = BTreeSet::new();
    for correction in corrections {
        let identity = verify_correction(correction)?;
        if !identities.insert(identity) {
            return Err("Duplicate staged correction".to_owned());
        }
    }
    if !corrections.is_empty()
        && inspection
            .schema_objects
            .iter()
            .any(|item| item.object_type == "trigger")
    {
        return Err("Database triggers require individual migration review".to_owned());
    }
    if !corrections.is_empty() {
        let transaction = snapshot_db
            .transaction()
            .map_err(|_| "Cannot begin isolated migration rehearsal")?;
        for correction in corrections {
            apply_verified_change(&transaction, correction)?;
        }
        let after_counts = table_counts(&transaction, &inspection)?;
        if after_counts != original_counts {
            return Err("Record counts changed during rehearsal".to_owned());
        }
        let check: String = transaction
            .query_row("PRAGMA quick_check", [], |row| row.get(0))
            .map_err(|_| "Rehearsed database integrity check failed")?;
        if check != "ok" {
            return Err("Rehearsed database is not integral".to_owned());
        }
        let violations: i64 = transaction
            .query_row("SELECT count(*) FROM pragma_foreign_key_check", [], |row| {
                row.get(0)
            })
            .map_err(|_| "Rehearsed foreign-key check failed")?;
        if violations != 0 {
            return Err("Rehearsed database has foreign-key violations".to_owned());
        }
        transaction
            .rollback()
            .map_err(|_| "Rehearsal rollback failed")?;
    }
    Ok(MigrationDryRun {
        tables: original_counts,
        field_coverage: field_coverage(&inspection),
        schema_objects: inspection.schema_objects.len(),
        verified_changes: corrections.len(),
        source_records_written: false,
        destination_created: false,
        execution_enabled: false,
    })
}

#[cfg(test)]
mod tests;
