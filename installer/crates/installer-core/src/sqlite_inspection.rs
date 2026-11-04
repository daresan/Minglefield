//! SQLite integrity and schema inspection on a consistent in-memory snapshot.
//! This module never executes migrations or writes schema changes to the source.

use rusqlite::{Connection, DatabaseName, OpenFlags};
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InspectedTable {
    pub name: String,
    pub columns: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SqliteInspection {
    pub application_id: i64,
    pub user_version: i64,
    pub tables: Vec<InspectedTable>,
    pub integrity_ok: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InspectionError {
    NotRegularFile,
    DatabaseError,
    IntegrityFailed,
    TooManyTables,
}

/// Opens the source read-only and backs up a transactionally consistent view
/// to memory. SQLite may manage WAL shared-memory sidecars while reading an
/// active database; no source schema or user data is modified here.
/// The result does not establish that a database belongs to Minglefield.
pub fn inspect_sqlite(path: &Path) -> Result<SqliteInspection, InspectionError> {
    let metadata = std::fs::symlink_metadata(path).map_err(|_| InspectionError::NotRegularFile)?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err(InspectionError::NotRegularFile);
    }
    let source = Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|_| InspectionError::DatabaseError)?;
    let mut snapshot = Connection::open_in_memory().map_err(|_| InspectionError::DatabaseError)?;
    source
        .backup(DatabaseName::Main, &mut snapshot, None)
        .map_err(|_| InspectionError::DatabaseError)?;
    let check: String = snapshot
        .query_row("PRAGMA quick_check", [], |row| row.get(0))
        .map_err(|_| InspectionError::DatabaseError)?;
    if check != "ok" {
        return Err(InspectionError::IntegrityFailed);
    }
    let application_id = snapshot
        .query_row("PRAGMA application_id", [], |row| row.get(0))
        .map_err(|_| InspectionError::DatabaseError)?;
    let user_version = snapshot
        .query_row("PRAGMA user_version", [], |row| row.get(0))
        .map_err(|_| InspectionError::DatabaseError)?;
    let mut table_stmt = snapshot
        .prepare(
            "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
        )
        .map_err(|_| InspectionError::DatabaseError)?;
    let names = table_stmt
        .query_map([], |row| row.get::<_, String>(0))
        .map_err(|_| InspectionError::DatabaseError)?
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|_| InspectionError::DatabaseError)?;
    if names.len() > 4096 {
        return Err(InspectionError::TooManyTables);
    }
    drop(table_stmt);
    let mut tables = Vec::with_capacity(names.len());
    let mut columns_stmt = snapshot
        .prepare("SELECT name FROM pragma_table_xinfo(?1) ORDER BY cid")
        .map_err(|_| InspectionError::DatabaseError)?;
    for name in names {
        let columns = columns_stmt
            .query_map([&name], |row| row.get::<_, String>(0))
            .map_err(|_| InspectionError::DatabaseError)?
            .collect::<rusqlite::Result<Vec<_>>>()
            .map_err(|_| InspectionError::DatabaseError)?;
        tables.push(InspectedTable { name, columns });
    }
    Ok(SqliteInspection {
        application_id,
        user_version,
        tables,
        integrity_ok: true,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn snapshots_schema_and_preserves_source() {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "minglefield-inspect-{}-{stamp}.sqlite3",
            std::process::id()
        ));
        {
            let db = Connection::open(&path).unwrap();
            db.execute_batch(
                "CREATE TABLE alpha_users (id TEXT PRIMARY KEY); PRAGMA user_version=7; PRAGMA application_id=123;",
            )
            .unwrap();
        }
        let before = std::fs::read(&path).unwrap();
        let result = inspect_sqlite(&path).unwrap();
        assert!(result.integrity_ok);
        assert_eq!(result.application_id, 123);
        assert_eq!(result.user_version, 7);
        assert_eq!(result.tables[0].name, "alpha_users");
        assert_eq!(result.tables[0].columns, vec!["id"]);
        assert_eq!(std::fs::read(&path).unwrap(), before);
        std::fs::remove_file(path).unwrap();
    }

    #[test]
    fn rejects_missing_file() {
        assert_eq!(
            inspect_sqlite(Path::new("minglefield-nonexistent-database-file")),
            Err(InspectionError::NotRegularFile)
        );
    }
}
