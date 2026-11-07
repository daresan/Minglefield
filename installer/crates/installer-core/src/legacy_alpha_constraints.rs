//! Independently registered full DDL and index-object audit for the unversioned
//! local Alpha SQLite family. This is read-only and does not authorize migration.
//! CREATE statements are mirrored from the three authoritative server modules.
//! No rows, credentials, or host settings are embedded in this contract.
use crate::sqlite_inspection::SqliteInspection;
use rusqlite::Connection;
use std::collections::{BTreeMap, BTreeSet};

const REGISTERED_SOURCE_SQL: &[(&str, &str)] = &[
    (
        "alpha_invites",
        r#"CREATE TABLE IF NOT EXISTS alpha_invites(
                invitation_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE,
                expires_at INTEGER NOT NULL, redeemed INTEGER NOT NULL DEFAULT 0,
                revoked INTEGER NOT NULL DEFAULT 0)"#,
    ),
    (
        "alpha_users",
        r#"CREATE TABLE IF NOT EXISTS alpha_users(
                user_id TEXT PRIMARY KEY, disabled INTEGER NOT NULL DEFAULT 0)"#,
    ),
    (
        "alpha_agents",
        r#"CREATE TABLE IF NOT EXISTS alpha_agents(
                agent_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0)"#,
    ),
    (
        "alpha_sessions",
        r#"CREATE TABLE IF NOT EXISTS alpha_sessions(
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                expires_at INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)"#,
    ),
    (
        "alpha_jobs",
        r#"CREATE TABLE IF NOT EXISTS alpha_jobs(
                job_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, agent_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL, action TEXT NOT NULL,
                UNIQUE(user_id,idempotency_key))"#,
    ),
    (
        "alpha_passwords",
        r#"CREATE TABLE IF NOT EXISTS alpha_passwords(
                user_id TEXT PRIMARY KEY, salt BLOB NOT NULL, password_hash BLOB NOT NULL)"#,
    ),
    (
        "alpha_agent_grants",
        r#"CREATE TABLE IF NOT EXISTS alpha_agent_grants(
                agent_id TEXT NOT NULL, grantee_user_id TEXT NOT NULL,
                action TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(agent_id,grantee_user_id,action))"#,
    ),
    (
        "alpha_executor_hosts",
        r#"CREATE TABLE IF NOT EXISTS alpha_executor_hosts(
                host_id TEXT PRIMARY KEY, operator_id TEXT NOT NULL,
                active INTEGER NOT NULL CHECK(active IN (0,1)))"#,
    ),
    (
        "alpha_agent_host_assignments",
        r#"CREATE TABLE IF NOT EXISTS alpha_agent_host_assignments(
                agent_id TEXT NOT NULL, host_id TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
                PRIMARY KEY(agent_id,host_id))"#,
    ),
    (
        "alpha_sec01_admissions",
        r#"CREATE TABLE IF NOT EXISTS alpha_sec01_admissions(
                effect_key TEXT PRIMARY KEY, binding TEXT NOT NULL)"#,
    ),
    (
        "sec01_host_comfy_workflows",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_comfy_workflows(
                host_id TEXT NOT NULL, effect_id TEXT NOT NULL,
                runtime_id TEXT NOT NULL, workflow TEXT NOT NULL,
                metadata TEXT NOT NULL, PRIMARY KEY(host_id,effect_id))"#,
    ),
    (
        "sec01_host_job_parameters",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_job_parameters(
                job_id TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                effect_id TEXT NOT NULL, workflow_sha256 TEXT NOT NULL,
                parameters TEXT NOT NULL)"#,
    ),
    (
        "alpha_git_profiles",
        r#"CREATE TABLE IF NOT EXISTS alpha_git_profiles(
                host_id TEXT NOT NULL, profile_id TEXT NOT NULL, owner_id TEXT NOT NULL,
                auth_method TEXT NOT NULL, label TEXT NOT NULL,
                git_executable TEXT NOT NULL, author_name TEXT NOT NULL,
                author_email TEXT NOT NULL, PRIMARY KEY(host_id,profile_id))"#,
    ),
    (
        "alpha_game_installation_evidence",
        r#"CREATE TABLE IF NOT EXISTS alpha_game_installation_evidence(
                host_id TEXT NOT NULL, project_id TEXT NOT NULL,
                integration_id TEXT NOT NULL, installer_run_id TEXT NOT NULL,
                evidence_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
                PRIMARY KEY(host_id,project_id,integration_id,installer_run_id),
                FOREIGN KEY(project_id) REFERENCES alpha_game_projects(project_id))"#,
    ),
    (
        "alpha_game_projects",
        r#"CREATE TABLE IF NOT EXISTS alpha_game_projects(
                project_id TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                owner_id TEXT NOT NULL, name TEXT NOT NULL,
                repository_root TEXT NOT NULL, job_attachments_root TEXT NOT NULL,
                output_root TEXT NOT NULL, settings_revision INTEGER NOT NULL DEFAULT 1,
                UNIQUE(host_id,project_id))"#,
    ),
    (
        "sec01_game_install_journal",
        r#"CREATE TABLE IF NOT EXISTS sec01_game_install_journal(
                operation_id TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                owner_id TEXT NOT NULL, project_id TEXT NOT NULL,
                state TEXT NOT NULL, plan_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"#,
    ),
    (
        "sec01_host_settings",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_settings(
                host_id TEXT PRIMARY KEY, settings TEXT NOT NULL)"#,
    ),
    (
        "sec01_host_runtimes",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_runtimes(
                host_id TEXT NOT NULL, runtime_id TEXT NOT NULL,
                config TEXT NOT NULL, PRIMARY KEY(host_id,runtime_id))"#,
    ),
    (
        "sec01_host_owners",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_owners(
                host_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL)"#,
    ),
    (
        "sec01_host_effect_definitions",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_effect_definitions(
                host_id TEXT NOT NULL, effect_id TEXT NOT NULL,
                description TEXT NOT NULL, enabled INTEGER NOT NULL,
                PRIMARY KEY(host_id,effect_id))"#,
    ),
    (
        "sec01_host_jobs",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_jobs(
                job_id TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                effect_id TEXT NOT NULL, requested_by TEXT NOT NULL,
                state TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(host_id,job_id))"#,
    ),
    (
        "sec01_host_admins",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_admins(
                host_id TEXT NOT NULL, admin_id TEXT NOT NULL,
                PRIMARY KEY(host_id,admin_id))"#,
    ),
    (
        "sec01_host_rules",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_rules(
                host_id TEXT NOT NULL, rule_id TEXT NOT NULL,
                priority INTEGER NOT NULL, enabled INTEGER NOT NULL,
                config TEXT NOT NULL, PRIMARY KEY(host_id,rule_id))"#,
    ),
    (
        "sec01_host_approvals",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_approvals(
                host_id TEXT NOT NULL, effect_key TEXT NOT NULL,
                approved_by TEXT NOT NULL, PRIMARY KEY(host_id,effect_key))"#,
    ),
    (
        "sec01_host_commits",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_commits(
                effect_key TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                binding TEXT NOT NULL, rule_id TEXT NOT NULL)"#,
    ),
    (
        "sec01_host_active_slots",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_active_slots(
                effect_key TEXT PRIMARY KEY, host_id TEXT NOT NULL)"#,
    ),
    (
        "sec01_host_comfy_executions",
        r#"CREATE TABLE IF NOT EXISTS sec01_host_comfy_executions(
                job_id TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                prompt_id TEXT, error TEXT)"#,
    ),
];
const ACTIVE_GAME_INDEX: &str = r#"CREATE UNIQUE INDEX IF NOT EXISTS uq_game_install_one_active_project ON sec01_game_install_journal(host_id,project_id) WHERE state NOT IN ('cancelled','committed','rolled_back')"#;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AlphaSchemaObjectAudit {
    pub verified: bool,
    pub reason: &'static str,
    pub expected_schema_entry_count: usize,
    pub matched_schema_entry_count: usize,
    pub expected_index_count: usize,
    pub missing_objects: Vec<String>,
    pub extra_objects: Vec<String>,
    pub incompatible_objects: Vec<String>,
    pub migration_enabled: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ObjectRow {
    kind: String,
    name: String,
    table: String,
    sql: Option<String>,
}

/// Canonicalize SQL formatting and harmless SQLite identifier quoting.
/// Preserve case and whitespace **inside SQL string literals** (partial
/// index filtering and DEFAULT literals must never change semantics).
fn canonical_sql(sql: &str) -> String {
    let mut output = String::with_capacity(sql.len());
    let mut string_literal = false;
    for ch in sql.chars() {
        if ch == '\'' {
            string_literal = !string_literal;
            output.push(ch);
        } else if string_literal {
            output.push(ch);
        } else if ch == '"' || ch == '`' || ch.is_ascii_whitespace() {
            continue;
        } else {
            output.push(ch.to_ascii_uppercase());
        }
    }
    output.trim_end_matches(';').to_owned()
}

fn schema_objects(db: &Connection) -> Result<BTreeMap<String, ObjectRow>, String> {
    let mut stmt = db
        .prepare("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name")
        .map_err(|_| "Cannot prepare complete Alpha schema audit")?;
    let rows = stmt
        .query_map([], |row| {
            Ok(ObjectRow {
                kind: row.get(0)?,
                name: row.get(1)?,
                table: row.get(2)?,
                sql: row.get::<_, Option<String>>(3)?.map(|s| canonical_sql(&s)),
            })
        })
        .map_err(|_| "Cannot enumerate complete Alpha schema objects")?
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|_| "Cannot decode complete Alpha schema objects")?;
    if rows.len() > 8192 {
        return Err("Alpha source exceeds safe schema object limit".to_owned());
    }
    let mut entries = BTreeMap::new();
    for row in rows {
        if entries.insert(row.name.clone(), row).is_some() {
            return Err("Duplicate SQLite schema object name".to_owned());
        }
    }
    Ok(entries)
}

fn known_reference() -> Result<Connection, String> {
    let db = Connection::open_in_memory()
        .map_err(|_| "Cannot allocate registered Alpha schema reference")?;
    for &(name, sql) in REGISTERED_SOURCE_SQL {
        db.execute_batch(sql)
            .map_err(|_| format!("Registered Alpha DDL invalid: {name}"))?;
    }
    db.execute_batch(ACTIVE_GAME_INDEX)
        .map_err(|_| "Registered Alpha active-game index invalid")?;
    Ok(db)
}

/// Compare *all* sqlite_schema objects against SQLite's own interpretation of
/// the reviewed server CREATE TABLE / UNIQUE INDEX statements. This also
/// verifies table-level CHECK, UNIQUE, FOREIGN KEY, DEFAULT, named/automatic
/// indexes, partial-index predicates, and rejects views/triggers/extensions.
/// Canonicalization is conservative: unsupported variations fail closed.
/// A positive audit does not prove an operational SQLCipher database runtime.
pub fn audit_registered_alpha_schema_objects(
    inspected_db: &Connection,
    inspection: &SqliteInspection,
) -> Result<AlphaSchemaObjectAudit, String> {
    let reference = known_reference()?;
    let expected = schema_objects(&reference)?;
    let mut report = AlphaSchemaObjectAudit {
        verified: false,
        reason: "alpha_schema_objects_incompatible",
        expected_schema_entry_count: expected.len(),
        matched_schema_entry_count: 0,
        expected_index_count: expected.values().filter(|row| row.kind == "index").count(),
        missing_objects: Vec::new(),
        extra_objects: Vec::new(),
        incompatible_objects: Vec::new(),
        migration_enabled: false,
    };
    if !inspection.integrity_ok || inspection.foreign_key_violations != 0 {
        report.reason = "integrity_or_foreign_keys_unverified";
        return Ok(report);
    }
    if inspection.application_id != 0 || inspection.user_version != 0 {
        report.reason = "not_unversioned_alpha";
        return Ok(report);
    }
    let actual = schema_objects(inspected_db)?;
    for (name, expected_item) in &expected {
        match actual.get(name) {
            Some(item) if item == expected_item => report.matched_schema_entry_count += 1,
            Some(_) => report.incompatible_objects.push(name.clone()),
            None => report.missing_objects.push(name.clone()),
        }
    }
    report.extra_objects = actual
        .keys()
        .filter(|name| !expected.contains_key(*name))
        .cloned()
        .collect();
    if report.missing_objects.is_empty()
        && report.extra_objects.is_empty()
        && report.incompatible_objects.is_empty()
        && report.matched_schema_entry_count == expected.len()
    {
        report.verified = true;
        report.reason = "registered_alpha_schema_objects_verified";
    } else if !report.extra_objects.is_empty() {
        report.reason = "alpha_unregistered_schema_objects";
    } else if !report.missing_objects.is_empty() {
        report.reason = "alpha_required_schema_objects_missing";
    }
    Ok(report)
}

/// Explicit, non-destructive-on-failure addition of operator-selected
/// schema objects from the *registered* reference DDL. The caller supplies
/// an isolated, mutable target copy; never pass the original database here.
/// No SQL text is accepted from the UI or inferred from missing-object names.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SelectedSchemaAdditions {
    pub added_objects: Vec<String>,
    pub still_missing_objects: Vec<String>,
    pub complete_registered_schema: bool,
}

pub fn add_selected_registered_schema_objects(
    target: &mut Connection,
    selected: &[String],
) -> Result<SelectedSchemaAdditions, String> {
    let reference = known_reference()?;
    let expected = schema_objects(&reference)?;
    let current = schema_objects(target)?;
    // Preserve arbitrary SQLite source schemas in the ordinary no-selection
    // migration path. Registered-DDL restrictions apply only to requested
    // changes, never to unchanged legacy copies or unrelated test fixtures.
    if selected.is_empty() {
        return Ok(SelectedSchemaAdditions {
            added_objects: Vec::new(),
            still_missing_objects: expected
                .keys()
                .filter(|name| !current.contains_key(*name))
                .cloned()
                .collect(),
            complete_registered_schema: current == expected,
        });
    }
    // The selected missing registered objects can be added to a legacy
    // database which also has unrelated extension objects; they are preserved.
    let missing: BTreeSet<String> = expected
        .keys()
        .filter(|name| !current.contains_key(*name))
        .cloned()
        .collect();
    let choices: BTreeSet<String> = selected.iter().cloned().collect();
    if choices.len() != selected.len() || !choices.is_subset(&missing) {
        return Err(
            "Schema additions must be distinct, currently missing registered objects".into(),
        );
    }
    for name in &choices {
        let row = expected
            .get(name)
            .ok_or("Selected schema name is not registered")?;
        if row.kind == "index"
            && !choices.contains(&row.table)
            && current.get(&row.table) != expected.get(&row.table)
        {
            return Err("Selected index requires its registered parent table".into());
        }
    }
    // A transaction means a failed UNIQUE index, missing dependency, or
    // invalid DDL cannot leave *part* of a chosen group behind.
    let transaction = target
        .transaction()
        .map_err(|_| "Cannot begin isolated schema additions transaction")?;
    // Explicit tables first: their implicit SQLite autoindexes appear with
    // the table's PRIMARY KEY/UNIQUE constraints. They are never constructed
    // through arbitrary or user-provided SQL.
    for &(name, statement) in REGISTERED_SOURCE_SQL {
        if choices.contains(name) {
            transaction
                .execute_batch(statement)
                .map_err(|_| "Selected schema table cannot be created with existing data")?;
        }
    }
    // Explicit indexes, views and triggers (if registered later) use the
    // independently constructed reference, not any client-provided SQL.
    for name in &choices {
        let row = expected
            .get(name)
            .ok_or("Selected schema object is not registered")?;
        if row.kind == "table" || row.sql.is_none() {
            continue;
        }
        let statement: String = reference
            .query_row(
                "SELECT sql FROM sqlite_schema WHERE name=?1",
                [name.as_str()],
                |r| r.get(0),
            )
            .map_err(|_| "Registered SQL for missing object is unavailable")?;
        transaction
            .execute_batch(&statement)
            .map_err(|_| "Selected schema object cannot be created with existing data")?;
    }
    let after = schema_objects(&transaction)?;
    for (name, row) in &current {
        if after.get(name) != Some(row) {
            return Err("Existing schema object unexpectedly changed".into());
        }
    }
    for (name, row) in &after {
        if current.contains_key(name) {
            continue; // Existing objects must remain byte-for-byte unchanged.
        }
        if expected.get(name) != Some(row) {
            return Err("Unexpected schema object introduced by selected additions".into());
        }
        if !choices.contains(name) {
            // Autoindexes are dependencies generated by an explicitly
            // selected missing table, not standalone user-requested DDL.
            if row.kind != "index" || row.sql.is_some() || !choices.contains(&row.table) {
                return Err("Selected schema addition produced an unapproved dependency".into());
            }
        }
    }
    if choices.iter().any(|name| !after.contains_key(name)) {
        return Err("A selected schema object could not be created independently".into());
    }
    let check: String = transaction
        .query_row("PRAGMA quick_check", [], |r| r.get(0))
        .map_err(|_| "Cannot verify schema additions integrity")?;
    let violations: i64 = transaction
        .query_row("SELECT count(*) FROM pragma_foreign_key_check", [], |r| {
            r.get(0)
        })
        .map_err(|_| "Cannot verify schema additions foreign keys")?;
    if check != "ok" || violations != 0 {
        return Err("Schema additions failed database integrity checks".into());
    }
    let added_objects = after
        .keys()
        .filter(|name| !current.contains_key(*name))
        .cloned()
        .collect();
    let still_missing_objects = expected
        .keys()
        .filter(|name| !after.contains_key(*name))
        .cloned()
        .collect();
    let complete_registered_schema = after == expected;
    transaction
        .commit()
        .map_err(|_| "Cannot commit verified schema additions to isolated copy")?;
    Ok(SelectedSchemaAdditions {
        added_objects,
        still_missing_objects,
        complete_registered_schema,
    })
}

/// Create the exact 27-table registered Alpha fixture for other installer
/// unit-test modules; not shipped as a runtime schema repair API.
#[cfg(test)]
pub(crate) fn create_registered_alpha_test_file(path: &std::path::Path) -> Result<(), String> {
    let db = Connection::open(path).map_err(|_| "Cannot create registered Alpha test fixture")?;
    for &(name, statement) in REGISTERED_SOURCE_SQL {
        db.execute_batch(statement)
            .map_err(|_| format!("Cannot initialize registered Alpha test table: {name}"))?;
    }
    db.execute_batch(ACTIVE_GAME_INDEX)
        .map_err(|_| "Cannot initialize registered Alpha test index")?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sqlite_inspection::{InspectedTable, SchemaObject};

    fn inspect(db: &Connection) -> SqliteInspection {
        let schema = schema_objects(db).unwrap();
        SqliteInspection {
            application_id: 0,
            user_version: 0,
            source_encrypted: false,
            tables: schema
                .values()
                .filter(|item| item.kind == "table" && !item.name.starts_with("sqlite_"))
                .map(|item| InspectedTable {
                    name: item.name.clone(),
                    columns: Vec::new(),
                    create_sql: item.sql.clone(),
                })
                .collect(),
            schema_objects: schema
                .values()
                .filter(|item| item.kind != "table")
                .map(|item| SchemaObject {
                    object_type: item.kind.clone(),
                    name: item.name.clone(),
                    table_name: item.table.clone(),
                    create_sql: item.sql.clone(),
                })
                .collect(),
            integrity_ok: true,
            foreign_key_violations: 0,
        }
    }

    #[test]
    fn recognizes_complete_registered_schema_with_constraints_indexes_and_fk() {
        let db = known_reference().unwrap();
        let report = audit_registered_alpha_schema_objects(&db, &inspect(&db)).unwrap();
        assert!(report.verified);
        assert_eq!(REGISTERED_SOURCE_SQL.len(), 27);
        assert_eq!(
            report.expected_schema_entry_count,
            report.matched_schema_entry_count
        );
        assert!(report.expected_index_count >= 27);
        assert_eq!(report.reason, "registered_alpha_schema_objects_verified");
        assert!(!report.migration_enabled);
    }

    #[test]
    fn rejects_missing_or_changed_unique_partial_index() {
        let db = known_reference().unwrap();
        db.execute_batch("DROP INDEX uq_game_install_one_active_project")
            .unwrap();
        let report = audit_registered_alpha_schema_objects(&db, &inspect(&db)).unwrap();
        assert!(!report.verified);
        assert!(report
            .missing_objects
            .contains(&"uq_game_install_one_active_project".to_owned()));
        assert_eq!(report.reason, "alpha_required_schema_objects_missing");
        assert!(!report.migration_enabled);
        db.execute_batch(
            "CREATE UNIQUE INDEX uq_game_install_one_active_project ON sec01_game_install_journal(host_id,project_id) WHERE state IN ('cancelled','committed','rolled_back')"
        ).unwrap();
        let report = audit_registered_alpha_schema_objects(&db, &inspect(&db)).unwrap();
        assert!(!report.verified);
        assert!(report
            .incompatible_objects
            .contains(&"uq_game_install_one_active_project".to_owned()));
    }

    #[test]
    fn missing_registered_index_is_added_without_rejecting_existing_extensions() {
        let mut db = known_reference().unwrap();
        db.execute_batch(
            "DROP INDEX uq_game_install_one_active_project;
             CREATE TABLE extension_data(note TEXT);
             INSERT INTO extension_data VALUES('preserved');",
        )
        .unwrap();
        let selected = vec!["uq_game_install_one_active_project".to_owned()];
        let result = add_selected_registered_schema_objects(&mut db, &selected).unwrap();
        assert_eq!(result.added_objects, selected);
        assert_eq!(
            db.query_row("SELECT note FROM extension_data", [], |row| row
                .get::<_, String>(0))
                .unwrap(),
            "preserved"
        );
        assert!(db
            .query_row(
                "SELECT name FROM sqlite_schema WHERE name='uq_game_install_one_active_project'",
                [],
                |row| row.get::<_, String>(0)
            )
            .is_ok());
    }

    #[test]
    fn missing_active_game_index_with_duplicate_active_operations_is_not_repairable() {
        let db = known_reference().unwrap();
        db.execute_batch("DROP INDEX uq_game_install_one_active_project;")
            .unwrap();
        db.execute_batch(
            "INSERT INTO sec01_game_install_journal
             (operation_id,host_id,owner_id,project_id,state,plan_sha256)
             VALUES
             ('op-first','host-one','owner-one','game-one','prepared','digest-one'),
             ('op-second','host-one','owner-one','game-one','prepared','digest-two');",
        )
        .unwrap();
        let report = audit_registered_alpha_schema_objects(&db, &inspect(&db)).unwrap();
        assert!(!report.verified);
        assert!(!report.migration_enabled);
        assert_eq!(report.reason, "alpha_required_schema_objects_missing");
        assert_eq!(
            report.missing_objects,
            vec!["uq_game_install_one_active_project".to_owned()]
        );
        assert!(report.extra_objects.is_empty());
        assert!(report.incompatible_objects.is_empty());
    }

    #[test]
    fn terminal_journal_entries_do_not_count_as_active_index_conflicts() {
        let db = known_reference().unwrap();
        db.execute_batch("DROP INDEX uq_game_install_one_active_project;")
            .unwrap();
        db.execute_batch(
            "INSERT INTO sec01_game_install_journal
             (operation_id,host_id,owner_id,project_id,state,plan_sha256)
             VALUES
             ('op-first','host-one','owner-one','game-one','prepared','digest-one'),
             ('op-second','host-one','owner-one','game-one','committed','digest-two');",
        )
        .unwrap();
        let report = audit_registered_alpha_schema_objects(&db, &inspect(&db)).unwrap();
        assert_eq!(report.reason, "alpha_required_schema_objects_missing");
        assert!(!report.verified);
        assert!(!report.migration_enabled);
    }

    #[test]
    fn selected_missing_index_can_be_added_on_isolated_copy_without_special_cases() {
        let mut db = known_reference().unwrap();
        db.execute_batch("DROP INDEX uq_game_install_one_active_project;")
            .unwrap();
        let original = audit_registered_alpha_schema_objects(&db, &inspect(&db)).unwrap();
        assert!(!original.verified);
        assert_eq!(
            original.missing_objects,
            ["uq_game_install_one_active_project"]
        );
        let outcome = add_selected_registered_schema_objects(
            &mut db,
            &["uq_game_install_one_active_project".to_owned()],
        )
        .unwrap();
        assert_eq!(
            outcome.added_objects,
            ["uq_game_install_one_active_project"]
        );
        assert!(outcome.still_missing_objects.is_empty());
        assert!(outcome.complete_registered_schema);
        assert!(
            audit_registered_alpha_schema_objects(&db, &inspect(&db))
                .unwrap()
                .verified
        );
    }

    #[test]
    fn selected_missing_table_creates_required_implicit_indexes_and_supports_subset_choice() {
        let mut db = known_reference().unwrap();
        db.execute_batch("DROP TABLE alpha_users; DROP INDEX uq_game_install_one_active_project;")
            .unwrap();
        let skipped = add_selected_registered_schema_objects(&mut db, &[]).unwrap();
        assert!(skipped.added_objects.is_empty());
        assert!(!skipped.complete_registered_schema);
        let selected =
            add_selected_registered_schema_objects(&mut db, &["alpha_users".to_owned()]).unwrap();
        assert!(selected.added_objects.contains(&"alpha_users".to_owned()));
        assert!(selected
            .added_objects
            .contains(&"sqlite_autoindex_alpha_users_1".to_owned()));
        assert_eq!(
            selected.still_missing_objects,
            ["uq_game_install_one_active_project"]
        );
        assert!(!selected.complete_registered_schema);
        assert!(
            !audit_registered_alpha_schema_objects(&db, &inspect(&db))
                .unwrap()
                .verified
        );
    }

    #[test]
    fn adding_a_unique_index_with_conflicting_rows_rolls_back_all_selected_objects() {
        let mut db = known_reference().unwrap();
        db.execute_batch(
            "DROP TABLE alpha_users;
             DROP INDEX uq_game_install_one_active_project;
             INSERT INTO sec01_game_install_journal
             (operation_id,host_id,owner_id,project_id,state,plan_sha256)
             VALUES
             ('op-first','host-one','owner-one','game-one','prepared','digest-one'),
             ('op-second','host-one','owner-one','game-one','prepared','digest-two');",
        )
        .unwrap();
        assert!(add_selected_registered_schema_objects(
            &mut db,
            &[
                "alpha_users".to_owned(),
                "uq_game_install_one_active_project".to_owned()
            ],
        )
        .is_err());
        let report = audit_registered_alpha_schema_objects(&db, &inspect(&db)).unwrap();
        assert!(!report.verified);
        assert!(report.missing_objects.contains(&"alpha_users".to_owned()));
        assert!(report
            .missing_objects
            .contains(&"uq_game_install_one_active_project".to_owned()));
        assert!(!schema_objects(&db).unwrap().contains_key("alpha_users"));
    }

    #[test]
    fn unknown_duplicate_or_already_present_schema_selections_are_rejected() {
        let mut db = known_reference().unwrap();
        db.execute_batch("DROP INDEX uq_game_install_one_active_project;")
            .unwrap();
        for selection in [
            vec!["some_nonexistent_index".to_owned()],
            vec!["alpha_users".to_owned()],
            vec!["uq_game_install_one_active_project".to_owned(); 2],
        ] {
            assert!(add_selected_registered_schema_objects(&mut db, &selection).is_err());
        }
        assert!(!schema_objects(&db)
            .unwrap()
            .contains_key("uq_game_install_one_active_project"));
    }

    #[test]
    fn rejects_added_trigger_view_index_and_preserves_all_source_objects() {
        let db = known_reference().unwrap();
        db.execute_batch(
            "CREATE VIEW extra_view AS SELECT * FROM alpha_users;
             CREATE TRIGGER extra_trigger AFTER UPDATE ON alpha_users BEGIN SELECT 1; END;
             CREATE INDEX rogue_index ON sec01_host_rules(priority);",
        )
        .unwrap();
        let report = audit_registered_alpha_schema_objects(&db, &inspect(&db)).unwrap();
        assert!(!report.verified);
        for name in ["extra_view", "extra_trigger", "rogue_index"] {
            assert!(report.extra_objects.contains(&name.to_owned()));
        }
        assert!(!report.migration_enabled);
    }

    fn with_replaced_ddl(table_name: &str, replacement: &str) -> Connection {
        let db = Connection::open_in_memory().unwrap();
        for &(name, sql) in REGISTERED_SOURCE_SQL {
            let sql = if name == table_name { replacement } else { sql };
            db.execute_batch(sql).unwrap();
        }
        db.execute_batch(ACTIVE_GAME_INDEX).unwrap();
        db
    }

    #[test]
    fn rejects_missing_unique_check_fk_and_modified_default_even_with_same_columns() {
        for (table, replacement) in [
            (
                "alpha_invites",
                r#"CREATE TABLE IF NOT EXISTS alpha_invites(
                invitation_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                expires_at INTEGER NOT NULL, redeemed INTEGER NOT NULL DEFAULT 0,
                revoked INTEGER NOT NULL DEFAULT 0)"#,
            ),
            (
                "alpha_executor_hosts",
                r#"CREATE TABLE IF NOT EXISTS alpha_executor_hosts(
                host_id TEXT PRIMARY KEY, operator_id TEXT NOT NULL,
                active INTEGER NOT NULL)"#,
            ),
            (
                "alpha_game_installation_evidence",
                r#"CREATE TABLE IF NOT EXISTS alpha_game_installation_evidence(
                host_id TEXT NOT NULL, project_id TEXT NOT NULL,
                integration_id TEXT NOT NULL, installer_run_id TEXT NOT NULL,
                evidence_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
                PRIMARY KEY(host_id,project_id,integration_id,installer_run_id))"#,
            ),
            (
                "alpha_users",
                r#"CREATE TABLE IF NOT EXISTS alpha_users(
                user_id TEXT PRIMARY KEY, disabled INTEGER NOT NULL DEFAULT 1)"#,
            ),
        ] {
            let db = with_replaced_ddl(table, replacement);
            let audit = audit_registered_alpha_schema_objects(&db, &inspect(&db)).unwrap();
            assert!(!audit.verified, "{table}");
            assert!(
                audit.incompatible_objects.contains(&table.to_owned()),
                "{table}"
            );
        }
    }

    #[test]
    fn allows_sqlite_identifier_quotes_after_supported_legacy_column_rename() {
        let db = known_reference().unwrap();
        db.execute_batch(
            "ALTER TABLE alpha_game_projects RENAME COLUMN job_attachments_root TO staging_root;
             ALTER TABLE alpha_game_projects RENAME COLUMN staging_root TO job_attachments_root;",
        )
        .unwrap();
        let report = audit_registered_alpha_schema_objects(&db, &inspect(&db)).unwrap();
        assert!(report.verified, "{report:?}");
    }

    #[test]
    fn does_not_promote_unknown_headers_or_bad_integrity() {
        let db = known_reference().unwrap();
        let mut inspected = inspect(&db);
        inspected.application_id = 12345;
        assert_eq!(
            audit_registered_alpha_schema_objects(&db, &inspected)
                .unwrap()
                .reason,
            "not_unversioned_alpha"
        );
        inspected.application_id = 0;
        inspected.foreign_key_violations = 1;
        assert!(
            !audit_registered_alpha_schema_objects(&db, &inspected)
                .unwrap()
                .verified
        );
    }
}
