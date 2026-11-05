//! Strong, content-aware preflight for the future database migration.
//! Copy the inspected in-memory SQLite snapshot into a second in-memory database.
//! Verify schema metadata and *all* table values, including duplicate rows,
//! BLOBs, internal sqlite_sequence data and extension tables. Nothing persists.
//! This does not create or validate an encrypted SQLCipher destination.
use crate::integrity::sha256;
use rusqlite::{backup::Backup, types::ValueRef, Connection};
use std::collections::BTreeMap;
use std::time::Duration;

const MAX_TABLES: usize = 4096;
const MAX_ROWS_PER_TABLE: u64 = 1_000_000;
const MAX_ROW_BYTES: usize = 128 * 1024 * 1024;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SnapshotFidelity {
    pub tables_checked: usize,
    pub rows_checked: u64,
    pub schema_entries_checked: usize,
    pub internal_tables_checked: usize,
    pub values_verified: bool,
}

fn check_database(db: &Connection) -> Result<(), String> {
    let result: String = db
        .query_row("PRAGMA quick_check", [], |row| row.get(0))
        .map_err(|_| "Cannot validate snapshot copy integrity")?;
    if result != "ok" {
        return Err("Snapshot copy integrity failed".to_owned());
    }
    let violations: i64 = db
        .query_row("SELECT count(*) FROM pragma_foreign_key_check", [], |row| {
            row.get(0)
        })
        .map_err(|_| "Cannot verify snapshot copy foreign keys")?;
    if violations != 0 {
        return Err("Snapshot copy contains foreign-key violations".to_owned());
    }
    Ok(())
}

type SchemaEntry = (String, String, String, Option<String>);

fn schema(db: &Connection) -> Result<Vec<SchemaEntry>, String> {
    let mut statement = db
        .prepare("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name")
        .map_err(|_| "Cannot read complete source schema")?;
    statement
        .query_map([], |row| {
            Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?))
        })
        .map_err(|_| "Cannot inventory source schema")?
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|_| "Cannot decode complete source schema".to_owned())
}

fn table_names(entries: &[SchemaEntry]) -> Vec<String> {
    entries
        .iter()
        .filter(|entry| entry.0 == "table")
        .map(|entry| entry.1.clone())
        .collect()
}

fn quote(identifier: &str) -> String {
    format!("\"{}\"", identifier.replace('"', "\"\""))
}

fn columns(db: &Connection, table: &str) -> Result<Vec<String>, String> {
    let mut stmt = db
        .prepare("SELECT name FROM pragma_table_xinfo(?1) ORDER BY cid")
        .map_err(|_| "Cannot inspect source table columns")?;
    let result = stmt
        .query_map([table], |row| row.get::<_, String>(0))
        .map_err(|_| "Cannot enumerate source table columns")?
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|_| "Cannot decode source table columns")?;
    if result.is_empty() || result.len() > 1024 {
        return Err("Source table has unsupported column count".to_owned());
    }
    Ok(result)
}

fn append_value(bytes: &mut Vec<u8>, value: ValueRef<'_>) -> Result<(), String> {
    match value {
        ValueRef::Null => bytes.push(0),
        ValueRef::Integer(value) => {
            bytes.push(1);
            bytes.extend_from_slice(&value.to_be_bytes());
        }
        ValueRef::Real(value) => {
            bytes.push(2);
            bytes.extend_from_slice(&value.to_bits().to_be_bytes());
        }
        ValueRef::Text(value) => {
            bytes.push(3);
            bytes.extend_from_slice(&(value.len() as u64).to_be_bytes());
            bytes.extend_from_slice(value);
        }
        ValueRef::Blob(value) => {
            bytes.push(4);
            bytes.extend_from_slice(&(value.len() as u64).to_be_bytes());
            bytes.extend_from_slice(value);
        }
    }
    if bytes.len() > MAX_ROW_BYTES {
        return Err("Source row exceeds safe verification size".to_owned());
    }
    Ok(())
}

fn row_fingerprints(
    db: &Connection,
    table: &str,
) -> Result<(u64, BTreeMap<[u8; 32], u64>), String> {
    let names = columns(db, table)?;
    let sql = format!(
        "SELECT {} FROM {}",
        names
            .iter()
            .map(|name| quote(name))
            .collect::<Vec<_>>()
            .join(","),
        quote(table)
    );
    let mut stmt = db
        .prepare(&sql)
        .map_err(|_| "Cannot inspect all source values")?;
    let count = stmt.column_count();
    let mut rows = stmt.query([]).map_err(|_| "Cannot read source values")?;
    let mut digests = BTreeMap::new();
    let mut total = 0_u64;
    while let Some(row) = rows.next().map_err(|_| "Cannot read complete table")? {
        total = total.checked_add(1).ok_or("Row count overflow")?;
        if total > MAX_ROWS_PER_TABLE {
            return Err("Table exceeds safe verification row limit".to_owned());
        }
        let mut encoding = Vec::with_capacity(128);
        encoding.extend_from_slice(&(count as u64).to_be_bytes());
        for index in 0..count {
            let value = row
                .get_ref(index)
                .map_err(|_| "Cannot inspect source cell")?;
            append_value(&mut encoding, value)?;
        }
        let digest = sha256(&encoding);
        let entry = digests.entry(digest).or_insert(0_u64);
        *entry = entry.checked_add(1).ok_or("Row frequency overflow")?;
    }
    Ok((total, digests))
}

/// Compares structure and the multiset of full row contents for every table,
/// including SQLite internal tables. SHA-256 row fingerprints remain private
/// to this process, are multiplicity-sensitive, and are never returned to UI.
pub fn verify_snapshot_equality(
    original: &Connection,
    copied: &Connection,
) -> Result<SnapshotFidelity, String> {
    check_database(original)?;
    check_database(copied)?;
    for pragma in ["application_id", "user_version", "encoding"] {
        let sql = format!("PRAGMA {pragma}");
        let left: rusqlite::types::Value = original
            .query_row(&sql, [], |r| r.get(0))
            .map_err(|_| "Cannot inspect source database metadata")?;
        let right: rusqlite::types::Value = copied
            .query_row(&sql, [], |r| r.get(0))
            .map_err(|_| "Cannot inspect copied database metadata")?;
        if left != right {
            return Err("Database metadata differs after snapshot copy".to_owned());
        }
    }
    let left = schema(original)?;
    let right = schema(copied)?;
    if left != right {
        return Err("Schema objects differ after snapshot copy".to_owned());
    }
    let table_names = table_names(&left);
    if table_names.len() > MAX_TABLES {
        return Err("Source has too many tables to verify".to_owned());
    }
    let mut total_rows = 0_u64;
    let mut internal_tables = 0;
    for table in &table_names {
        if table.starts_with("sqlite_") {
            internal_tables += 1;
        }
        if columns(original, table)? != columns(copied, table)? {
            return Err("Source table columns differ after snapshot copy".to_owned());
        }
        let before = row_fingerprints(original, table)?;
        let after = row_fingerprints(copied, table)?;
        if before != after {
            return Err(format!("Stored rows differ after snapshot copy: {table}"));
        }
        total_rows = total_rows
            .checked_add(before.0)
            .ok_or("Total row count overflow")?;
    }
    Ok(SnapshotFidelity {
        tables_checked: table_names.len(),
        rows_checked: total_rows,
        schema_entries_checked: left.len(),
        internal_tables_checked: internal_tables,
        values_verified: true,
    })
}

/// Produce a second, disposable in-memory database via the same SQLite backup
/// API used for source inspection. Verify *before* allowing staged changes.
pub fn create_verified_memory_copy(
    source: &Connection,
) -> Result<(Connection, SnapshotFidelity), String> {
    let mut copied = Connection::open_in_memory()
        .map_err(|_| "Cannot prepare isolated in-memory migration copy")?;
    {
        let backup = Backup::new(source, &mut copied)
            .map_err(|_| "Cannot initialize isolated migration backup")?;
        backup
            .run_to_completion(128, Duration::from_millis(50), None)
            .map_err(|_| "Cannot construct in-memory migration backup")?;
    }
    let verified = verify_snapshot_equality(source, &copied)?;
    Ok((copied, verified))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> Connection {
        let db = Connection::open_in_memory().unwrap();
        db.execute_batch(
            "PRAGMA application_id=12345;
             PRAGMA user_version=17;
             CREATE TABLE autoinc(id INTEGER PRIMARY KEY AUTOINCREMENT, payload BLOB, note TEXT);
             INSERT INTO autoinc(payload,note) VALUES(x'00ff','a'),(x'01ff','b');
             DELETE FROM autoinc WHERE id=2;
             CREATE TABLE duplicate_values(payload BLOB, note TEXT);
             INSERT INTO duplicate_values VALUES(x'010203','same'),(x'010203','same'),(x'040506','different');
             CREATE TABLE no_rowid(k TEXT PRIMARY KEY, bytes BLOB) WITHOUT ROWID;
             INSERT INTO no_rowid VALUES('unique',x'0001ff');
             CREATE INDEX ix_autoinc_note ON autoinc(note);
             CREATE VIEW visible AS SELECT note FROM autoinc;
             CREATE TRIGGER tr_autoinc AFTER UPDATE OF note ON autoinc
               BEGIN INSERT INTO duplicate_values VALUES(x'ff','changed'); END;"
        ).unwrap();
        db
    }

    #[test]
    fn verifies_complete_copy_including_blob_duplicates_and_sqlite_sequence() {
        let db = fixture();
        let (copy, report) = create_verified_memory_copy(&db).unwrap();
        assert!(report.values_verified);
        assert_eq!(report.tables_checked, 4);
        assert_eq!(report.rows_checked, 5);
        assert_eq!(report.internal_tables_checked, 1);
        assert!(report.schema_entries_checked >= 7);
        assert_eq!(verify_snapshot_equality(&db, &copy).unwrap(), report);
    }

    #[test]
    fn detects_corrupted_blob_even_with_unchanged_row_counts() {
        let db = fixture();
        let (copy, _) = create_verified_memory_copy(&db).unwrap();
        copy.execute(
            "UPDATE duplicate_values SET payload=x'99' WHERE rowid=2",
            [],
        )
        .unwrap();
        assert!(verify_snapshot_equality(&db, &copy).is_err());
    }

    #[test]
    fn detects_missing_duplicate_even_when_total_counts_match() {
        let db = fixture();
        let (copy, _) = create_verified_memory_copy(&db).unwrap();
        copy.execute_batch(
            "DELETE FROM duplicate_values WHERE rowid=2;
             INSERT INTO duplicate_values VALUES(x'040506','different');",
        )
        .unwrap();
        assert!(verify_snapshot_equality(&db, &copy).is_err());
    }

    #[test]
    fn detects_schema_and_version_drift_and_rollback_recovery() {
        let db = fixture();
        let (mut copy, _) = create_verified_memory_copy(&db).unwrap();
        {
            let transaction = copy.transaction().unwrap();
            transaction
                .execute("UPDATE no_rowid SET bytes=x'1234'", [])
                .unwrap();
            assert!(verify_snapshot_equality(&db, &transaction).is_err());
            transaction.rollback().unwrap();
        }
        assert!(verify_snapshot_equality(&db, &copy).is_ok());
        copy.execute_batch("DROP VIEW visible;").unwrap();
        assert!(verify_snapshot_equality(&db, &copy).is_err());
        let (copy, _) = create_verified_memory_copy(&db).unwrap();
        copy.pragma_update(None, "user_version", 20).unwrap();
        assert!(verify_snapshot_equality(&db, &copy).is_err());
    }
}
