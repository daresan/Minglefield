//! Shared SQLCipher-only CLI/GUI operations. No Host claim or app launch.
//! The reviewed destination writer remains in encrypted_copy_preflight.
use crate::encrypted_copy_preflight::{
    execute_reviewed_encrypted_copy_with_schema, EncryptedTestCopy,
};
use crate::sqlite_inspection::inspect_sqlite_with_password;
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerifiedEncryptedDatabase {
    pub encrypted: bool,
    pub integrity_verified: bool,
    pub tables: usize,
    pub schema_entries: usize,
    pub alpha_users_table_present: bool,
}

pub fn verify_encrypted_database(
    path: &Path,
    key: &str,
) -> Result<VerifiedEncryptedDatabase, &'static str> {
    let result = inspect_sqlite_with_password(path, key)
        .map_err(|_| "SQLCipher database inspect/unlock rejected")?;
    if !result.source_encrypted
        || !result.integrity_ok
        || result.foreign_key_violations != 0
    {
        return Err("database must be encrypted and integrity-valid");
    }
    Ok(VerifiedEncryptedDatabase {
        encrypted: true,
        integrity_verified: true,
        tables: result.tables.len(),
        schema_entries: result.schema_objects.len(),
        alpha_users_table_present: result.tables.iter().any(|t| t.name == "alpha_users"),
    })
}

/// Perform the same reviewed exclusive destination publication as the GUI.
/// No extra user-visible rehearsal, no Host/user creation, and no overwrite.
/// The caller must supply the existing source and separate verified backup.
#[allow(clippy::too_many_arguments)]
pub fn create_reviewed_encrypted_database_copy(
    source: &Path,
    destination: &Path,
    backup: &Path,
    existing_password: &str,
    new_password: &str,
    schema_additions: &[String],
    confirmation: &str,
) -> Result<EncryptedTestCopy, String> {
    execute_reviewed_encrypted_copy_with_schema(
        source,
        destination,
        backup,
        existing_password,
        new_password,
        &[],
        schema_additions,
        confirmation,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::Connection;

    #[test]
    fn verification_requires_genuine_sqlcipher_and_correct_key() {
        let dir = std::env::temp_dir().join(format!(
            "mf-db-operation-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let ciphertext = dir.join("encrypted.db");
        let plaintext = dir.join("plaintext.db");
        {
            let connection = Connection::open(&ciphertext).unwrap();
            connection.pragma_update(None, "key", "StrongKey123!").unwrap();
            connection.execute_batch("CREATE TABLE alpha_users(user_id TEXT PRIMARY KEY, disabled INTEGER); INSERT INTO alpha_users VALUES('mingleadmin',0);").unwrap();
        }
        {
            let connection = Connection::open(&plaintext).unwrap();
            connection.execute_batch("CREATE TABLE demo(id INTEGER);").unwrap();
        }
        let result = verify_encrypted_database(&ciphertext, "StrongKey123!").unwrap();
        assert!(result.encrypted && result.integrity_verified);
        assert!(result.alpha_users_table_present);
        assert!(verify_encrypted_database(&ciphertext, "wrong!").is_err());
        assert!(verify_encrypted_database(&plaintext, "StrongKey123!").is_err());
        std::fs::remove_dir_all(dir).unwrap();
    }
}
