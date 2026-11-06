//! Isolated on-disk SQLCipher export rehearsal. No final destination writes.
use crate::database_password::validate_new_database_password;
use crate::migration_destination::{preview_migration_destination, PinnedDestinationParent};
use crate::migration_dry_run::{
    apply_staged_to_isolated_copy, table_counts, validate_alpha_schema, ReviewCorrection,
};
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
    pub atomic_temporary_publication_verified: bool,
    pub full_disk_copy_verified: bool,
    pub staged_changes_verified: usize,
    pub staged_values_match_ciphertext: bool,
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
        Self::create_under(source, &std::env::temp_dir())
    }
    fn create_under(source: &Connection, staging_parent: &Path) -> Result<Self, String> {
        for _ in 0..8 {
            let id: String = source
                .query_row("SELECT lower(hex(randomblob(16)))", [], |r| r.get(0))
                .map_err(|_| "Cannot choose private staging identifier")?;
            let path = staging_parent.join(format!("minglefield-stage-{id}"));
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

/// Sync a *previously verified* encrypted stage before the existing
/// test-only hard-link rehearsal. Never open a directory/symlink as data.
/// This establishes a file-data flush barrier only; directory-entry
/// durability, path-handle pinning and crash recovery remain separate gates.
fn sync_verified_ciphertext_stage(path: &Path) -> Result<(), String> {
    let metadata =
        fs::symlink_metadata(path).map_err(|_| "Cannot inspect verified encrypted stage")?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err("Verified encrypted stage is not a regular file".to_owned());
    }
    // A writable handle is required for FlushFileBuffers on Windows.
    // Do not change the ciphertext; only flush its already-verified bytes.
    let file = fs::OpenOptions::new()
        .read(true)
        .write(true)
        .open(path)
        .map_err(|_| "Cannot reopen verified encrypted stage for flush")?;
    if !file
        .metadata()
        .map_err(|_| "Cannot inspect encrypted stage handle")?
        .is_file()
    {
        return Err("Encrypted stage handle is not a regular file".to_owned());
    }
    file.sync_all()
        .map_err(|_| "Cannot flush verified encrypted stage to storage".to_owned())
}

/// A real ciphertext file is created ONLY in a private randomized temp dir,
/// reopened with the supplied NEW key, compared, and deleted. The proposed
/// final destination and the existing Alpha source are never written.
pub fn rehearse_encrypted_test_copy(
    source_path: &Path,
    existing_password: &str,
    new_password: &str,
    corrections: &[ReviewCorrection],
) -> Result<EncryptedTestCopy, String> {
    rehearse_encrypted_test_copy_under(
        source_path,
        existing_password,
        new_password,
        corrections,
        None,
        None,
    )
}

/// Explicit destination-volume *rehearsal* for trusted callers and isolated
/// tests. Creates and removes an encrypted scratch copy in a randomized
/// private subdirectory beneath the selected destination parent. The final
/// destination path itself is never created, replaced or used as a link name.
///
/// Both path checks are advisory: they do not pin a native directory handle
/// or prevent a malicious concurrent directory replacement. This function
/// is NOT a safe final-publication primitive and must not authorize install.
pub fn rehearse_encrypted_test_copy_on_destination_volume(
    source_path: &Path,
    destination_path: &Path,
    existing_password: &str,
    new_password: &str,
    corrections: &[ReviewCorrection],
) -> Result<EncryptedTestCopy, String> {
    let before = preview_migration_destination(source_path, destination_path)
        .map_err(|_| "Destination-volume rehearsal path rejected")?;
    let parent = before
        .destination
        .parent()
        .ok_or("Destination-volume rehearsal parent unavailable")?;
    // Keep the opened native destination-parent identity pinned across the
    // entire isolated export, verification and temporary-link rehearsal.
    // This is still NOT a safe final destination publication primitive.
    let parent_guard = PinnedDestinationParent::open(&before)?;
    let proof = rehearse_encrypted_test_copy_under(
        source_path,
        existing_password,
        new_password,
        corrections,
        Some(parent),
        None,
    )?;
    parent_guard.revalidate()?;
    let after = preview_migration_destination(source_path, destination_path)
        .map_err(|_| "Destination-volume rehearsal path changed")?;
    if before != after {
        return Err("Destination-volume rehearsal path changed".to_owned());
    }
    Ok(proof)
}

fn rehearse_encrypted_test_copy_under(
    source_path: &Path,
    existing_password: &str,
    new_password: &str,
    corrections: &[ReviewCorrection],
    staging_parent: Option<&Path>,
    publication_target: Option<&Path>,
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
    let (mut corrected_memory, source_proof) = create_verified_memory_copy(&source, source_key)?;
    if !source_proof.values_verified {
        return Err("Original memory copy did not verify".into());
    }
    if !corrections.is_empty() {
        validate_alpha_schema(&inspection)?;
        let original_counts = table_counts(&source, &inspection)?;
        // Keep the source snapshot immutable. The shared stale-value,
        // identity, trigger and row-count policy is applied exclusively to
        // our verified second RAM copy, then retained for the disk export.
        apply_staged_to_isolated_copy(
            &mut corrected_memory,
            &inspection,
            &original_counts,
            corrections,
            true,
        )?;
    }
    let private = match staging_parent {
        Some(parent) => PrivateTempDir::create_under(&source, parent)?,
        None => PrivateTempDir::create(&source)?,
    };
    let staged = private.path.join("temporary-encrypted.sqlite3");
    export(&corrected_memory, &staged, new_password)?;
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
    // Any changed field must survive the encryption round-trip exactly.
    // Comparison against the unchanged source would reject legitimate edits;
    // the independently checked corrected RAM copy is the expected target.
    let fidelity = verify_snapshot_equality(&corrected_memory, &reopened)?;
    drop(reopened);
    if !fidelity.values_verified {
        return Err("Verified encrypted stage did not preserve all source values".to_owned());
    }
    // Fail closed before creating even the temporary promotion link if
    // ciphertext cannot be flushed. This is not final publish durability.
    sync_verified_ciphertext_stage(&staged)?;

    // Verify the native create-if-absent publication primitive in the SAME
    // private temporary directory. A hard link either publishes a complete
    // already-verified ciphertext inode or fails if the target exists; it
    // never copies plaintext or truncates an existing file. This is not a
    // claim about the user's eventual destination filesystem or path handles.
    let promoted = private.path.join("atomic-publication-rehearsal.sqlite3");
    fs::hard_link(&staged, &promoted)
        .map_err(|_| "Atomic temporary SQLCipher publication unavailable")?;
    let duplicate_rejected = fs::hard_link(&staged, &promoted)
        .is_err_and(|error| error.kind() == std::io::ErrorKind::AlreadyExists);
    if !duplicate_rejected {
        return Err("Atomic temporary publication did not reject an existing target".to_owned());
    }
    let occupied = private.path.join("preexisting-collision-control");
    fs::write(&occupied, b"unchanged")
        .map_err(|_| "Cannot create atomic publication collision control")?;
    let occupied_rejected = fs::hard_link(&staged, &occupied)
        .is_err_and(|error| error.kind() == std::io::ErrorKind::AlreadyExists);
    if !occupied_rejected || fs::read(&occupied).ok().as_deref() != Some(&b"unchanged"[..]) {
        return Err("Atomic temporary publication did not preserve occupied file".to_owned());
    }
    let published = Connection::open_with_flags(&promoted, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|_| "Cannot reopen atomically published temporary ciphertext")?;
    published
        .pragma_update(None, "key", new_password)
        .map_err(|_| "Cannot unlock atomically published temporary ciphertext")?;
    let promoted_fidelity = verify_snapshot_equality(&corrected_memory, &published)?;
    if promoted_fidelity != fidelity || !promoted_fidelity.values_verified {
        return Err("Atomic temporary ciphertext differs from the staged data".to_owned());
    }
    drop(published);

    // Only explicitly gated callers may request a final-name publication.
    // No hard-link operation may overwrite an existing destination file.
    // Full handle-relative and crash-durable release gates remain separate.
    let fixture_created = if let Some(target) = publication_target {
        fs::hard_link(&staged, target)
            .map_err(|_| "Cannot exclusively publish fixture ciphertext")?;
        let published_fixture =
            Connection::open_with_flags(target, OpenFlags::SQLITE_OPEN_READ_ONLY)
                .map_err(|_| "Cannot reopen published fixture ciphertext")?;
        published_fixture
            .pragma_update(None, "key", new_password)
            .map_err(|_| "Cannot unlock published fixture ciphertext")?;
        let final_fidelity = verify_snapshot_equality(&corrected_memory, &published_fixture)?;
        if final_fidelity != fidelity || !final_fidelity.values_verified {
            return Err("Published fixture data differs from verified stage".to_owned());
        }
        drop(published_fixture);
        true
    } else {
        false
    };
    drop(corrected_memory);
    drop(source);
    private.remove()?;
    Ok(EncryptedTestCopy {
        full_source_verified: true,
        ciphertext_header_verified: true,
        wrong_key_rejected,
        atomic_temporary_publication_verified: true,
        full_disk_copy_verified: fidelity.values_verified,
        staged_changes_verified: corrections.len(),
        staged_values_match_ciphertext: fidelity.values_verified,
        rows_checked: fidelity.rows_checked,
        tables_checked: fidelity.tables_checked,
        schema_entries_checked: fidelity.schema_entries_checked,
        temporary_files_removed: true,
        destination_created: fixture_created,
        encrypted_destination_verified: fixture_created,
        // This flag means general application migration is enabled. A
        // test-only fixture publication cannot turn that capability on.
        execution_enabled: false,
    })
}

/// Explicitly permitted, experimental encrypted *copy*, not application
/// installation or Host authorization. The caller must provide a separate,
/// independently verified backup and the exact opt-in phrase. Unlike the
/// test-only helper, this path is compiled for the controlled Alpha GUI.
pub const EXPERIMENTAL_COPY_CONFIRMATION: &str = "CREATE EXPERIMENTAL ENCRYPTED COPY";

pub fn execute_reviewed_encrypted_copy(
    source_path: &Path,
    destination_path: &Path,
    backup_path: &Path,
    existing_password: &str,
    new_password: &str,
    corrections: &[ReviewCorrection],
    confirmation: &str,
) -> Result<EncryptedTestCopy, String> {
    if confirmation != EXPERIMENTAL_COPY_CONFIRMATION {
        return Err("Experimental encrypted copy requires the exact operator confirmation".into());
    }
    let before = preview_migration_destination(source_path, destination_path)
        .map_err(|_| "Experimental encrypted destination rejected")?;
    let source = before.source.as_path();
    let backup_meta = fs::symlink_metadata(backup_path)
        .map_err(|_| "An existing separate backup file is required")?;
    if backup_meta.file_type().is_symlink() || !backup_meta.is_file() {
        return Err("Backup must be an existing regular file, not a symlink".into());
    }
    let backup = fs::canonicalize(backup_path)
        .map_err(|_| "Cannot identify backup file")?;
    if backup == source || backup == before.destination {
        return Err("Backup must be separate from source and destination".into());
    }
    // A backup is not considered verified because a checkbox was selected.
    // Compare actual data, schema and metadata using independent read-only
    // snapshots. This is a local Alpha safety gate, not proof of physical
    // media independence or adversarial path-race resistance.
    let (source_db, source_info) = open_inspected_snapshot(source, existing_password)
        .map_err(|_| "Cannot verify original source for backup comparison")?;
    let (backup_db, backup_info) = open_inspected_snapshot(&backup, existing_password)
        .map_err(|_| "Cannot open verified source backup")?;
    if !source_info.integrity_ok || !backup_info.integrity_ok
        || source_info.foreign_key_violations != 0
        || backup_info.foreign_key_violations != 0
    {
        return Err("Source and backup must both pass integrity checks".into());
    }
    if !verify_snapshot_equality(&source_db, &backup_db)?.values_verified {
        return Err("Backup contents do not match source".into());
    }
    drop(backup_db);
    drop(source_db);
    let parent = before.destination.parent()
        .ok_or("Destination parent unavailable")?;
    let guard = PinnedDestinationParent::open(&before)?;
    // Explicitly request a durable output filename only after consent and
    // the independent source/backup comparison; use the proven same-volume
    // encrypted staging and exclusive hard-link copy.
    let report = rehearse_encrypted_test_copy_under(
        source, existing_password, new_password, corrections,
        Some(parent), Some(&before.destination),
    )?;
    guard.revalidate_identity()?;
    if !report.destination_created || !report.encrypted_destination_verified
        || !report.full_disk_copy_verified || !report.temporary_files_removed
    {
        return Err("Experimental encrypted copy was not verified".into());
    }
    Ok(report)
}

#[cfg(test)]
fn publish_disposable_fixture_copy(
    source_path: &Path,
    destination_path: &Path,
    existing_password: &str,
    new_password: &str,
    corrections: &[ReviewCorrection],
) -> Result<EncryptedTestCopy, String> {
    let preview = preview_migration_destination(source_path, destination_path)
        .map_err(|_| "Disposable fixture destination rejected")?;
    let guard = PinnedDestinationParent::open(&preview)?;
    guard.revalidate()?;
    let parent = preview
        .destination
        .parent()
        .ok_or("Disposable fixture destination parent unavailable")?;
    rehearse_encrypted_test_copy_under(
        source_path,
        existing_password,
        new_password,
        corrections,
        Some(parent),
        Some(&preview.destination),
    )
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
        let proof = rehearse_encrypted_test_copy(&path, "", "NewKey123!", &[]).unwrap();
        assert!(proof.full_disk_copy_verified && proof.wrong_key_rejected);
        assert!(proof.ciphertext_header_verified && proof.temporary_files_removed);
        assert!(proof.atomic_temporary_publication_verified);
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
        let result =
            rehearse_encrypted_test_copy(&path, "ExistingKey9!", "NewKey123!", &[]).unwrap();
        assert!(result.full_disk_copy_verified);
        assert!(result.atomic_temporary_publication_verified);
        assert_eq!(fs::read(&path).unwrap(), original);
        fs::remove_file(path).unwrap();
    }
    fn target_volume_fixture() -> PathBuf {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let id = NEXT.fetch_add(1, Ordering::Relaxed);
        let directory = std::env::temp_dir().join(format!(
            "minglefield-target-volume-{}-{stamp}-{id}",
            std::process::id()
        ));
        fs::create_dir(&directory).unwrap();
        directory
    }

    #[test]
    fn disposable_fixture_publication_creates_real_ciphertext_on_selected_volume() {
        for source_encrypted in [false, true] {
            let source = fixture(source_encrypted);
            let original = fs::read(&source).unwrap();
            let target_parent = target_volume_fixture();
            let target = target_parent.join("chosen-destination.sqlite3");
            let source_key = if source_encrypted {
                "ExistingKey9!"
            } else {
                ""
            };
            let report =
                publish_disposable_fixture_copy(&source, &target, source_key, "NewKey123!", &[])
                    .unwrap();
            assert!(report.destination_created && report.encrypted_destination_verified);
            assert!(!report.execution_enabled);
            assert!(report.temporary_files_removed && report.full_disk_copy_verified);
            assert!(report.wrong_key_rejected && report.atomic_temporary_publication_verified);
            assert_eq!(fs::read(&source).unwrap(), original);
            assert_eq!(fs::read_dir(&target_parent).unwrap().count(), 1);
            let mut header = [0_u8; 16];
            fs::File::open(&target)
                .unwrap()
                .read_exact(&mut header)
                .unwrap();
            assert_ne!(&header, b"SQLite format 3\0");
            let reopened =
                Connection::open_with_flags(&target, OpenFlags::SQLITE_OPEN_READ_ONLY).unwrap();
            reopened.pragma_update(None, "key", "NewKey123!").unwrap();
            let row: (String, Vec<u8>) = reopened
                .query_row("SELECT name,payload FROM records WHERE id=1", [], |r| {
                    Ok((r.get(0)?, r.get(1)?))
                })
                .unwrap();
            assert_eq!(row, ("first".to_owned(), vec![0, 255]));
            let version: i64 = reopened
                .query_row("PRAGMA user_version", [], |r| r.get(0))
                .unwrap();
            assert_eq!(version, 17);
            drop(reopened);
            fs::remove_dir_all(target_parent).unwrap();
            fs::remove_file(source).unwrap();
        }
    }

    #[test]
    fn disposable_fixture_publication_rejects_collision_and_invalid_inputs() {
        let source = fixture(false);
        let original = fs::read(&source).unwrap();
        let target_parent = target_volume_fixture();
        let target = target_parent.join("chosen-destination.sqlite3");
        fs::write(&target, b"existing-user-data").unwrap();
        assert!(publish_disposable_fixture_copy(&source, &target, "", "NewKey123!", &[],).is_err());
        assert_eq!(fs::read(&target).unwrap(), b"existing-user-data");
        assert_eq!(fs::read_dir(&target_parent).unwrap().count(), 1);
        let missing = target_parent.join("missing").join("chosen.sqlite3");
        assert!(
            publish_disposable_fixture_copy(&source, &missing, "", "NewKey123!", &[],).is_err()
        );
        fs::remove_file(&target).unwrap();
        assert!(publish_disposable_fixture_copy(&source, &target, "", "bad", &[],).is_err());
        assert!(!target.exists());
        assert!(fs::read_dir(&target_parent).unwrap().next().is_none());
        assert_eq!(fs::read(&source).unwrap(), original);
        fs::remove_dir_all(target_parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[test]
    fn disposable_fixture_publication_preserves_reviewed_edits_and_denies_stale_review() {
        let source = editable_alpha_fixture(false);
        let original = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let target = parent.join("corrected.sqlite3");
        let report =
            publish_disposable_fixture_copy(&source, &target, "", "NewKey123!", &changes())
                .unwrap();
        assert_eq!(report.staged_changes_verified, 7);
        assert!(report.destination_created && report.staged_values_match_ciphertext);
        let reopened =
            Connection::open_with_flags(&target, OpenFlags::SQLITE_OPEN_READ_ONLY).unwrap();
        reopened.pragma_update(None, "key", "NewKey123!").unwrap();
        let disabled: i64 = reopened
            .query_row(
                "SELECT disabled FROM alpha_users WHERE user_id='alice'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(disabled, 1);
        let name: String = reopened
            .query_row(
                "SELECT name FROM alpha_game_projects WHERE project_id='g1'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(name, "Updated game");
        drop(reopened);
        assert_eq!(fs::read(&source).unwrap(), original);
        let mut stale = changes();
        if let ReviewCorrection::UserDisabled { before, .. } = &mut stale[0] {
            *before = true;
        }
        let second = parent.join("should-not-exist.sqlite3");
        assert!(
            publish_disposable_fixture_copy(&source, &second, "", "NewKey123!", &stale,).is_err()
        );
        assert!(!second.exists());
        assert_eq!(fs::read_dir(&parent).unwrap().count(), 1);
        assert_eq!(fs::read(&source).unwrap(), original);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[test]
    #[ignore = "requires Python 3.11 and real sqlcipher3 DB-API runtime"]
    fn cross_runtime_published_fixture_python_open() {
        use std::io::Write;
        use std::process::{Command, Stdio};

        let source = fixture(false);
        let original = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let target = parent.join("real-published-fixture.sqlite3");
        let report =
            publish_disposable_fixture_copy(&source, &target, "", "NewKey123!", &[]).unwrap();
        assert!(report.destination_created && report.encrypted_destination_verified);
        let repo = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .parent()
            .unwrap();
        let python = r#"
import sys
sys.path.insert(0, sys.argv[1] + "/server")
from alpha_sqlcipher_runtime import open_alpha_database, AlphaDatabaseOpenError
values = sys.stdin.buffer.read().split(b"\0")
assert len(values) == 3 and values[-1] == b""
database, key = [v.decode("utf-8") for v in values[:-1]]
db = open_alpha_database(database, key_provider=lambda: key)
assert db.execute("SELECT name,hex(payload) FROM records WHERE id=1").fetchone() == ("first", "00FF")
assert db.execute("PRAGMA user_version").fetchone() == (17,)
assert db.execute("PRAGMA quick_check").fetchone() == ("ok",)
db.close()
try:
    open_alpha_database(database, key_provider=lambda: "WrongKey123!")
except AlphaDatabaseOpenError:
    pass
else:
    raise AssertionError("wrong key accepted")
print("published_fixture_runtime_verified")
"#;
        let mut child = Command::new("python")
            .arg("-B")
            .arg("-c")
            .arg(python)
            .arg(repo)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("Python 3.11 must be installed for fixture acceptance");
        {
            let mut stdin = child.stdin.take().unwrap();
            let target_text = target.to_string_lossy().to_string();
            for value in [target_text.as_str(), "NewKey123!"] {
                stdin.write_all(value.as_bytes()).unwrap();
                stdin.write_all(&[0]).unwrap();
            }
        }
        let output = child.wait_with_output().unwrap();
        assert!(
            output.status.success(),
            "Python could not reopen the published fixture (output redacted)"
        );
        assert_eq!(
            String::from_utf8(output.stdout).unwrap().trim(),
            "published_fixture_runtime_verified"
        );
        assert_eq!(fs::read(&source).unwrap(), original);
        assert_eq!(fs::read_dir(&parent).unwrap().count(), 1);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[test]
    fn verified_stage_flush_requires_regular_file_and_preserves_bytes() {
        let parent = target_volume_fixture();
        let staged = parent.join("stage.sqlite3");
        let bytes = b"verified-fixture-data";
        fs::write(&staged, bytes).unwrap();
        sync_verified_ciphertext_stage(&staged).unwrap();
        assert_eq!(fs::read(&staged).unwrap(), bytes);
        assert!(sync_verified_ciphertext_stage(&parent).is_err());
        assert!(sync_verified_ciphertext_stage(&parent.join("missing")).is_err());
        #[cfg(unix)]
        {
            let alias = parent.join("alias.sqlite3");
            std::os::unix::fs::symlink(&staged, &alias).unwrap();
            assert!(sync_verified_ciphertext_stage(&alias).is_err());
            fs::remove_file(alias).unwrap();
        }
        assert_eq!(fs::read(&staged).unwrap(), bytes);
        fs::remove_dir_all(parent).unwrap();
    }

    #[test]
    fn destination_volume_rehearsal_uses_target_parent_and_removes_all_scratch() {
        let source = fixture(false);
        let original = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let target = parent.join("encrypted-migration.sqlite3");
        let proof = rehearse_encrypted_test_copy_on_destination_volume(
            &source,
            &target,
            "",
            "NewKey123!",
            &[],
        )
        .unwrap();
        assert!(proof.atomic_temporary_publication_verified);
        assert!(proof.full_disk_copy_verified && proof.temporary_files_removed);
        assert!(!proof.destination_created && !proof.execution_enabled);
        assert!(!target.exists());
        assert!(fs::read_dir(&parent).unwrap().next().is_none());
        assert_eq!(fs::read(&source).unwrap(), original);
        fs::remove_dir(parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[test]
    fn destination_volume_rehearsal_rejects_occupied_and_missing_targets() {
        let source = fixture(false);
        let original = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let occupied = parent.join("occupied.sqlite3");
        fs::write(&occupied, b"do not overwrite").unwrap();
        assert!(rehearse_encrypted_test_copy_on_destination_volume(
            &source,
            &occupied,
            "",
            "NewKey123!",
            &[],
        )
        .is_err());
        assert_eq!(fs::read(&occupied).unwrap(), b"do not overwrite");
        assert!(rehearse_encrypted_test_copy_on_destination_volume(
            &source,
            &parent.join("missing").join("new.sqlite3"),
            "",
            "NewKey123!",
            &[],
        )
        .is_err());
        assert_eq!(fs::read_dir(&parent).unwrap().count(), 1);
        assert_eq!(fs::read(&source).unwrap(), original);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn destination_volume_rehearsal_rejects_symlink_destination_parent() {
        let source = fixture(false);
        let parent = target_volume_fixture();
        let alias = parent.with_extension("symlink");
        std::os::unix::fs::symlink(&parent, &alias).unwrap();
        assert!(rehearse_encrypted_test_copy_on_destination_volume(
            &source,
            &alias.join("new.sqlite3"),
            "",
            "NewKey123!",
            &[],
        )
        .is_err());
        assert!(fs::read_dir(&parent).unwrap().next().is_none());
        fs::remove_file(alias).unwrap();
        fs::remove_dir(parent).unwrap();
        fs::remove_file(source).unwrap();
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
            assert!(rehearse_encrypted_test_copy(&path, existing, next, &[]).is_err());
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
    fn editable_alpha_fixture(encrypted: bool) -> PathBuf {
        let path = fixture(encrypted);
        {
            let db = Connection::open(&path).unwrap();
            if encrypted {
                db.pragma_update(None, "key", "ExistingKey9!").unwrap();
            }
            db.execute_batch(
                "CREATE TABLE alpha_invites(invitation_hash TEXT,user_id TEXT,expires_at INTEGER,redeemed INTEGER,revoked INTEGER);
                 CREATE TABLE alpha_users(user_id TEXT PRIMARY KEY,disabled INTEGER);
                 INSERT INTO alpha_users VALUES('alice',0);
                 CREATE TABLE alpha_agents(agent_id TEXT,user_id TEXT,disabled INTEGER);
                 INSERT INTO alpha_agents VALUES('a1','alice',0);
                 CREATE TABLE alpha_sessions(token_hash TEXT,user_id TEXT,expires_at INTEGER,revoked INTEGER);
                 CREATE TABLE alpha_jobs(job_id TEXT,user_id TEXT,agent_id TEXT,idempotency_key TEXT,action TEXT);
                 CREATE TABLE alpha_passwords(user_id TEXT,salt BLOB,password_hash BLOB);
                 CREATE TABLE alpha_agent_grants(agent_id TEXT,grantee_user_id TEXT,action TEXT,revoked INTEGER);
                 CREATE TABLE sec01_host_effect_definitions(host_id TEXT,effect_id TEXT,description TEXT,enabled INTEGER);
                 INSERT INTO sec01_host_effect_definitions VALUES('h1','e1','Original effect',1);
                 CREATE TABLE alpha_game_projects(project_id TEXT,host_id TEXT,owner_id TEXT,name TEXT,repository_root TEXT,job_attachments_root TEXT,output_root TEXT,settings_revision INTEGER);
                 INSERT INTO alpha_game_projects VALUES('g1','h1','alice','Original game','/tmp/game','/tmp/input','/tmp/out',7);
                 CREATE TABLE alpha_git_profiles(host_id TEXT,profile_id TEXT,owner_id TEXT,label TEXT,auth_method TEXT,git_executable TEXT,author_name TEXT,author_email TEXT);
                 INSERT INTO alpha_git_profiles VALUES('h1','p1','alice','Personal','local','git','Alice','alice@example.test');"
            ).unwrap();
        }
        path
    }

    fn changes() -> Vec<ReviewCorrection> {
        use crate::migration_dry_run::{GamePathField, GitProfileField};
        vec![
            ReviewCorrection::UserDisabled {
                user_id: "alice".into(),
                before: false,
                after: true,
            },
            ReviewCorrection::AgentDisabled {
                agent_id: "a1".into(),
                user_id: "alice".into(),
                before: false,
                after: true,
            },
            ReviewCorrection::EffectEnabled {
                host_id: "h1".into(),
                effect_id: "e1".into(),
                before: true,
                after: false,
            },
            ReviewCorrection::GameName {
                project_id: "g1".into(),
                before: "Original game".into(),
                after: "Updated game".into(),
            },
            ReviewCorrection::EffectDescription {
                host_id: "h1".into(),
                effect_id: "e1".into(),
                before: "Original effect".into(),
                after: "Updated effect".into(),
            },
            ReviewCorrection::GamePath {
                project_id: "g1".into(),
                field: GamePathField::RepositoryRoot,
                before: "/tmp/game".into(),
                after: "/tmp/updated-game".into(),
            },
            ReviewCorrection::GitProfileText {
                host_id: "h1".into(),
                profile_id: "p1".into(),
                owner_id: "alice".into(),
                field: GitProfileField::AuthorName,
                before: "Alice".into(),
                after: "Alice Changed".into(),
            },
        ]
    }

    #[test]
    fn verified_staged_edits_roundtrip_in_encrypted_temp_db_without_touching_source() {
        for encrypted in [false, true] {
            let path = editable_alpha_fixture(encrypted);
            let before = fs::read(&path).unwrap();
            let key = if encrypted { "ExistingKey9!" } else { "" };
            let proof = rehearse_encrypted_test_copy(&path, key, "NewKey123!", &changes()).unwrap();
            assert_eq!(proof.staged_changes_verified, 7);
            assert!(proof.staged_values_match_ciphertext && proof.full_disk_copy_verified);
            assert!(proof.temporary_files_removed && proof.wrong_key_rejected);
            assert!(proof.atomic_temporary_publication_verified);
            assert!(!proof.destination_created && !proof.encrypted_destination_verified);
            assert_eq!(fs::read(&path).unwrap(), before);
            fs::remove_file(path).unwrap();
        }
    }

    #[test]
    fn stale_or_duplicate_staged_edits_are_rejected_before_disk_export() {
        let path = editable_alpha_fixture(false);
        let before = fs::read(&path).unwrap();
        let mut stale = changes();
        if let ReviewCorrection::UserDisabled { before, .. } = &mut stale[0] {
            *before = true;
        }
        assert!(rehearse_encrypted_test_copy(&path, "", "NewKey123!", &stale).is_err());
        let mut duplicate = changes();
        duplicate.push(changes()[0].clone());
        assert!(rehearse_encrypted_test_copy(&path, "", "NewKey123!", &duplicate).is_err());
        assert_eq!(fs::read(&path).unwrap(), before);
        fs::remove_file(path).unwrap();
    }
    #[test]
    fn source_triggers_block_encrypted_disk_edits_without_mutation() {
        let path = editable_alpha_fixture(false);
        {
            let db = Connection::open(&path).unwrap();
            db.execute_batch(
                "CREATE TRIGGER audit_user_disabled AFTER UPDATE ON alpha_users
                 BEGIN UPDATE alpha_users SET disabled=NEW.disabled WHERE user_id=NEW.user_id; END;"
            ).unwrap();
        }
        let before = fs::read(&path).unwrap();
        assert!(rehearse_encrypted_test_copy(&path, "", "NewKey123!", &changes()).is_err());
        assert_eq!(fs::read(&path).unwrap(), before);
        fs::remove_file(path).unwrap();
    }
    /// Cross-implementation acceptance: the exact SQLCipher ciphertext written
    /// by the Rust export code must be usable for real Alpha transactions by
    /// the pinned Python runtime. Secrets travel over a child-process pipe,
    /// never via command-line arguments, the environment or debug output.
    ///
    /// Ignored in the default Rust suite because it needs Python 3.11 and the
    /// separately locked sqlcipher3 wheel. Explicitly enabled by the existing
    /// three-OS installer CI job after installing that wheel.
    #[test]
    #[ignore = "requires Python 3.11 and real sqlcipher3 DB-API runtime"]
    fn cross_runtime_sqlcipher_export_python_first_run() {
        use std::io::Write;
        use std::process::{Command, Stdio};

        let source = Connection::open_in_memory().unwrap();
        source
            .execute_batch(
                "CREATE TABLE original_fixture(
                    id INTEGER PRIMARY KEY, note TEXT NOT NULL, payload BLOB);
                 INSERT INTO original_fixture VALUES(1,'source preserved',x'00ff');
                 PRAGMA user_version=0; PRAGMA application_id=0;",
            )
            .unwrap();
        let temporary = PrivateTempDir::create(&source).unwrap();
        let stage = temporary.path.join("rust-export-for-python.sqlite3");
        let cipher_password = "RustCrossRuntime9!'cipher";
        let login_password = "IndependentLoginTest9!password";
        export(&source, &stage, cipher_password).unwrap();
        let mut header = [0_u8; 16];
        fs::File::open(&stage)
            .unwrap()
            .read_exact(&mut header)
            .unwrap();
        assert_ne!(&header, b"SQLite format 3\0");

        let repo = Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .parent()
            .unwrap();
        let python = r#"
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]) / "server"))
from alpha_sqlcipher_runtime import open_alpha_database, AlphaDatabaseOpenError
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy

values = sys.stdin.buffer.read().split(b"\0")
assert len(values) == 4 and values[-1] == b"", "invalid test-only pipe"
database, cipher_key, login_key = [v.decode("utf-8") for v in values[:-1]]
assert cipher_key != login_key
def unlock():
    return cipher_key

runtime = open_alpha_database(database, key_provider=unlock)
assert runtime.execute("SELECT note,hex(payload) FROM original_fixture").fetchone() == (
    "source preserved", "00FF")
runtime.close()
try:
    open_alpha_database(database, key_provider=lambda: "WrongKey123!")
except AlphaDatabaseOpenError:
    pass
else:
    raise AssertionError("wrong SQLCipher password accepted")

store = AlphaAuthStore(database, sqlcipher_key_provider=unlock)
policy = HostCommitPolicy(IntegratedAlphaAdmission(store))
provision = policy.provision_first_run_local_host_admin_trusted(
    "host.cross-runtime", login_key, login_user_id="mingleadmin")
assert (provision.state, provision.reason) == (
    "created", "first_run_local_host_admin_created")
repeat = policy.provision_first_run_local_host_admin_trusted(
    "host.cross-runtime", login_key, login_user_id="mingleadmin")
assert repeat.state == "denied"
session = store.login("mingleadmin", login_key)
assert session
assert store.login("mingleadmin", cipher_key) is None
assert store.principal("Bearer " + session).user_id == "mingleadmin"
with store._tx() as db:
    assert db.execute("SELECT count(*) FROM alpha_invites").fetchone() == (0,)
    assert db.execute("SELECT count(*) FROM sec01_host_owners").fetchone() == (1,)
    assert policy._admin(db, "host.cross-runtime", "mingleadmin")
    assert not policy._admin(db, "host.other", "mingleadmin")
print("python_runtime_verified")
"#;
        let mut child = Command::new("python")
            .arg("-B")
            .arg("-c")
            .arg(python)
            .arg(repo)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("Python 3.11 must be installed for cross-runtime acceptance");
        {
            let mut stdin = child.stdin.take().unwrap();
            let stage_text = stage.to_string_lossy().to_string();
            for value in [stage_text.as_str(), cipher_password, login_password] {
                stdin.write_all(value.as_bytes()).unwrap();
                stdin.write_all(&[0]).unwrap();
            }
        }
        let output = child.wait_with_output().unwrap();
        assert!(
            output.status.success(),
            "Python SQLCipher cross-runtime acceptance failed (output redacted)"
        );
        assert_eq!(
            String::from_utf8(output.stdout).unwrap().trim(),
            "python_runtime_verified"
        );

        let reopened =
            Connection::open_with_flags(&stage, OpenFlags::SQLITE_OPEN_READ_ONLY).unwrap();
        reopened
            .pragma_update(None, "key", cipher_password)
            .unwrap();
        let (login, host): (String, String) = reopened
            .query_row(
                "SELECT u.user_id,o.host_id
                 FROM alpha_users u
                 JOIN sec01_host_owners o ON o.owner_id=u.user_id",
                [],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .unwrap();
        assert_eq!(login, "mingleadmin");
        assert_eq!(host, "host.cross-runtime");
        let old_fixture: Vec<u8> = reopened
            .query_row(
                "SELECT payload FROM original_fixture WHERE id=1",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(old_fixture, vec![0, 255]);
        let integrity: String = reopened
            .query_row("PRAGMA quick_check", [], |row| row.get(0))
            .unwrap();
        assert_eq!(integrity, "ok");
        drop(reopened);
        temporary.remove().unwrap();
        assert!(!stage.exists());
    }
}
