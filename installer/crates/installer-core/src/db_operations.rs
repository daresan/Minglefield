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


pub const NEW_ENCRYPTED_DATABASE_CONFIRMATION: &str = "CREATE NEW ENCRYPTED DATABASE";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NewEncryptedDatabase {
    pub status: &'static str,
    pub encrypted_database_verified: bool,
    pub host_provisioning_enabled: bool,
    pub application_launch_enabled: bool,
}

/// Create a genuinely new SQLCipher container without importing a legacy DB.
///
/// This bounded primitive does not create application tables, users, Host IDs,
/// ownership grants or application sessions. Existing Alpha initialization
/// and first-run Host authorization remain the sole sources of those records.
/// The destination parent must already exist. After an interrupted creation
/// the exclusive destination name stays occupied for explicit review.
pub fn create_new_encrypted_database(
    destination: &Path,
    new_password: &str,
    confirmation: &str,
) -> Result<NewEncryptedDatabase, String> {
    use crate::database_password::validate_new_database_password;
    use rusqlite::{Connection, OpenFlags};
    use std::io::Read;
    use std::path::Component;

    if confirmation != NEW_ENCRYPTED_DATABASE_CONFIRMATION {
        return Err("Explicit fresh encrypted-database approval required".into());
    }
    validate_new_database_password(new_password)
        .map_err(|_| "New SQLCipher password does not meet the shared policy")?;
    if !destination.is_absolute()
        || destination
            .components()
            .any(|component| component == Component::ParentDir)
    {
        return Err("Fresh encrypted-database destination must be absolute".into());
    }
    let parent = destination
        .parent()
        .ok_or("Fresh encrypted-database destination has no parent")?;
    let parent_meta = std::fs::symlink_metadata(parent)
        .map_err(|_| "Fresh database parent must already exist")?;
    if !parent_meta.is_dir() || parent_meta.file_type().is_symlink() {
        return Err("Fresh database parent must be a real directory".into());
    }

    // Exclusive creation is the primary no-overwrite boundary, including
    // hard links and existing regular files. Do not retry/replace on failure.
    let initial_file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(destination)
        .map_err(|_| "Fresh SQLCipher target already exists or cannot be created")?;
    drop(initial_file);
    let connection = Connection::open_with_flags(
        destination,
        OpenFlags::SQLITE_OPEN_READ_WRITE,
    )
    .map_err(|_| "Cannot initialize fresh SQLCipher file")?;
    connection
        .pragma_update(None, "key", new_password)
        .map_err(|_| "Cannot set new SQLCipher key")?;
    let cipher_version: String = connection
        .query_row("PRAGMA cipher_version", [], |row| row.get(0))
        .map_err(|_| "SQLCipher engine is not available")?;
    if cipher_version.is_empty() {
        return Err("SQLCipher engine is not available".into());
    }
    // Force creation of an encrypted file header without leaving a duplicate
    // copy of the application's canonical schema in installer code.
    connection
        .execute_batch(
            "CREATE TABLE minglefield_new_db_bootstrap_marker(id INTEGER);
             DROP TABLE minglefield_new_db_bootstrap_marker;",
        )
        .map_err(|_| "Cannot initialize encrypted database pages")?;
    drop(connection);
    let mut header = [0_u8; 16];
    std::fs::File::open(destination)
        .and_then(|mut file| file.read_exact(&mut header))
        .map_err(|_| "New encrypted database is incomplete")?;
    if &header == b"SQLite format 3\0" {
        return Err("Fresh SQLCipher database unexpectedly has a plaintext header".into());
    }
    let verified = verify_encrypted_database(destination, new_password)
        .map_err(|_| "Fresh SQLCipher database verification failed")?;
    if !verified.encrypted || !verified.integrity_verified || verified.tables != 0 {
        return Err("Fresh SQLCipher database contains unexpected application data".into());
    }
    std::fs::OpenOptions::new()
        .read(true)
        .open(destination)
        .and_then(|file| file.sync_all())
        .map_err(|_| "Cannot flush fresh SQLCipher destination")?;

    Ok(NewEncryptedDatabase {
        status: "new_encrypted_database_created",
        encrypted_database_verified: true,
        host_provisioning_enabled: false,
        application_launch_enabled: false,
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
    fn new_ciphertext_requires_consent_and_never_creates_host_or_user() {
        let dir = std::env::temp_dir().join(format!(
            "mf-fresh-database-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("first-install.db");
        assert!(
            create_new_encrypted_database(&path, "FreshKey123!", "MISSING APPROVAL").is_err()
        );
        assert!(!path.exists());
        let result = create_new_encrypted_database(
            &path,
            "FreshKey123!",
            NEW_ENCRYPTED_DATABASE_CONFIRMATION,
        )
        .unwrap();
        assert_eq!(result.status, "new_encrypted_database_created");
        assert!(result.encrypted_database_verified);
        assert!(!result.host_provisioning_enabled);
        assert!(!result.application_launch_enabled);
        let verified = verify_encrypted_database(&path, "FreshKey123!").unwrap();
        assert_eq!(verified.tables, 0);
        assert!(!verified.alpha_users_table_present);
        assert!(verify_encrypted_database(&path, "WrongPassword9!").is_err());
        let original = std::fs::read(&path).unwrap();
        assert!(
            create_new_encrypted_database(
                &path,
                "FreshKey123!",
                NEW_ENCRYPTED_DATABASE_CONFIRMATION,
            )
            .is_err()
        );
        assert_eq!(std::fs::read(&path).unwrap(), original);
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
