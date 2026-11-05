//! Isolated on-disk SQLCipher export rehearsal. No final destination writes.
use crate::database_password::validate_new_database_password;
use crate::snapshot_fidelity::{create_verified_memory_copy, verify_snapshot_equality};
use crate::sqlite_inspection::open_inspected_snapshot;
use rusqlite::{params, Connection, OpenFlags};
use std::{
    fs,
    io::Read,
    path::{Path, PathBuf},
};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EncryptedTestCopy {
    pub full_source_verified: bool,
    pub ciphertext_header_verified: bool,
    pub wrong_key_rejected: bool,
    pub full_disk_copy_verified: bool,
    pub rows_checked: u64,
    pub tables_checked: usize,
    pub schema_entries_checked: usize,
    pub temporary_files_removed: bool,
    pub destination_created: bool,
    pub encrypted_destination_verified: bool,
    pub execution_enabled: bool,
}

struct PrivateTempDir {
    path: PathBuf,
    cleaned: bool,
}

impl PrivateTempDir {
    fn create(source: &Connection) -> Result<Self, String> {
        for _ in 0..8 {
            let id: String = source
                .query_row("SELECT lower(hex(randomblob(16)))", [], |r| r.get(0))
                .map_err(|_| "Cannot choose private staging identifier")?;
            let path = std::env::temp_dir().join(format!("minglefield-stage-{id}"));
            #[cfg(unix)]
            let mut builder = fs::DirBuilder::new();
            #[cfg(not(unix))]
            let builder = fs::DirBuilder::new();
            #[cfg(unix)]
            {
                use std::os::unix::fs::DirBuilderExt;
                builder.mode(0o700);
            }
            match builder.create(&path) {
                Ok(()) => {
                    return Ok(Self {
                        path,
                        cleaned: false,
                    })
                }
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {}
                Err(_) => return Err("Cannot create private temporary staging directory".into()),
            }
        }
        Err("Cannot obtain unique private staging directory".into())
    }
    fn remove(mut self) -> Result<(), String> {
        fs::remove_dir_all(&self.path)
            .map_err(|_| "Cannot clean temporary encrypted copy".to_owned())?;
        self.cleaned = true;
        Ok(())
    }
}
impl Drop for PrivateTempDir {
    fn drop(&mut self) {
        if !self.cleaned {
            let _ = fs::remove_dir_all(&self.path);
        }
    }
}

fn export(source: &Connection, path: &Path, key: &str) -> Result<(), String> {
    // SQLCipher backup does not support plaintext->encrypted; sqlcipher_export
    // does. Both filename and password are bound, never interpolated into SQL.
    source
        .execute(
            "ATTACH DATABASE ?1 AS encrypted_stage KEY ?2",
            params![path.to_string_lossy().as_ref(), key],
        )
        .map_err(|_| "Cannot attach protected temporary SQLCipher destination")?;
    let result = (|| -> Result<(), String> {
        // SQLCipher's export function returns NULL on successful completion.
        source
            .query_row("SELECT sqlcipher_export('encrypted_stage')", [], |r| {
                r.get::<_, Option<String>>(0)
            })
            .map_err(|_| "SQLCipher export of source records failed")?;
        let user_version: i64 = source
            .query_row("PRAGMA main.user_version", [], |r| r.get(0))
            .map_err(|_| "Cannot read source user_version")?;
        let application_id: i64 = source
            .query_row("PRAGMA main.application_id", [], |r| r.get(0))
            .map_err(|_| "Cannot read source application_id")?;
        // SQLCipher export does not automatically preserve these metadata.
        source.execute_batch(&format!(
            "PRAGMA encrypted_stage.user_version={user_version}; PRAGMA encrypted_stage.application_id={application_id};"
        )).map_err(|_| "Cannot preserve encrypted database metadata")?;
        Ok(())
    })();
    let detached = source.execute_batch("DETACH DATABASE encrypted_stage");
    result?;
    detached.map_err(|_| "Cannot detach temporary encrypted destination")?;
    Ok(())
}

/// A real ciphertext file is created ONLY in a private randomized temp dir,
/// reopened with the supplied NEW key, compared, and deleted. The proposed
/// final destination and the existing Alpha source are never written.
pub fn rehearse_encrypted_test_copy(
    source_path: &Path,
    existing_password: &str,
    new_password: &str,
) -> Result<EncryptedTestCopy, String> {
    validate_new_database_password(new_password)
        .map_err(|_| "A strong new SQLCipher password is required")?;
    if !existing_password.is_empty() && existing_password == new_password {
        return Err("New SQLCipher key must differ from the existing key".into());
    }
    let (source, inspection) = open_inspected_snapshot(source_path, existing_password)
        .map_err(|_| "Cannot verify original Alpha database")?;
    if !inspection.integrity_ok || inspection.foreign_key_violations != 0 {
        return Err("Source integrity or foreign-key verification failed".into());
    }
    let source_key = if inspection.source_encrypted {
        existing_password
    } else {
        ""
    };
    let (_, source_proof) = create_verified_memory_copy(&source, source_key)?;
    if !source_proof.values_verified {
        return Err("Original memory copy did not verify".into());
    }
    let private = PrivateTempDir::create(&source)?;
    let staged = private.path.join("temporary-encrypted.sqlite3");
    export(&source, &staged, new_password)?;
    let mut header = [0_u8; 16];
    fs::File::open(&staged)
        .map_err(|_| "Cannot reopen encrypted file header")?
        .read_exact(&mut header)
        .map_err(|_| "Encrypted file header is truncated")?;
    if &header == b"SQLite format 3\0" {
        return Err("Temporary encrypted destination has a plaintext header".into());
    }
    let bad_key = Connection::open_with_flags(&staged, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|_| "Cannot exercise encrypted wrong-key control")?;
    let control_key = if new_password == "WrongControlPassword123!" {
        "DifferentWrongControlPassword2!"
    } else {
        "WrongControlPassword123!"
    };
    bad_key
        .pragma_update(None, "key", control_key)
        .map_err(|_| "Cannot set wrong-key control")?;
    let wrong_key_rejected = bad_key
        .query_row("SELECT count(*) FROM sqlite_schema", [], |r| {
            r.get::<_, i64>(0)
        })
        .is_err();
    drop(bad_key);
    if !wrong_key_rejected {
        return Err("Encrypted copy accepted wrong key".into());
    }
    let reopened = Connection::open_with_flags(&staged, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|_| "Cannot reopen temporary encrypted SQLCipher file")?;
    reopened
        .pragma_update(None, "key", new_password)
        .map_err(|_| "Cannot unlock temporary encrypted SQLCipher file")?;
    let fidelity = verify_snapshot_equality(&source, &reopened)?;
    drop(reopened);
    drop(source);
    private.remove()?;
    Ok(EncryptedTestCopy {
        full_source_verified: true,
        ciphertext_header_verified: true,
        wrong_key_rejected,
        full_disk_copy_verified: fidelity.values_verified,
        rows_checked: fidelity.rows_checked,
        tables_checked: fidelity.tables_checked,
        schema_entries_checked: fidelity.schema_entries_checked,
        temporary_files_removed: true,
        destination_created: false,
        encrypted_destination_verified: false,
        execution_enabled: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::{SystemTime, UNIX_EPOCH};
    static NEXT: AtomicU64 = AtomicU64::new(0);
    fn fixture(encrypted: bool) -> PathBuf {
        let id = NEXT.fetch_add(1, Ordering::Relaxed);
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "minglefield-encrypted-copy-test-{}-{stamp}-{id}.sqlite3",
            std::process::id()
        ));
        {
            let db = Connection::open(&path).unwrap();
            if encrypted {
                db.pragma_update(None, "key", "ExistingKey9!").unwrap();
            }
            db.execute_batch(
                "PRAGMA user_version=17; PRAGMA application_id=12345;
                 CREATE TABLE records(id INTEGER PRIMARY KEY AUTOINCREMENT,payload BLOB,name TEXT);
                 INSERT INTO records(payload,name) VALUES(x'00ff','first'),(x'01ff','second');
                 DELETE FROM records WHERE id=2;
                 CREATE TABLE duplicate_rows(payload BLOB);
                 INSERT INTO duplicate_rows VALUES(x'1234'),(x'1234');
                 CREATE INDEX idx_records_name ON records(name);
                 CREATE VIEW readable AS SELECT name FROM records;",
            )
            .unwrap();
        }
        path
    }
    #[test]
    fn plaintext_source_exports_to_encrypted_file_and_cleans() {
        let path = fixture(false);
        let original = fs::read(&path).unwrap();
        let proof = rehearse_encrypted_test_copy(&path, "", "NewKey123!").unwrap();
        assert!(proof.full_disk_copy_verified && proof.wrong_key_rejected);
        assert!(proof.ciphertext_header_verified && proof.temporary_files_removed);
        assert_eq!(proof.tables_checked, 3);
        assert_eq!(proof.rows_checked, 4);
        assert!(!proof.destination_created && !proof.encrypted_destination_verified);
        assert_eq!(fs::read(&path).unwrap(), original);
        fs::remove_file(path).unwrap();
    }
    #[test]
    fn encrypted_source_rekeys_to_distinct_temporary_key() {
        let path = fixture(true);
        let original = fs::read(&path).unwrap();
        let result = rehearse_encrypted_test_copy(&path, "ExistingKey9!", "NewKey123!").unwrap();
        assert!(result.full_disk_copy_verified);
        assert_eq!(fs::read(&path).unwrap(), original);
        fs::remove_file(path).unwrap();
    }
    #[test]
    fn invalid_keys_reject_without_source_mutation() {
        let path = fixture(true);
        let original = fs::read(&path).unwrap();
        for (existing, next) in [
            ("ExistingKey9!", "weak"),
            ("bad-source-key", "NewKey123!"),
            ("ExistingKey9!", "ExistingKey9!"),
        ] {
            assert!(rehearse_encrypted_test_copy(&path, existing, next).is_err());
            assert_eq!(fs::read(&path).unwrap(), original);
        }
        fs::remove_file(path).unwrap();
    }
    #[test]
    fn temp_directory_drop_cleans_up_after_failure() {
        let db = Connection::open_in_memory().unwrap();
        let path;
        {
            let temp = PrivateTempDir::create(&db).unwrap();
            path = temp.path.clone();
            fs::write(path.join("temporary-encrypted.sqlite3"), b"test").unwrap();
            assert!(path.exists());
        }
        assert!(!path.exists());
    }

}
