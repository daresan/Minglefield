//! Verified, non-persistent migration rehearsal on a consistent SQLite snapshot.
//! This never writes source records or creates the target SQLCipher database.
use crate::snapshot_fidelity::{
    create_verified_memory_copy, verify_snapshot_equality, SnapshotFidelity,
};
use crate::sqlite_inspection::{open_inspected_snapshot, SqliteInspection};
use rusqlite::{params, Connection, OptionalExtension};
use std::collections::BTreeSet;
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RawCell {
    pub kind: String,
    pub value: Option<String>,
}

impl RawCell {
    fn to_sql(&self) -> Result<rusqlite::types::Value, String> {
        use rusqlite::types::Value;
        let raw = self.value.as_deref();
        match (self.kind.as_str(), raw) {
            ("null", None) => Ok(Value::Null),
            ("integer", Some(value)) => value
                .parse::<i64>()
                .map(Value::Integer)
                .map_err(|_| "Invalid SQLite integer".to_owned()),
            ("real", Some(value)) => value
                .parse::<f64>()
                .ok()
                .filter(|v| v.is_finite())
                .map(Value::Real)
                .ok_or_else(|| "Invalid SQLite real value".to_owned()),
            ("text", Some(value)) if value.len() <= 4 * 1024 * 1024 => {
                Ok(Value::Text(value.to_owned()))
            }
            ("blob", Some(value)) if value.len() <= 8 * 1024 * 1024 && value.len() % 2 == 0 => {
                let mut bytes = Vec::with_capacity(value.len() / 2);
                for part in value.as_bytes().chunks_exact(2) {
                    let text = std::str::from_utf8(part)
                        .map_err(|_| "Invalid hexadecimal BLOB".to_owned())?;
                    bytes.push(
                        u8::from_str_radix(text, 16)
                            .map_err(|_| "Invalid hexadecimal BLOB".to_owned())?,
                    );
                }
                Ok(Value::Blob(bytes))
            }
            _ => Err("Invalid or oversized SQLite cell".to_owned()),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ReviewCorrection {
    FullRow {
        table: String,
        row_id: Option<String>,
        columns: Vec<String>,
        before: Vec<RawCell>,
        after: Vec<RawCell>,
    },
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
    GitProfileText {
        host_id: String,
        profile_id: String,
        owner_id: String,
        field: GitProfileField,
        before: String,
        after: String,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GitProfileField {
    Label,
    AuthorName,
    AuthorEmail,
}

impl GitProfileField {
    fn column(self) -> &'static str {
        match self {
            Self::Label => "label",
            Self::AuthorName => "author_name",
            Self::AuthorEmail => "author_email",
        }
    }
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

fn field_coverage(inspection: &SqliteInspection) -> Vec<TableFieldCoverage> {
    inspection
        .tables
        .iter()
        .map(|table| {
            // Every stored column is available to the generic typed review.
            // Database constraints and generated-column restrictions are
            // checked by SQLite on an isolated copy before accepting edits.
            let staged_editable_columns = table.columns.clone();
            let protected_columns = Vec::new();
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
    pub fidelity: SnapshotFidelity,
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

pub(crate) fn validate_alpha_schema(snapshot: &SqliteInspection) -> Result<(), String> {
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

pub(crate) fn table_counts(
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
        ReviewCorrection::FullRow {
            table,
            row_id,
            columns,
            before,
            after,
        } => {
            if table.is_empty()
                || table.starts_with("sqlite_")
                || table.len() > 256
                || columns.is_empty()
                || columns.len() > 1024
                || before.len() != columns.len()
                || after.len() != columns.len()
                || before == after
                || columns.iter().any(|col| col.is_empty() || col.len() > 256)
                || columns.iter().collect::<BTreeSet<_>>().len() != columns.len()
            {
                return Err("Invalid full-row migration correction".to_owned());
            }
            if let Some(id) = row_id {
                id.parse::<i64>()
                    .map_err(|_| "Invalid original row identifier")?;
            }
            for cell in before.iter().chain(after) {
                cell.to_sql()?;
            }
            // Row identity uses a native rowid when available. WITHOUT ROWID
            // tables are matched by their complete original typed values.
            let identity = row_id.clone().unwrap_or_else(|| format!("{before:?}"));
            Ok((7, table.clone(), identity))
        }
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
        ReviewCorrection::GitProfileText {
            host_id,
            profile_id,
            owner_id,
            field,
            before,
            after,
        } => {
            if !valid_id(host_id)
                || !valid_id(profile_id)
                || !valid_id(owner_id)
                || before == after
                || before.contains('\0')
                || after.contains('\0')
                || before.chars().count() > 256
                || after.chars().count() > 256
                || (matches!(field, GitProfileField::Label)
                    && (after.trim() != after || after.is_empty() || after.chars().count() > 120))
            {
                return Err("Invalid Git profile text correction".to_owned());
            }
            Ok((
                6,
                format!("{host_id}:{profile_id}"),
                field.column().to_owned(),
            ))
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
        ReviewCorrection::FullRow {
            table,
            row_id,
            columns,
            before,
            after,
        } => {
            let expected: Vec<String> = {
                let mut stmt = db
                    .prepare("SELECT name FROM pragma_table_xinfo(?1) ORDER BY cid")
                    .map_err(|_| "Cannot inspect staged table columns")?;
                let found = stmt
                    .query_map([table], |row| row.get(0))
                    .map_err(|_| "Cannot inspect staged table layout")?
                    .collect::<rusqlite::Result<_>>()
                    .map_err(|_| "Cannot read staged table layout")?;
                found
            };
            if &expected != columns {
                return Err("Source table schema changed since review".to_owned());
            }
            let name = format!("\"{}\"", table.replace('"', "\"\""));
            let quoted = columns
                .iter()
                .map(|col| format!("\"{}\"", col.replace('"', "\"\"")))
                .collect::<Vec<_>>();
            let previous = before
                .iter()
                .map(RawCell::to_sql)
                .collect::<Result<Vec<_>, _>>()?;
            let new = after
                .iter()
                .map(RawCell::to_sql)
                .collect::<Result<Vec<_>, _>>()?;
            let mut predicate_values = Vec::new();
            let predicate = if let Some(id) = row_id {
                predicate_values.push(rusqlite::types::Value::Integer(
                    id.parse().map_err(|_| "Invalid original row identifier")?,
                ));
                "rowid IS ?".to_owned()
            } else {
                predicate_values.extend(previous.iter().cloned());
                quoted
                    .iter()
                    .map(|col| format!("{col} IS ?"))
                    .collect::<Vec<_>>()
                    .join(" AND ")
            };
            let read_sql = format!("SELECT {} FROM {name} WHERE {predicate}", quoted.join(","));
            let mut stmt = db
                .prepare(&read_sql)
                .map_err(|_| "Cannot prepare original row verification")?;
            let mut rows = stmt
                .query(rusqlite::params_from_iter(predicate_values.iter()))
                .map_err(|_| "Cannot verify original row")?;
            let observed = rows
                .next()
                .map_err(|_| "Cannot read original row")?
                .ok_or("Original row no longer exists")?;
            let actual = (0..columns.len())
                .map(|index| observed.get::<_, rusqlite::types::Value>(index))
                .collect::<rusqlite::Result<Vec<_>>>()
                .map_err(|_| "Cannot decode original row")?;
            if actual != previous {
                return Err("Staged row contains stale original values".to_owned());
            }
            if rows
                .next()
                .map_err(|_| "Cannot check ambiguous original rows")?
                .is_some()
            {
                return Err("Original row is ambiguous without an SQLite rowid".to_owned());
            }
            drop(rows);
            drop(stmt);
            let changed_columns: Vec<usize> = (0..columns.len())
                .filter(|index| previous[*index] != new[*index])
                .collect();
            let setters = changed_columns
                .iter()
                .map(|index| format!("{} = ?", quoted[*index]))
                .collect::<Vec<_>>()
                .join(",");
            let update_sql = format!("UPDATE {name} SET {setters} WHERE {predicate}");
            let mut bind = changed_columns
                .iter()
                .map(|index| new[*index].clone())
                .collect::<Vec<_>>();
            bind.extend(predicate_values);
            let count = db
                .execute(&update_sql, rusqlite::params_from_iter(bind.iter()))
                .map_err(|_| "Cannot apply staged full-row edit to isolated copy")?;
            if count != 1 {
                return Err("Staged full-row edit did not match exactly one row".to_owned());
            }
        }
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
        ReviewCorrection::GitProfileText {
            host_id,
            profile_id,
            owner_id,
            field,
            before,
            after,
        } => {
            let column = field.column();
            let sql = format!(
                "SELECT {column} FROM alpha_git_profiles WHERE host_id=?1 AND profile_id=?2 AND owner_id=?3"
            );
            let actual: Option<String> = db
                .query_row(&sql, params![host_id, profile_id, owner_id], |r| r.get(0))
                .optional()
                .map_err(|_| "Cannot verify staged Git profile")?;
            if actual.as_deref() != Some(before.as_str()) {
                return Err("Staged Git profile value, identity or owner is stale".to_owned());
            }
            let sql = format!(
                "UPDATE alpha_git_profiles SET {column}=?1 WHERE host_id=?2 AND profile_id=?3 AND owner_id=?4 AND {column}=?5"
            );
            let changed = db
                .execute(&sql, params![after, host_id, profile_id, owner_id, before])
                .map_err(|_| "Cannot simulate Git profile correction")?;
            if changed != 1 {
                return Err("Staged Git profile update failed".to_owned());
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

/// The only allowlisted mutation path for temporary migration copies.
/// Both memory rollback tests and encrypted-disk-copy tests reuse this exact
/// stale-value, owner-binding, duplicate, trigger, integrity and count policy.
/// `commit_to_isolated_copy` must NEVER be used with the original source:
/// the caller is responsible for an independently verified RAM snapshot.
pub(crate) fn apply_staged_to_isolated_copy(
    rehearsal_db: &mut Connection,
    inspection: &SqliteInspection,
    original_counts: &[TableRowCount],
    corrections: &[ReviewCorrection],
    commit_to_isolated_copy: bool,
) -> Result<(), String> {
    if corrections.len() > 1500 {
        return Err("Too many staged corrections".to_owned());
    }
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

    if corrections.is_empty() {
        return Ok(());
    }
    let transaction = rehearsal_db
        .transaction()
        .map_err(|_| "Cannot begin isolated migration rehearsal")?;
    for correction in corrections {
        apply_verified_change(&transaction, correction)?;
    }
    let after_counts = table_counts(&transaction, inspection)?;
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
    if commit_to_isolated_copy {
        transaction
            .commit()
            .map_err(|_| "Cannot retain edits in isolated memory copy".to_owned())?;
    } else {
        transaction
            .rollback()
            .map_err(|_| "Rehearsal rollback failed".to_owned())?;
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
    let (snapshot_db, inspection) = open_inspected_snapshot(source, existing_password)
        .map_err(|_| "Selected database could not be verified")?;
    if !inspection.integrity_ok || inspection.foreign_key_violations != 0 {
        return Err("Database integrity or foreign-key validation failed".to_owned());
    }
    validate_alpha_schema(&inspection)?;
    let original_counts = table_counts(&snapshot_db, &inspection)?;
    // A password may have been entered for a plaintext Alpha source.
    // Only initialize the second SQLCipher in-memory copy with a key when
    // source inspection actually detected an encrypted database.
    let snapshot_key = if inspection.source_encrypted {
        existing_password
    } else {
        ""
    };
    let (mut rehearsal_db, before_fidelity) =
        create_verified_memory_copy(&snapshot_db, snapshot_key)?;
    apply_staged_to_isolated_copy(
        &mut rehearsal_db,
        &inspection,
        &original_counts,
        corrections,
        false,
    )?;
    let fidelity = verify_snapshot_equality(&snapshot_db, &rehearsal_db)?;
    if fidelity != before_fidelity {
        return Err("Temporary migration rehearsal failed to restore all original data".to_owned());
    }
    Ok(MigrationDryRun {
        tables: original_counts,
        field_coverage: field_coverage(&inspection),
        schema_objects: inspection.schema_objects.len(),
        fidelity,
        verified_changes: corrections.len(),
        source_records_written: false,
        destination_created: false,
        execution_enabled: false,
    })
}

#[cfg(test)]
mod tests;
