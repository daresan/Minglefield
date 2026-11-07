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
    if !result.source_encrypted || !result.integrity_ok || result.foreign_key_violations != 0 {
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
            connection
                .pragma_update(None, "key", "StrongKey123!")
                .unwrap();
            connection
                .execute_batch(
                    "CREATE TABLE alpha_users(user_id TEXT PRIMARY KEY, disabled INTEGER);
                     INSERT INTO alpha_users VALUES('mingleadmin',0);",
                )
                .unwrap();
        }
        {
            let connection = Connection::open(&plaintext).unwrap();
            connection
                .execute_batch("CREATE TABLE demo(id INTEGER);")
                .unwrap();
        }
        let result = verify_encrypted_database(&ciphertext, "StrongKey123!").unwrap();
        assert!(result.encrypted && result.integrity_verified);
        assert!(result.alpha_users_table_present);
        assert!(verify_encrypted_database(&ciphertext, "wrong!").is_err());
        assert!(verify_encrypted_database(&plaintext, "StrongKey123!").is_err());
        std::fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn reviewed_ciphertext_copy_preserves_source_backup_and_existing_identity() {
        use crate::encrypted_copy_preflight::EXPERIMENTAL_COPY_CONFIRMATION;
        use rusqlite::{Connection, OpenFlags};
        let dir = std::env::temp_dir().join(format!(
            "mf-copy-identity-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let source = dir.join("original.db");
        let backup = dir.join("independent-backup.db");
        let destination = dir.join("new-encrypted.db");
        {
            let db = Connection::open(&source).unwrap();
            db.pragma_update(None, "key", "ExistingKey9!").unwrap();
            db.execute_batch(
                "CREATE TABLE alpha_invites(invitation_hash TEXT, user_id TEXT, expires_at INTEGER, redeemed INTEGER, revoked INTEGER);
                 CREATE TABLE alpha_users(user_id TEXT PRIMARY KEY, disabled INTEGER);
                 INSERT INTO alpha_users VALUES('mingleadmin',0);
                 CREATE TABLE alpha_agents(agent_id TEXT, user_id TEXT, disabled INTEGER);
                 CREATE TABLE alpha_sessions(token_hash TEXT, user_id TEXT, expires_at INTEGER, revoked INTEGER);
                 CREATE TABLE alpha_jobs(job_id TEXT, user_id TEXT, agent_id TEXT, idempotency_key TEXT, action TEXT);
                 CREATE TABLE alpha_passwords(user_id TEXT, salt BLOB, password_hash BLOB);
                 CREATE TABLE alpha_agent_grants(agent_id TEXT, grantee_user_id TEXT, action TEXT, revoked INTEGER);
                 CREATE TABLE sec01_host_owners(host_id TEXT, owner_id TEXT);
                 INSERT INTO sec01_host_owners VALUES('local.stable','mingleadmin');",
            )
            .unwrap();
        }
        std::fs::copy(&source, &backup).unwrap();
        let before = std::fs::read(&source).unwrap();
        let result = create_reviewed_encrypted_database_copy(
            &source,
            &destination,
            &backup,
            "ExistingKey9!",
            "AnotherStrongKey19!",
            &[],
            EXPERIMENTAL_COPY_CONFIRMATION,
        )
        .unwrap();
        assert!(result.destination_created && result.encrypted_destination_verified);
        assert_eq!(std::fs::read(&source).unwrap(), before);
        assert_eq!(std::fs::read(&backup).unwrap(), before);
        let copied =
            Connection::open_with_flags(&destination, OpenFlags::SQLITE_OPEN_READ_ONLY).unwrap();
        copied
            .pragma_update(None, "key", "AnotherStrongKey19!")
            .unwrap();
        let host: String = copied
            .query_row(
                "SELECT host_id FROM sec01_host_owners WHERE owner_id='mingleadmin'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(host, "local.stable");
        drop(copied);
        assert!(create_reviewed_encrypted_database_copy(
            &source,
            &destination,
            &backup,
            "ExistingKey9!",
            "AnotherStrongKey19!",
            &[],
            EXPERIMENTAL_COPY_CONFIRMATION,
        )
        .is_err());
        std::fs::remove_dir_all(dir).unwrap();
    }
}
