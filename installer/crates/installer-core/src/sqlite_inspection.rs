//! SQLite integrity and schema inspection on a consistent in-memory snapshot.
//! This module never executes migrations or writes schema changes to the source.

use rusqlite::{backup::Backup, Connection, OpenFlags};
use std::path::Path;
use std::time::Duration;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InspectedTable {
    pub name: String,
    pub columns: Vec<String>,
    pub create_sql: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SchemaObject {
    pub object_type: String,
    pub name: String,
    pub table_name: String,
    pub create_sql: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SqliteInspection {
    pub application_id: i64,
    pub user_version: i64,
    pub tables: Vec<InspectedTable>,
    pub schema_objects: Vec<SchemaObject>,
    pub integrity_ok: bool,
    pub foreign_key_violations: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InspectionError {
    NotRegularFile,
    DatabaseError,
    IntegrityFailed,
    TooManyTables,
    PasswordRequired,
    UnlockFailed,
}

/// Opens the source read-only and backs up a transactionally consistent view
/// to memory. SQLite may manage WAL shared-memory sidecars while reading an
/// active database; no source schema or user data is modified here.
/// The result does not establish that a database belongs to Minglefield.
pub fn inspect_sqlite(path: &Path) -> Result<SqliteInspection, InspectionError> {
    inspect_sqlite_with_password(path, "")
}

/// Inspects plaintext SQLite without a key, or SQLCipher databases with an
/// explicit key. A failed encrypted unlock never falls back to plaintext.
/// The supplied key is never interpolated into SQL or included in errors.
pub fn inspect_sqlite_with_password(
    path: &Path,
    password: &str,
) -> Result<SqliteInspection, InspectionError> {
    let (_, inspection) = open_inspected_snapshot(path, password)?;
    Ok(inspection)
}

/// Return the same transactionally consistent, integrity-checked in-memory
/// snapshot used to inspect the schema. Callers must read records from this
/// connection, never reopen the mutable source after validating it.
pub fn open_inspected_snapshot(
    path: &Path,
    password: &str,
) -> Result<(Connection, SqliteInspection), InspectionError> {
    let metadata = std::fs::symlink_metadata(path).map_err(|_| InspectionError::NotRegularFile)?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err(InspectionError::NotRegularFile);
    }
    let mut header = [0_u8; 16];
    {
        use std::io::Read;
        let mut file = std::fs::File::open(path).map_err(|_| InspectionError::DatabaseError)?;
        file.read_exact(&mut header)
            .map_err(|_| InspectionError::DatabaseError)?;
    }
    let plaintext = &header == b"SQLite format 3\0";
    if !plaintext && password.is_empty() {
        return Err(InspectionError::PasswordRequired);
    }
    let source = Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|_| InspectionError::DatabaseError)?;
    if !plaintext {
        source
            .pragma_update(None, "key", password)
            .map_err(|_| InspectionError::UnlockFailed)?;
        source
            .query_row("SELECT count(*) FROM sqlite_master", [], |row| {
                row.get::<_, i64>(0)
            })
            .map_err(|_| InspectionError::UnlockFailed)?;
    }
    let mut snapshot = Connection::open_in_memory().map_err(|_| InspectionError::DatabaseError)?;
    if !plaintext {
        snapshot
            .pragma_update(None, "key", password)
            .map_err(|_| InspectionError::DatabaseError)?;
    }
    {
        let backup =
            Backup::new(&source, &mut snapshot).map_err(|_| InspectionError::DatabaseError)?;
        backup
            .run_to_completion(128, Duration::from_millis(50), None)
            .map_err(|_| InspectionError::DatabaseError)?;
    }
    let check: String = snapshot
        .query_row("PRAGMA quick_check", [], |row| row.get(0))
        .map_err(|_| InspectionError::DatabaseError)?;
    if check != "ok" {
        return Err(InspectionError::IntegrityFailed);
    }
    // SQLite quick_check does not validate foreign-key relationships.
    // Report violations without suppressing the schema inventory.
    let foreign_key_violations = {
        let mut statement = snapshot
            .prepare("PRAGMA foreign_key_check")
            .map_err(|_| InspectionError::DatabaseError)?;
        let mut rows = statement
            .query([])
            .map_err(|_| InspectionError::DatabaseError)?;
        let mut count = 0_u64;
        while rows
            .next()
            .map_err(|_| InspectionError::DatabaseError)?
            .is_some()
        {
            count = count.checked_add(1).ok_or(InspectionError::DatabaseError)?;
        }
        count
    };
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
        let create_sql = snapshot
            .query_row(
                "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name = ?1",
                [&name],
                |row| row.get(0),
            )
            .map_err(|_| InspectionError::DatabaseError)?;
        tables.push(InspectedTable {
            name,
            columns,
            create_sql,
        });
    }
    drop(columns_stmt);
    let mut objects_stmt = snapshot
        .prepare("SELECT type, name, tbl_name, sql FROM sqlite_schema WHERE type IN ('index', 'trigger', 'view') ORDER BY type, name")
        .map_err(|_| InspectionError::DatabaseError)?;
    let schema_objects = objects_stmt
        .query_map([], |row| {
            Ok(SchemaObject {
                object_type: row.get(0)?,
                name: row.get(1)?,
                table_name: row.get(2)?,
                create_sql: row.get(3)?,
            })
        })
        .map_err(|_| InspectionError::DatabaseError)?
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|_| InspectionError::DatabaseError)?;
    drop(objects_stmt);
    Ok((snapshot, SqliteInspection {
        application_id,
        user_version,
        tables,
        schema_objects,
        integrity_ok: true,
        foreign_key_violations,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn verified_snapshot_is_isolated_from_later_source_edits() {
        let file = std::env::temp_dir().join(format!("mf-snapshot-{}.sqlite3", std::process::id()));
        {
            let db = Connection::open(&file).unwrap();
            db.execute_batch("CREATE TABLE records(id TEXT, label TEXT); INSERT INTO records VALUES('one','before');").unwrap();
        }
        let (snapshot, inspection) = open_inspected_snapshot(&file, "").unwrap();
        assert!(inspection.integrity_ok);
        {
            let db = Connection::open(&file).unwrap();
            db.execute("UPDATE records SET label='after'", []).unwrap();
        }
        let value: String = snapshot.query_row("SELECT label FROM records", [], |r| r.get(0)).unwrap();
        assert_eq!(value, "before");
        drop(snapshot);
        std::fs::remove_file(file).unwrap();
    }

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
        assert_eq!(result.foreign_key_violations, 0);
        assert_eq!(result.application_id, 123);
        assert_eq!(result.user_version, 7);
        assert_eq!(result.tables[0].name, "alpha_users");
        assert_eq!(result.tables[0].columns, vec!["id"]);
        assert!(result.tables[0]
            .create_sql
            .as_deref()
            .unwrap()
            .contains("PRIMARY KEY"));
        assert!(result
            .schema_objects
            .iter()
            .any(|item| item.object_type == "index"));
        assert_eq!(std::fs::read(&path).unwrap(), before);
        std::fs::remove_file(path).unwrap();
    }

    #[test]
    fn plaintext_database_accepts_optional_password() {
        let path = std::env::temp_dir().join(format!(
            "minglefield-plaintext-password-{}.sqlite3",
            std::process::id()
        ));
        {
            let db = Connection::open(&path).unwrap();
            db.execute_batch("CREATE TABLE alpha_users (id TEXT PRIMARY KEY);")
                .unwrap();
        }
        assert!(inspect_sqlite_with_password(&path, "ignored-existing-password").is_ok());
        std::fs::remove_file(path).unwrap();
    }

    #[test]
    fn encrypted_database_requires_correct_password() {
        let path = std::env::temp_dir().join(format!(
            "minglefield-encrypted-password-{}.sqlite3",
            std::process::id()
        ));
        {
            let db = Connection::open(&path).unwrap();
            db.pragma_update(None, "key", "StrongPassword9!").unwrap();
            db.execute_batch("CREATE TABLE alpha_users (id TEXT PRIMARY KEY);")
                .unwrap();
        }
        assert_eq!(
            inspect_sqlite_with_password(&path, ""),
            Err(InspectionError::PasswordRequired)
        );
        assert_eq!(
            inspect_sqlite_with_password(&path, "incorrect"),
            Err(InspectionError::UnlockFailed)
        );
        let result = inspect_sqlite_with_password(&path, "StrongPassword9!").unwrap();
        assert_eq!(result.tables[0].name, "alpha_users");
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
