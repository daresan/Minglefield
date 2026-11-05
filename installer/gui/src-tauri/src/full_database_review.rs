//! Complete typed, read-only SQLite record inventory for an offline migration preview.
//! Source data is read from a consistent verified memory snapshot only.
use minglefield_installer_core::sqlite_inspection::open_inspected_snapshot;
use rusqlite::{types::Value, Connection};
use serde::Serialize;
use std::path::Path;

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DatabaseRow {
    row_id: Option<String>,
    cells: Vec<super::migration_review::FullCellValue>,
}

#[derive(Debug, Serialize)]
pub struct DatabaseTable {
    name: String,
    columns: Vec<String>,
    rows: Vec<DatabaseRow>,
}

#[derive(Debug, Serialize)]
pub struct FullDatabaseReview {
    tables: Vec<DatabaseTable>,
}

fn quote(name: &str) -> String {
    format!("\"{}\"", name.replace('"', "\"\""))
}

fn wire(value: Value) -> super::migration_review::FullCellValue {
    use super::migration_review::FullCellValue;
    match value {
        Value::Null => FullCellValue {
            kind: "null".to_owned(),
            value: None,
        },
        Value::Integer(n) => FullCellValue {
            kind: "integer".to_owned(),
            value: Some(n.to_string()),
        },
        Value::Real(n) => FullCellValue {
            kind: "real".to_owned(),
            value: Some(n.to_string()),
        },
        Value::Text(s) => FullCellValue {
            kind: "text".to_owned(),
            value: Some(s),
        },
        Value::Blob(bytes) => {
            let hex = bytes.iter().map(|b| format!("{b:02x}")).collect::<String>();
            FullCellValue {
                kind: "blob".to_owned(),
                value: Some(hex),
            }
        }
    }
}

fn inspect(path: &Path, password: &str) -> Result<FullDatabaseReview, String> {
    let (db, schema) = open_inspected_snapshot(path, password)
        .map_err(|_| "Cannot inspect selected SQLite database")?;
    if !schema.integrity_ok || schema.foreign_key_violations != 0 {
        return Err("Invalid source database integrity or foreign keys".to_owned());
    }
    let mut tables = Vec::new();
    let mut total_bytes = 0usize;
    for entry in schema.tables {
        if entry.columns.is_empty() || entry.columns.len() > 1024 {
            return Err("Unsupported source table layout".to_owned());
        }
        let quoted = entry
            .columns
            .iter()
            .map(|col| quote(col))
            .collect::<Vec<_>>();
        let projection = quoted.join(",");
        let with_id = format!("SELECT rowid,{projection} FROM {}", quote(&entry.name));
        let without_id = format!("SELECT {projection} FROM {}", quote(&entry.name));
        let (sql, has_rowid) = if db.prepare(&with_id).is_ok() {
            (with_id, true)
        } else {
            (without_id, false)
        };
        let rows = load_rows(&db, &sql, entry.columns.len(), has_rowid, &mut total_bytes)?;
        tables.push(DatabaseTable {
            name: entry.name,
            columns: entry.columns,
            rows,
        });
    }
    Ok(FullDatabaseReview { tables })
}

fn load_rows(
    db: &Connection,
    sql: &str,
    column_count: usize,
    has_rowid: bool,
    total_bytes: &mut usize,
) -> Result<Vec<DatabaseRow>, String> {
    let mut stmt = db.prepare(sql).map_err(|_| "Cannot read source table")?;
    let mut rows = stmt.query([]).map_err(|_| "Cannot query source table")?;
    let mut result = Vec::new();
    while let Some(row) = rows.next().map_err(|_| "Cannot decode source record")? {
        if result.len() >= 5000 {
            return Err(
                "Source table has more than 5000 rows; paged review is required".to_owned(),
            );
        }
        let row_id = if has_rowid {
            Some(
                row.get::<_, i64>(0)
                    .map_err(|_| "Cannot read source rowid")?
                    .to_string(),
            )
        } else {
            None
        };
        let offset = usize::from(has_rowid);
        let mut cells = Vec::new();
        for index in 0..column_count {
            let value: Value = row
                .get(index + offset)
                .map_err(|_| "Cannot decode source SQLite value")?;
            let cell = wire(value);
            *total_bytes = total_bytes.saturating_add(cell.value.as_ref().map_or(0, String::len));
            if *total_bytes > 32 * 1024 * 1024 {
                return Err(
                    "Full database review exceeds 32 MiB; paged review is required".to_owned(),
                );
            }
            cells.push(cell);
        }
        result.push(DatabaseRow { row_id, cells });
    }
    Ok(result)
}

#[tauri::command]
pub async fn inspect_full_database(
    path: String,
    password: String,
) -> Result<FullDatabaseReview, String> {
    tauri::async_runtime::spawn_blocking(move || inspect(Path::new(&path), &password))
        .await
        .map_err(|_| "Full SQLite inventory worker failed".to_owned())?
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn includes_comfy_and_host_rules_with_typed_values() {
        let path = std::env::temp_dir().join(format!(
            "minglefield-full-review-{}.sqlite3",
            std::process::id()
        ));
        {
            let db = Connection::open(&path).unwrap();
            db.execute_batch(
                r#"CREATE TABLE sec01_host_rules(host_id TEXT,rule_id TEXT,config TEXT);
                INSERT INTO sec01_host_rules VALUES('h','rule','{"limit":5}');
                CREATE TABLE sec01_host_comfy_workflows(host_id TEXT,workflow_id TEXT,definition BLOB);
                INSERT INTO sec01_host_comfy_workflows VALUES('h','workflow',x'00ff');
                CREATE TABLE no_rowid(k TEXT PRIMARY KEY, note TEXT) WITHOUT ROWID;
                INSERT INTO no_rowid VALUES('key','text');"#
            ).unwrap();
        }
        let review = inspect(&path, "").unwrap();
        assert_eq!(review.tables.len(), 3);
        let wf = review
            .tables
            .iter()
            .find(|t| t.name == "sec01_host_comfy_workflows")
            .unwrap();
        assert_eq!(wf.rows[0].cells[2].value.as_deref(), Some("00ff"));
        let rules = review
            .tables
            .iter()
            .find(|t| t.name == "sec01_host_rules")
            .unwrap();
        assert_eq!(
            rules.rows[0].cells[2].value.as_deref(),
            Some(r#"{"limit":5}"#)
        );
        let no_id = review.tables.iter().find(|t| t.name == "no_rowid").unwrap();
        assert_eq!(no_id.rows[0].row_id, None);
        drop(review);
        std::fs::remove_file(path).unwrap();
    }
}
