//! Allowlisted, bounded read-only view of existing host-policy and game tables.
use minglefield_installer_core::sqlite_inspection::{open_inspected_snapshot, InspectedTable};
use rusqlite::{Connection, Row};
use serde::Serialize;
use std::path::Path;

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentRecord {
    agent_id: String,
    user_id: String,
    disabled: bool,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HostRecord {
    host_id: String,
    owner_id: String,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GitProfileRecord {
    host_id: String,
    profile_id: String,
    owner_id: String,
    label: String,
    auth_method: String,
    git_executable: String,
    author_name: String,
    author_email: String,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HostRuntimeRecord {
    host_id: String,
    runtime_id: String,
    runtime_type: String,
    endpoint: String,
    enabled: bool,
    input_folder: String,
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
    job_attachments_root: String,
    output_root: String,
    settings_revision: i64,
}
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyRecordReview {
    agents: Vec<AgentRecord>,
    hosts: Vec<HostRecord>,
    host_runtimes: Vec<HostRuntimeRecord>,
    git_profiles: Vec<GitProfileRecord>,
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
        agents: vec![],
        hosts: vec![],
        host_runtimes: vec![],
        git_profiles: vec![],
        effects: vec![],
        host_jobs: vec![],
        games: vec![],
        unavailable: vec![],
    };
    if present(
        &schema.tables,
        "alpha_agents",
        &["agent_id", "user_id", "disabled"],
        &mut result.unavailable,
    )? {
        result.agents = read(
            &db,
            "SELECT agent_id,user_id,disabled FROM alpha_agents ORDER BY agent_id LIMIT 501",
            |row| {
                let value: i64 = row.get(2)?;
                if value != 0 && value != 1 {
                    return Err(rusqlite::Error::InvalidQuery);
                }
                Ok(AgentRecord {
                    agent_id: bounded(row, 0, 128)?,
                    user_id: bounded(row, 1, 128)?,
                    disabled: value == 1,
                })
            },
        )?;
    }
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
        "sec01_host_runtimes",
        &["host_id", "runtime_id", "config"],
        &mut result.unavailable,
    )? {
        result.host_runtimes = read(&db,
            "SELECT host_id,runtime_id,json_extract(config,'$.type'),json_extract(config,'$.endpoint'),json_extract(config,'$.enabled'),coalesce(json_extract(config,'$.input_folder'),'') FROM sec01_host_runtimes ORDER BY host_id,runtime_id LIMIT 501",
            |r| {
                let enabled: i64 = r.get(4)?;
                if enabled != 0 && enabled != 1 {
                    return Err(rusqlite::Error::InvalidQuery);
                }
                Ok(HostRuntimeRecord {
                    host_id: bounded(r,0,128)?,
                    runtime_id: bounded(r,1,128)?,
                    runtime_type: bounded(r,2,32)?,
                    endpoint: bounded(r,3,256)?,
                    enabled: enabled == 1,
                    input_folder: bounded(r,5,512)?,
                })
            }
        )?;
    }
    if present(
        &schema.tables,
        "alpha_git_profiles",
        &["host_id", "profile_id", "owner_id", "label", "auth_method", "git_executable", "author_name", "author_email"],
        &mut result.unavailable,
    )? {
        result.git_profiles = read(
            &db,
            "SELECT host_id,profile_id,owner_id,label,auth_method,git_executable,author_name,author_email FROM alpha_git_profiles ORDER BY host_id,profile_id LIMIT 501",
            |r| Ok(GitProfileRecord {
                host_id: bounded(r, 0, 128)?,
                profile_id: bounded(r, 1, 128)?,
                owner_id: bounded(r, 2, 128)?,
                label: bounded(r, 3, 120)?,
                auth_method: bounded(r, 4, 32)?,
                git_executable: bounded(r, 5, 256)?,
                author_name: bounded(r, 6, 256)?,
                author_email: bounded(r, 7, 256)?,
            }),
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
            "job_attachments_root",
            "output_root",
            "settings_revision",
        ],
        &mut result.unavailable,
    )? {
        result.games = read(&db, "SELECT project_id,host_id,owner_id,name,repository_root,job_attachments_root,output_root,settings_revision FROM alpha_game_projects ORDER BY project_id LIMIT 501", |r| Ok(GameRecord {
            project_id: bounded(r,0,128)?, host_id: bounded(r,1,128)?, owner_id: bounded(r,2,128)?,
            name: bounded(r,3,120)?, repository_root: bounded(r,4,1024)?,
            job_attachments_root: bounded(r,5,1024)?,
            output_root: bounded(r,6,1024)?,
            settings_revision: r.get(7)?,
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
        assert_eq!(inspect(&path, "").unwrap().unavailable.len(), 7);
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
                r#"CREATE TABLE alpha_agents(agent_id TEXT,user_id TEXT,disabled INTEGER);
                 INSERT INTO alpha_agents VALUES('agent1','alice',0);
                 CREATE TABLE sec01_host_owners(host_id TEXT,owner_id TEXT);
                 INSERT INTO sec01_host_owners VALUES('h1','alice');
                 CREATE TABLE alpha_git_profiles(host_id TEXT,profile_id TEXT,owner_id TEXT,label TEXT,auth_method TEXT,git_executable TEXT,author_name TEXT,author_email TEXT);
                 INSERT INTO alpha_git_profiles VALUES('h1','git1','alice','Main Git','local','git','Alice','alice@example.test');
                 CREATE TABLE sec01_host_runtimes(host_id TEXT,runtime_id TEXT,config TEXT);
                 INSERT INTO sec01_host_runtimes VALUES('h1','comfy1','{"type":"comfyui","endpoint":"http://127.0.0.1:8188","enabled":true,"input_folder":"/comfy/input"}');
                 CREATE TABLE sec01_host_effect_definitions(host_id TEXT,effect_id TEXT,description TEXT,enabled INTEGER);
                 INSERT INTO sec01_host_effect_definitions VALUES('h1','e1','Workflow',0);
                 CREATE TABLE sec01_host_jobs(job_id TEXT,host_id TEXT,effect_id TEXT,requested_by TEXT,state TEXT);
                 INSERT INTO sec01_host_jobs VALUES('j1','h1','e1','alice','queued');
                 CREATE TABLE alpha_game_projects(project_id TEXT,host_id TEXT,owner_id TEXT,name TEXT,repository_root TEXT,job_attachments_root TEXT,output_root TEXT,settings_revision INTEGER);
                 INSERT INTO alpha_game_projects VALUES('g1','h1','alice','Demo','/games/demo','/games/attachments','/games/output',1);
                 CREATE TABLE alpha_passwords(user_id TEXT,password_hash BLOB);
                 INSERT INTO alpha_passwords VALUES('alice',x'1234');"#,
            )
            .unwrap();
        }
        let original_bytes = std::fs::read(&path).unwrap();
        let reviewed = inspect(&path, "").unwrap();
        assert_eq!(reviewed.agents[0].agent_id, "agent1");
        assert!(!reviewed.agents[0].disabled);
        assert_eq!(reviewed.hosts[0].owner_id, "alice");
        assert_eq!(reviewed.git_profiles[0].label, "Main Git");
        assert_eq!(reviewed.git_profiles[0].author_email, "alice@example.test");
        assert_eq!(reviewed.host_runtimes[0].runtime_type, "comfyui");
        assert!(reviewed.host_runtimes[0].enabled);
        assert_eq!(reviewed.effects[0].description, "Workflow");
        assert!(!reviewed.effects[0].enabled);
        assert_eq!(reviewed.host_jobs[0].state, "queued");
        assert_eq!(reviewed.games[0].name, "Demo");
        assert!(reviewed.unavailable.is_empty());
        assert_eq!(std::fs::read(&path).unwrap(), original_bytes);
        std::fs::remove_file(path).unwrap();
    }
}
