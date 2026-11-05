//! Explicit structural signature for the current *unversioned* local Alpha database.
//! Source of truth: the CREATE TABLE declarations in private_alpha_auth.py,
//! sec01_integrated_alpha_admission.py and sec01_host_commit_policy_sim.py.
//! Identification is read-only and never authorizes installation or publication.
use crate::sqlite_inspection::SqliteInspection;
use rusqlite::Connection;
use std::collections::BTreeSet;

type ColumnContract = (&'static str, &'static str, bool, i64);
pub const REGISTERED_ALPHA: &[(&str, &[ColumnContract])] = &[
    ("alpha_invites", &[
        ("invitation_hash", "TEXT", false, 1),
        ("user_id", "TEXT", true, 0),
        ("expires_at", "INTEGER", true, 0),
        ("redeemed", "INTEGER", true, 0),
        ("revoked", "INTEGER", true, 0),
    ]),
    ("alpha_users", &[
        ("user_id", "TEXT", false, 1),
        ("disabled", "INTEGER", true, 0),
    ]),
    ("alpha_agents", &[
        ("agent_id", "TEXT", false, 1),
        ("user_id", "TEXT", true, 0),
        ("disabled", "INTEGER", true, 0),
    ]),
    ("alpha_sessions", &[
        ("token_hash", "TEXT", false, 1),
        ("user_id", "TEXT", true, 0),
        ("expires_at", "INTEGER", true, 0),
        ("revoked", "INTEGER", true, 0),
    ]),
    ("alpha_jobs", &[
        ("job_id", "TEXT", false, 1),
        ("user_id", "TEXT", true, 0),
        ("agent_id", "TEXT", true, 0),
        ("idempotency_key", "TEXT", true, 0),
        ("action", "TEXT", true, 0),
    ]),
    ("alpha_passwords", &[
        ("user_id", "TEXT", false, 1),
        ("salt", "BLOB", true, 0),
        ("password_hash", "BLOB", true, 0),
    ]),
    ("alpha_agent_grants", &[
        ("agent_id", "TEXT", true, 1),
        ("grantee_user_id", "TEXT", true, 2),
        ("action", "TEXT", true, 3),
        ("revoked", "INTEGER", true, 0),
    ]),
    ("alpha_executor_hosts", &[
        ("host_id", "TEXT", false, 1),
        ("operator_id", "TEXT", true, 0),
        ("active", "INTEGER", true, 0),
    ]),
    ("alpha_agent_host_assignments", &[
        ("agent_id", "TEXT", true, 1),
        ("host_id", "TEXT", true, 2),
        ("enabled", "INTEGER", true, 0),
    ]),
    ("alpha_sec01_admissions", &[
        ("effect_key", "TEXT", false, 1),
        ("binding", "TEXT", true, 0),
    ]),
    ("sec01_host_comfy_workflows", &[
        ("host_id", "TEXT", true, 1),
        ("effect_id", "TEXT", true, 2),
        ("runtime_id", "TEXT", true, 0),
        ("workflow", "TEXT", true, 0),
        ("metadata", "TEXT", true, 0),
    ]),
    ("sec01_host_job_parameters", &[
        ("job_id", "TEXT", false, 1),
        ("host_id", "TEXT", true, 0),
        ("effect_id", "TEXT", true, 0),
        ("workflow_sha256", "TEXT", true, 0),
        ("parameters", "TEXT", true, 0),
    ]),
    ("alpha_git_profiles", &[
        ("host_id", "TEXT", true, 1),
        ("profile_id", "TEXT", true, 2),
        ("owner_id", "TEXT", true, 0),
        ("auth_method", "TEXT", true, 0),
        ("label", "TEXT", true, 0),
        ("git_executable", "TEXT", true, 0),
        ("author_name", "TEXT", true, 0),
        ("author_email", "TEXT", true, 0),
    ]),
    ("alpha_game_installation_evidence", &[
        ("host_id", "TEXT", true, 1),
        ("project_id", "TEXT", true, 2),
        ("integration_id", "TEXT", true, 3),
        ("installer_run_id", "TEXT", true, 4),
        ("evidence_json", "TEXT", true, 0),
        ("recorded_at", "TEXT", true, 0),
    ]),
    ("alpha_game_projects", &[
        ("project_id", "TEXT", false, 1),
        ("host_id", "TEXT", true, 0),
        ("owner_id", "TEXT", true, 0),
        ("name", "TEXT", true, 0),
        ("repository_root", "TEXT", true, 0),
        ("job_attachments_root", "TEXT", true, 0),
        ("output_root", "TEXT", true, 0),
        ("settings_revision", "INTEGER", true, 0),
    ]),
    ("sec01_game_install_journal", &[
        ("operation_id", "TEXT", false, 1),
        ("host_id", "TEXT", true, 0),
        ("owner_id", "TEXT", true, 0),
        ("project_id", "TEXT", true, 0),
        ("state", "TEXT", true, 0),
        ("plan_sha256", "TEXT", true, 0),
        ("created_at", "TEXT", true, 0),
        ("updated_at", "TEXT", true, 0),
    ]),
    ("sec01_host_settings", &[
        ("host_id", "TEXT", false, 1),
        ("settings", "TEXT", true, 0),
    ]),
    ("sec01_host_runtimes", &[
        ("host_id", "TEXT", true, 1),
        ("runtime_id", "TEXT", true, 2),
        ("config", "TEXT", true, 0),
    ]),
    ("sec01_host_owners", &[
        ("host_id", "TEXT", false, 1),
        ("owner_id", "TEXT", true, 0),
    ]),
    ("sec01_host_effect_definitions", &[
        ("host_id", "TEXT", true, 1),
        ("effect_id", "TEXT", true, 2),
        ("description", "TEXT", true, 0),
        ("enabled", "INTEGER", true, 0),
    ]),
    ("sec01_host_jobs", &[
        ("job_id", "TEXT", false, 1),
        ("host_id", "TEXT", true, 0),
        ("effect_id", "TEXT", true, 0),
        ("requested_by", "TEXT", true, 0),
        ("state", "TEXT", true, 0),
        ("created_at", "TEXT", true, 0),
    ]),
    ("sec01_host_admins", &[
        ("host_id", "TEXT", true, 1),
        ("admin_id", "TEXT", true, 2),
    ]),
    ("sec01_host_rules", &[
        ("host_id", "TEXT", true, 1),
        ("rule_id", "TEXT", true, 2),
        ("priority", "INTEGER", true, 0),
        ("enabled", "INTEGER", true, 0),
        ("config", "TEXT", true, 0),
    ]),
    ("sec01_host_approvals", &[
        ("host_id", "TEXT", true, 1),
        ("effect_key", "TEXT", true, 2),
        ("approved_by", "TEXT", true, 0),
    ]),
    ("sec01_host_commits", &[
        ("effect_key", "TEXT", false, 1),
        ("host_id", "TEXT", true, 0),
        ("binding", "TEXT", true, 0),
        ("rule_id", "TEXT", true, 0),
    ]),
    ("sec01_host_active_slots", &[
        ("effect_key", "TEXT", false, 1),
        ("host_id", "TEXT", true, 0),
    ]),
    ("sec01_host_comfy_executions", &[
        ("job_id", "TEXT", false, 1),
        ("host_id", "TEXT", true, 0),
        ("prompt_id", "TEXT", false, 0),
        ("error", "TEXT", false, 0),
    ]),
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LegacyAlphaMapping {
    pub recognized: bool,
    pub reason: &'static str,
    pub matched_table_count: usize,
    pub matched_column_count: usize,
    pub missing_tables: Vec<String>,
    pub incompatible_tables: Vec<String>,
    pub extension_tables: Vec<String>,
    pub migration_enabled: bool,
}

impl LegacyAlphaMapping {
    fn report(reason: &'static str) -> Self {
        Self {
            recognized: false, reason,
            matched_table_count: 0, matched_column_count: 0,
            missing_tables: Vec::new(), incompatible_tables: Vec::new(),
            extension_tables: Vec::new(), migration_enabled: false,
        }
    }
}

/// Checks exact known-table signatures (order, SQLite storage declaration,
/// NOT NULL, primary-key order and absence of hidden/generated fields).
/// Other table data and schema objects are retained by snapshot fidelity;
/// unknown extensions prevent declaring a fully registered layout.
pub fn assess_registered_alpha_mapping(
    db: &Connection, inspection: &SqliteInspection,
) -> Result<LegacyAlphaMapping, String> {
    if !inspection.integrity_ok || inspection.foreign_key_violations != 0 {
        return Ok(LegacyAlphaMapping::report("integrity_or_foreign_keys_unverified"));
    }
    if inspection.application_id != 0 || inspection.user_version != 0 {
        return Ok(LegacyAlphaMapping::report("not_unversioned_alpha"));
    }
    let inventory: BTreeSet<&str> = inspection.tables.iter()
        .map(|item| item.name.as_str()).collect();
    if inventory.len() != inspection.tables.len() {
        return Ok(LegacyAlphaMapping::report("duplicate_table_inventory"));
    }
    let registered: BTreeSet<&str> = REGISTERED_ALPHA.iter().map(|(name, _)| *name).collect();
    if registered.len() != REGISTERED_ALPHA.len() {
        return Err("Conflicting registered Alpha table signatures".to_owned());
    }
    let mut report = LegacyAlphaMapping::report("registered_alpha_schema_incompatible");
    let mut stmt = db.prepare(
        "SELECT name,type,\"notnull\",pk,hidden FROM pragma_table_xinfo(?1) ORDER BY cid"
    ).map_err(|_| "Cannot prepare registered Alpha schema audit")?;
    for &(name, expected) in REGISTERED_ALPHA {
        let Some(inventory_table) = inspection.tables.iter().find(|item| item.name == name) else {
            report.missing_tables.push(name.to_owned());
            continue;
        };
        let actual = stmt.query_map([name], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, i64>(2)? != 0,
                row.get::<_, i64>(3)?,
                row.get::<_, i64>(4)?,
            ))
        }).map_err(|_| "Cannot query registered Alpha columns")?
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|_| "Cannot decode registered Alpha columns")?;
        if actual.len() != expected.len()
           || inventory_table.columns.len() != expected.len()
           || actual.iter().zip(expected.iter()).enumerate().any(|(i, (got, wanted))| {
               got.0 != wanted.0 || got.1.to_ascii_uppercase() != wanted.1
               || got.2 != wanted.2 || got.3 != wanted.3 || got.4 != 0
               || inventory_table.columns[i] != wanted.0
           }) {
            report.incompatible_tables.push(name.to_owned());
        } else {
            report.matched_table_count += 1;
            report.matched_column_count += actual.len();
        }
    }
    report.extension_tables = inventory.difference(&registered)
        .map(|name| (*name).to_owned()).collect();
    if inspection.schema_objects.iter().any(|object| object.object_type == "trigger") {
        report.reason = "alpha_trigger_review_required";
    } else if !report.missing_tables.is_empty() {
        report.reason = "required_alpha_tables_missing";
    } else if !report.incompatible_tables.is_empty() {
        report.reason = "alpha_column_signature_mismatch";
    } else if !report.extension_tables.is_empty() {
        report.reason = "unregistered_extension_tables";
    } else {
        report.recognized = true;
        report.reason = "registered_alpha_column_signatures_verified";
    }
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sqlite_inspection::{InspectedTable, SqliteInspection};

    fn fixture() -> (Connection, SqliteInspection) {
        let db = Connection::open_in_memory().unwrap();
        let mut tables = Vec::new();
        for &(name, cols) in REGISTERED_ALPHA {
            let mut definitions = Vec::new();
            let mut keys = cols.iter().filter(|col| col.3 != 0).collect::<Vec<_>>();
            keys.sort_by_key(|column| column.3);
            for &(column, ty, required, pk) in cols {
                let inline = keys.len() == 1 && pk == 1;
                definitions.push(format!(
                    "\"{column}\" {ty}{}{}",
                    if required { " NOT NULL" } else { "" },
                    if inline { " PRIMARY KEY" } else { "" },
                ));
            }
            if keys.len() > 1 {
                definitions.push(format!(
                    "PRIMARY KEY ({})",
                    keys.iter().map(|column| format!("\"{}\"", column.0))
                        .collect::<Vec<_>>().join(",")
                ));
            }
            let sql = format!("CREATE TABLE \"{name}\" ({})", definitions.join(","));
            db.execute_batch(&sql).unwrap();
            tables.push(InspectedTable {
                name: name.to_owned(),
                columns: cols.iter().map(|column| column.0.to_owned()).collect(),
                create_sql: Some(sql),
            });
        }
        let inspection = SqliteInspection {
            application_id: 0, user_version: 0, source_encrypted: false,
            tables, schema_objects: Vec::new(), integrity_ok: true,
            foreign_key_violations: 0,
        };
        (db, inspection)
    }
    #[test]
    fn matches_all_twenty_seven_registered_tables_and_111_columns() {
        let (db, inspected) = fixture();
        assert_eq!(REGISTERED_ALPHA.len(), 27);
        assert_eq!(REGISTERED_ALPHA.iter().map(|(_,cols)| cols.len()).sum::<usize>(), 111);
        let result = assess_registered_alpha_mapping(&db, &inspected).unwrap();
        assert!(result.recognized);
        assert_eq!(result.matched_table_count, 27);
        assert_eq!(result.matched_column_count, 111);
        assert!(!result.migration_enabled);
        assert!(result.missing_tables.is_empty());
        assert!(result.incompatible_tables.is_empty());
    }

    #[test]
    fn altered_column_type_or_missing_table_does_not_promote_schema() {
        let (db, mut inspected) = fixture();
        db.execute_batch("ALTER TABLE alpha_users ADD COLUMN extra_field TEXT").unwrap();
        assert_eq!(
            assess_registered_alpha_mapping(&db, &inspected).unwrap().reason,
            "alpha_column_signature_mismatch"
        );
        inspected.tables.retain(|item| item.name != "alpha_passwords");
        let outcome = assess_registered_alpha_mapping(&db, &inspected).unwrap();
        assert_eq!(outcome.reason, "required_alpha_tables_missing");
        assert!(!outcome.recognized);
    }

    #[test]
    fn extension_table_and_unregistered_header_never_enable_migration() {
        let (db, mut inspected) = fixture();
        db.execute_batch("CREATE TABLE extension_data (value BLOB)").unwrap();
        inspected.tables.push(InspectedTable {
            name: "extension_data".to_owned(),
            columns: vec!["value".to_owned()], create_sql: None,
        });
        let outcome = assess_registered_alpha_mapping(&db, &inspected).unwrap();
        assert_eq!(outcome.reason, "unregistered_extension_tables");
        assert_eq!(outcome.extension_tables, vec!["extension_data"]);
        assert!(!outcome.migration_enabled);
        inspected.application_id = 42;
        assert_eq!(
            assess_registered_alpha_mapping(&db, &inspected).unwrap().reason,
            "not_unversioned_alpha"
        );
    }
}
