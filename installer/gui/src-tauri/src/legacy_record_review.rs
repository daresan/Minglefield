//! Allowlisted, bounded read-only view of existing host-policy and game tables.
use minglefield_installer_core::sqlite_inspection::{open_inspected_snapshot, InspectedTable};
use rusqlite::{Connection, Row};
use serde::Serialize;
use std::path::Path;

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HostRecord {
    host_id: String,
    owner_id: String,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EffectRecord {
    host_id: String,
    effect_id: String,
    description: String,
    enabled: bool,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HostJobRecord {
    job_id: String,
    host_id: String,
    effect_id: String,
    requested_by: String,
    state: String,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GameRecord {
    project_id: String,
    host_id: String,
    owner_id: String,
    name: String,
    repository_root: String,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyRecordReview {
    hosts: Vec<HostRecord>,
    effects: Vec<EffectRecord>,
    host_jobs: Vec<HostJobRecord>,
    games: Vec<GameRecord>,
    unavailable: Vec<String>,
}

fn present(
    tables: &[InspectedTable],
    name: &str,
    columns: &[&str],
    missing: &mut Vec<String>,
) -> Result<bool, String> {
    let Some(table) = tables.iter().find(|t| t.name == name) else {
        missing.push(format!("{name}: not present"));
        return Ok(false);
    };
    if columns
        .iter()
        .any(|col| !table.columns.iter().any(|existing| existing == col))
    {
        return Err(format!("{name}: incompatible schema"));
    }
    Ok(true)
}
fn bounded(row: &Row<'_>, column: usize, limit: usize) -> rusqlite::Result<String> {
    let text: String = row.get(column)?;
    if text.len() > limit {
        return Err(rusqlite::Error::InvalidQuery);
    }
    Ok(text)
}
fn read<T, F>(db: &Connection, sql: &str, mut map: F) -> Result<Vec<T>, String>
where
    F: FnMut(&Row<'_>) -> rusqlite::Result<T>,
{
    let mut stmt = db
        .prepare(sql)
        .map_err(|_| "Cannot read application records")?;
    let rows = stmt
        .query_map([], |row| map(row))
        .map_err(|_| "Cannot query application records")?
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|_| "Invalid application record values")?;
    if rows.len() > 500 {
        return Err("More than 500 records: pagination required".to_owned());
    }
    Ok(rows)
}

fn inspect(path: &Path, password: &str) -> Result<LegacyRecordReview, String> {
    let (db, schema) = open_inspected_snapshot(path, password)
        .map_err(|error| format!("Database inspection rejected: {error:?}"))?;
    if !schema.integrity_ok || schema.foreign_key_violations != 0 {
        return Err("Database integrity validation failed".to_owned());
    }
    let mut result = LegacyRecordReview {
        hosts: vec![],
        effects: vec![],
        host_jobs: vec![],
        games: vec![],
        unavailable: vec![],
    };
    if present(
        &schema.tables,
        "sec01_host_owners",
        &["host_id", "owner_id"],
        &mut result.unavailable,
    )? {
        result.hosts = read(
            &db,
            "SELECT host_id,owner_id FROM sec01_host_owners ORDER BY host_id LIMIT 501",
            |r| {
                Ok(HostRecord {
                    host_id: bounded(r, 0, 128)?,
                    owner_id: bounded(r, 1, 128)?,
                })
            },
        )?;
    }
    if present(
        &schema.tables,
        "sec01_host_effect_definitions",
        &["host_id", "effect_id", "description", "enabled"],
        &mut result.unavailable,
    )? {
        result.effects = read(&db, "SELECT host_id,effect_id,description,enabled FROM sec01_host_effect_definitions ORDER BY host_id,effect_id LIMIT 501", |r| {
            let enabled: i64 = r.get(3)?;
            if enabled != 0 && enabled != 1 { return Err(rusqlite::Error::InvalidQuery); }
            Ok(EffectRecord {
                host_id: bounded(r,0,128)?, effect_id: bounded(r,1,128)?,
                description: bounded(r,2,256)?, enabled: enabled == 1,
            })
        })?;
    }
    if present(
        &schema.tables,
        "sec01_host_jobs",
        &["job_id", "host_id", "effect_id", "requested_by", "state"],
        &mut result.unavailable,
    )? {
        result.host_jobs = read(&db, "SELECT job_id,host_id,effect_id,requested_by,state FROM sec01_host_jobs ORDER BY job_id LIMIT 501", |r| Ok(HostJobRecord {
            job_id: bounded(r,0,128)?, host_id: bounded(r,1,128)?, effect_id: bounded(r,2,128)?,
            requested_by: bounded(r,3,128)?, state: bounded(r,4,128)?,
        }))?;
    }
    if present(
        &schema.tables,
        "alpha_game_projects",
        &[
            "project_id",
            "host_id",
            "owner_id",
            "name",
            "repository_root",
        ],
        &mut result.unavailable,
    )? {
        result.games = read(&db, "SELECT project_id,host_id,owner_id,name,repository_root FROM alpha_game_projects ORDER BY project_id LIMIT 501", |r| Ok(GameRecord {
            project_id: bounded(r,0,128)?, host_id: bounded(r,1,128)?, owner_id: bounded(r,2,128)?,
            name: bounded(r,3,120)?, repository_root: bounded(r,4,1024)?,
        }))?;
    }
    Ok(result)
}

#[tauri::command]
pub async fn inspect_legacy_records(
    path: String,
    password: String,
) -> Result<LegacyRecordReview, String> {
    tauri::async_runtime::spawn_blocking(move || inspect(Path::new(&path), &password))
        .await
        .map_err(|_| "Application record inspection task failed".to_owned())?
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn inspect_reports_missing_tables_and_rejects_incompatible_schema() {
        let path = std::env::temp_dir().join(format!(
            "minglefield-review-schema-{}.sqlite3",
            std::process::id()
        ));
        {
            let db = Connection::open(&path).unwrap();
            db.execute_batch("CREATE TABLE alpha_users(user_id TEXT PRIMARY KEY);")
                .unwrap();
        }
        assert_eq!(inspect(&path, "").unwrap().unavailable.len(), 4);
        {
            let db = Connection::open(&path).unwrap();
            db.execute_batch("CREATE TABLE sec01_host_owners(host_id TEXT);")
                .unwrap();
        }
        assert!(inspect(&path, "")
            .unwrap_err()
            .contains("incompatible schema"));
        std::fs::remove_file(path).unwrap();
    }
    #[test]
    fn reads_records_without_exposing_passwords_or_mutating_source() {
        let path = std::env::temp_dir().join(format!(
            "minglefield-review-values-{}.sqlite3",
            std::process::id()
        ));
        {
            let db = Connection::open(&path).unwrap();
            db.execute_batch(
                "CREATE TABLE sec01_host_owners(host_id TEXT,owner_id TEXT);
                 INSERT INTO sec01_host_owners VALUES('h1','alice');
                 CREATE TABLE sec01_host_effect_definitions(host_id TEXT,effect_id TEXT,description TEXT,enabled INTEGER);
                 INSERT INTO sec01_host_effect_definitions VALUES('h1','e1','Workflow',0);
                 CREATE TABLE sec01_host_jobs(job_id TEXT,host_id TEXT,effect_id TEXT,requested_by TEXT,state TEXT);
                 INSERT INTO sec01_host_jobs VALUES('j1','h1','e1','alice','queued');
                 CREATE TABLE alpha_game_projects(project_id TEXT,host_id TEXT,owner_id TEXT,name TEXT,repository_root TEXT);
                 INSERT INTO alpha_game_projects VALUES('g1','h1','alice','Demo','/games/demo');
                 CREATE TABLE alpha_passwords(user_id TEXT,password_hash BLOB);
                 INSERT INTO alpha_passwords VALUES('alice',x'1234');",
            )
            .unwrap();
        }
        let original_bytes = std::fs::read(&path).unwrap();
        let reviewed = inspect(&path, "").unwrap();
        assert_eq!(reviewed.hosts[0].owner_id, "alice");
        assert_eq!(reviewed.effects[0].description, "Workflow");
        assert!(!reviewed.effects[0].enabled);
        assert_eq!(reviewed.host_jobs[0].state, "queued");
        assert_eq!(reviewed.games[0].name, "Demo");
        assert!(reviewed.unavailable.is_empty());
        assert_eq!(std::fs::read(&path).unwrap(), original_bytes);
        std::fs::remove_file(path).unwrap();
    }
}
