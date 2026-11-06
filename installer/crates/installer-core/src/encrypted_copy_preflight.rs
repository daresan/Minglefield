//! Isolated on-disk SQLCipher export rehearsal. No final destination writes.
use crate::database_password::validate_new_database_password;
use crate::legacy_alpha_constraints::add_selected_registered_schema_objects;
use crate::migration_destination::{
    preview_migration_destination, same_underlying_file, PinnedDestinationParent,
};
use crate::recovery_receipt::{
    fixture_recovery_receipt, inspect_reserved_destination_recovery_receipt,
    reserve_destination_recovery_receipt, sync_published_destination_parent, ReceiptInspection,
};
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
    pub added_schema_objects: Vec<String>,
    pub recovery_operation_id: Option<String>,
    pub recovery_receipt_directory_synced: bool,
    pub destination_directory_synced: bool,
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

/// Private checkpoints for deterministic tests of the existing encrypted
/// staging/publication path. Production callers can only reach this path
/// through the wrapper's no-op callback; no user input selects a checkpoint.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum CopyCheckpoint {
    BeforeStaging,
    AfterEncryptedExport,
    BeforeFinalPublication,
    AfterReceiptReserved,
    AfterFinalPublication,
    DuringFinalVerification,
}

fn rehearse_encrypted_test_copy_under(
    source_path: &Path,
    existing_password: &str,
    new_password: &str,
    corrections: &[ReviewCorrection],
    staging_parent: Option<&Path>,
    publication_target: Option<&Path>,
) -> Result<EncryptedTestCopy, String> {
    rehearse_encrypted_test_copy_under_with_schema(
        source_path,
        existing_password,
        new_password,
        corrections,
        staging_parent,
        publication_target,
        &[],
    )
}

fn rehearse_encrypted_test_copy_under_with_schema(
    source_path: &Path,
    existing_password: &str,
    new_password: &str,
    corrections: &[ReviewCorrection],
    staging_parent: Option<&Path>,
    publication_target: Option<&Path>,
    schema_additions: &[String],
) -> Result<EncryptedTestCopy, String> {
    rehearse_encrypted_test_copy_under_with_checkpoints(
        source_path,
        existing_password,
        new_password,
        corrections,
        staging_parent,
        publication_target,
        schema_additions,
        None,
        |_| Ok(()),
    )
}

// Keep authorization, source/target keys, and staged adjustments separate
// at this security boundary rather than silently introducing defaults.
#[allow(clippy::too_many_arguments)]
fn rehearse_encrypted_test_copy_under_with_checkpoints(
    source_path: &Path,
    existing_password: &str,
    new_password: &str,
    corrections: &[ReviewCorrection],
    staging_parent: Option<&Path>,
    publication_target: Option<&Path>,
    schema_additions: &[String],
    receipt_backup: Option<&Path>,
    mut checkpoint: impl FnMut(CopyCheckpoint) -> Result<(), String>,
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
    // Add only operator-selected, registered missing objects on the isolated
    // corrected RAM copy. SQLite performs the actual constraint validation;
    // the entire selection is rolled back on any DDL or integrity failure.
    let added_schema_objects =
        add_selected_registered_schema_objects(&mut corrected_memory, schema_additions)?
            .added_objects;
    checkpoint(CopyCheckpoint::BeforeStaging)?;
    let private = match staging_parent {
        Some(parent) => PrivateTempDir::create_under(&source, parent)?,
        None => PrivateTempDir::create(&source)?,
    };
    let staged = private.path.join("temporary-encrypted.sqlite3");
    export(&corrected_memory, &staged, new_password)?;
    checkpoint(CopyCheckpoint::AfterEncryptedExport)?;
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
    let mut recovery_operation_id = None;
    let mut recovery_receipt_directory_synced = false;
    let mut destination_directory_synced = false;
    let fixture_created = if let Some(target) = publication_target {
        checkpoint(CopyCheckpoint::BeforeFinalPublication)?;
        if let Some(backup) = receipt_backup {
            // This verified and flushed ciphertext is the exact inode later
            // published under the final name. Reserve a unique operation
            // slot BEFORE linking it. An earlier operation (even interrupted
            // before publication) must prevent an unannounced second try.
            let record = fixture_recovery_receipt(
                source_path, backup, target, &staged, corrections, schema_additions,
            )?;
            let reserved = reserve_destination_recovery_receipt(target, &record)?;
            if inspect_reserved_destination_recovery_receipt(
                source_path, backup, target, &staged, corrections, schema_additions,
            )? != ReceiptInspection::Matched {
                return Err("Recovery receipt failed immediate staged-file verification".into());
            }
            recovery_operation_id = Some(reserved.operation_id);
            recovery_receipt_directory_synced = reserved.directory_entry_synced;
            checkpoint(CopyCheckpoint::AfterReceiptReserved)?;
        }
        fs::hard_link(&staged, target)
            .map_err(|_| "Cannot exclusively publish fixture ciphertext")?;
        if receipt_backup.is_some() {
            destination_directory_synced = sync_published_destination_parent(target)?;
        }
        checkpoint(CopyCheckpoint::AfterFinalPublication)?;
        let published_fixture =
            Connection::open_with_flags(target, OpenFlags::SQLITE_OPEN_READ_ONLY)
                .map_err(|_| "Cannot reopen published fixture ciphertext")?;
        published_fixture
            .pragma_update(None, "key", new_password)
            .map_err(|_| "Cannot unlock published fixture ciphertext")?;
        checkpoint(CopyCheckpoint::DuringFinalVerification)?;
        let final_fidelity = verify_snapshot_equality(&corrected_memory, &published_fixture)?;
        if final_fidelity != fidelity || !final_fidelity.values_verified {
            return Err("Published fixture data differs from verified stage".to_owned());
        }
        drop(published_fixture);
        if let Some(backup) = receipt_backup {
            if inspect_reserved_destination_recovery_receipt(
                source_path, backup, target, target, corrections, schema_additions,
            )? != ReceiptInspection::Matched {
                return Err("Published ciphertext does not match reserved recovery record".into());
            }
        }
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
        added_schema_objects,
        recovery_operation_id,
        recovery_receipt_directory_synced,
        destination_directory_synced,
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
    execute_reviewed_encrypted_copy_with_schema(
        source_path,
        destination_path,
        backup_path,
        existing_password,
        new_password,
        corrections,
        &[],
        confirmation,
    )
}

/// Operator-selected schema additions are confined to the same verified
/// isolated encrypted-copy path. The original/backup remain byte-preserved.
// Keep authorization, source/target keys, and staged adjustments separate
// at this security boundary rather than silently introducing defaults.
#[allow(clippy::too_many_arguments)]
pub fn execute_reviewed_encrypted_copy_with_schema(
    source_path: &Path,
    destination_path: &Path,
    backup_path: &Path,
    existing_password: &str,
    new_password: &str,
    corrections: &[ReviewCorrection],
    schema_additions: &[String],
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
    let backup = fs::canonicalize(backup_path).map_err(|_| "Cannot identify backup file")?;
    if backup == source || backup == before.destination || same_underlying_file(source, &backup)? {
        return Err("Backup must be a physically separate file from source and destination".into());
    }
    // A backup is not considered verified because a checkbox was selected.
    // Compare actual data, schema and metadata using independent read-only
    // snapshots. This is a local Alpha safety gate, not proof of physical
    // media independence or adversarial path-race resistance.
    let (source_db, source_info) = open_inspected_snapshot(source, existing_password)
        .map_err(|_| "Cannot verify original source for backup comparison")?;
    let (backup_db, backup_info) = open_inspected_snapshot(&backup, existing_password)
        .map_err(|_| "Cannot open verified source backup")?;
    if !source_info.integrity_ok
        || !backup_info.integrity_ok
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
    let parent = before
        .destination
        .parent()
        .ok_or("Destination parent unavailable")?;
    let guard = PinnedDestinationParent::open(&before)?;
    // Explicitly request a durable output filename only after consent and
    // the independent source/backup comparison; use the proven same-volume
    // encrypted staging and exclusive hard-link copy.
    let report = rehearse_encrypted_test_copy_under_with_checkpoints(
        source,
        existing_password,
        new_password,
        corrections,
        Some(parent),
        Some(&before.destination),
        schema_additions,
        Some(&backup),
        |_| Ok(()),
    )?;
    guard.revalidate_identity()?;
    if !report.destination_created
        || !report.encrypted_destination_verified
        || !report.full_disk_copy_verified
        || !report.temporary_files_removed
    {
        return Err("Experimental encrypted copy was not verified".into());
    }
    Ok(report)
}

/// M2.07: read-only classification of an interrupted Alpha-copy attempt.
/// A matching existing file proves only byte-value/schema equivalence at
/// inspection time, NOT installer provenance, recovery authorization, or
/// durable transaction completion. Never delete/replace a target from this.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EncryptedCopyRecoveryState {
    DestinationAbsent,
    ExistingMatchesExpected,
    ExistingUnverified,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct EncryptedCopyRecoveryAssessment {
    pub state: EncryptedCopyRecoveryState,
    pub automatic_retry_permitted: bool,
    pub automatic_delete_permitted: bool,
}

pub fn inspect_encrypted_copy_recovery(
    source_path: &Path,
    destination_path: &Path,
    source_password: &str,
    destination_password: &str,
    corrections: &[ReviewCorrection],
) -> Result<EncryptedCopyRecoveryAssessment, String> {
    // Require a fresh, integrity-checked read-only source snapshot. The
    // expected result is produced in private memory using existing typed
    // correction validation; source and target files are never modified.
    let (source, inspected) = open_inspected_snapshot(source_path, source_password)
        .map_err(|_| "Cannot inspect original source for recovery")?;
    if !inspected.integrity_ok || inspected.foreign_key_violations != 0 {
        return Err("Recovery source failed integrity verification".into());
    }
    let source_key = if inspected.source_encrypted {
        source_password
    } else {
        ""
    };
    let (mut expected, fidelity) = create_verified_memory_copy(&source, source_key)?;
    if !fidelity.values_verified {
        return Err("Cannot verify recovery source snapshot".into());
    }
    if !corrections.is_empty() {
        validate_alpha_schema(&inspected)?;
        let original_counts = table_counts(&source, &inspected)?;
        apply_staged_to_isolated_copy(
            &mut expected,
            &inspected,
            &original_counts,
            corrections,
            true,
        )?;
    }
    let state = match fs::symlink_metadata(destination_path) {
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
            EncryptedCopyRecoveryState::DestinationAbsent
        }
        Err(_) => return Err("Cannot inspect recovery destination".into()),
        Ok(meta) if meta.file_type().is_symlink() || !meta.is_file() => {
            EncryptedCopyRecoveryState::ExistingUnverified
        }
        Ok(_) => {
            let distinct = !same_underlying_file(source_path, destination_path)?;
            let mut header = [0_u8; 16];
            let ciphertext_header = fs::File::open(destination_path)
                .and_then(|mut file| file.read_exact(&mut header))
                .is_ok()
                && &header != b"SQLite format 3\0";
            let verified = if distinct && ciphertext_header && !destination_password.is_empty() {
                let check = (|| -> Result<(), String> {
                    let copy = Connection::open_with_flags(
                        destination_path,
                        OpenFlags::SQLITE_OPEN_READ_ONLY,
                    )
                    .map_err(|_| "Cannot read existing recovery destination")?;
                    copy.pragma_update(None, "key", destination_password)
                        .map_err(|_| "Cannot unlock existing recovery destination")?;
                    verify_snapshot_equality(&expected, &copy)?;
                    Ok(())
                })();
                check.is_ok()
            } else {
                false
            };
            if verified {
                EncryptedCopyRecoveryState::ExistingMatchesExpected
            } else {
                EncryptedCopyRecoveryState::ExistingUnverified
            }
        }
    };
    Ok(EncryptedCopyRecoveryAssessment {
        state,
        automatic_retry_permitted: false,
        automatic_delete_permitted: false,
    })
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
    fn recovery_distinguishes_absent_matching_and_unverified_destinations_without_writes() {
        let source = fixture(false);
        let original = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let target = parent.join("recovery-target.sqlite3");
        let inspect = |password: &str| {
            inspect_encrypted_copy_recovery(&source, &target, "", password, &[]).unwrap()
        };
        let absent = inspect("NewKey123!");
        assert_eq!(absent.state, EncryptedCopyRecoveryState::DestinationAbsent);
        assert!(!absent.automatic_retry_permitted && !absent.automatic_delete_permitted);

        fs::write(&target, b"existing-user-file").unwrap();
        let collision = inspect("NewKey123!");
        assert_eq!(
            collision.state,
            EncryptedCopyRecoveryState::ExistingUnverified
        );
        assert_eq!(fs::read(&target).unwrap(), b"existing-user-file");
        fs::remove_file(&target).unwrap();

        // A structurally identical plaintext copy is not a verified
        // encrypted destination even if its values and schema match.
        fs::copy(&source, &target).unwrap();
        assert_eq!(
            inspect("NewKey123!").state,
            EncryptedCopyRecoveryState::ExistingUnverified
        );
        fs::remove_file(&target).unwrap();

        let proof =
            publish_disposable_fixture_copy(&source, &target, "", "NewKey123!", &[]).unwrap();
        assert!(proof.encrypted_destination_verified);
        let verified = inspect("NewKey123!");
        assert_eq!(
            verified.state,
            EncryptedCopyRecoveryState::ExistingMatchesExpected
        );
        assert!(!verified.automatic_retry_permitted && !verified.automatic_delete_permitted);
        let wrong_key = inspect("WrongKey123!");
        assert_eq!(
            wrong_key.state,
            EncryptedCopyRecoveryState::ExistingUnverified
        );
        assert_eq!(fs::read(&source).unwrap(), original);
        assert_eq!(fs::read_dir(&parent).unwrap().count(), 1);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[test]
    fn recovery_detects_a_published_copy_that_does_not_match_staged_changes() {
        let source = editable_alpha_fixture(false);
        let original = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let target = parent.join("recovery-edits.sqlite3");
        publish_disposable_fixture_copy(&source, &target, "", "NewKey123!", &changes()).unwrap();
        let with_edits =
            inspect_encrypted_copy_recovery(&source, &target, "", "NewKey123!", &changes())
                .unwrap();
        assert_eq!(
            with_edits.state,
            EncryptedCopyRecoveryState::ExistingMatchesExpected
        );
        let without_edits =
            inspect_encrypted_copy_recovery(&source, &target, "", "NewKey123!", &[]).unwrap();
        assert_eq!(
            without_edits.state,
            EncryptedCopyRecoveryState::ExistingUnverified
        );
        assert!(!without_edits.automatic_delete_permitted);
        assert_eq!(fs::read(&source).unwrap(), original);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    /// A separate test-binary process uses the existing SQLCipher stage/
    /// publication implementation and exits without unwinding at one private
    /// checkpoint. This worker is inert in ordinary test runs.
    /// Fresh test process: read the independently persisted recovery record
    /// and the real SQLCipher destination without relying on the writer's
    /// in-memory state or any Minglefield application permission.
    #[test]
    fn m207_recovery_receipt_fresh_process_reader() {
        use crate::recovery_receipt::{inspect_fixture_recovery_receipt, ReceiptInspection};

        let root = match std::env::var_os("MINGLEFIELD_M207_RECEIPT_PARENT") {
            Some(value) => PathBuf::from(value),
            None => return,
        };
        let parent = fs::canonicalize(&root).unwrap();
        let temp = fs::canonicalize(std::env::temp_dir()).unwrap();
        assert_eq!(parent.parent(), Some(temp.as_path()));
        assert!(parent
            .file_name()
            .unwrap()
            .to_string_lossy()
            .starts_with("minglefield-target-volume-"));
        let operation_id = std::env::var("MINGLEFIELD_M207_RECEIPT_OPERATION")
            .expect("Missing test-only recovery operation ID");
        let source = parent.join("source.sqlite3");
        let backup = parent.join("backup.sqlite3");
        let target = parent.join("destination.sqlite3");
        let filename = crate::recovery_receipt::recovery_receipt_filename(&operation_id)
            .expect("Invalid test-only operation ID");
        let receipt_path = parent.join(filename);
        let classification = inspect_fixture_recovery_receipt(
            &receipt_path,
            &operation_id,
            &source,
            &backup,
            &target,
            &target,
            &[],
            &[],
        )
        .unwrap();
        assert_eq!(classification, ReceiptInspection::Matched);
        let content =
            inspect_encrypted_copy_recovery(&source, &target, "", "NewKey123!", &[]).unwrap();
        assert_eq!(
            content.state,
            EncryptedCopyRecoveryState::ExistingMatchesExpected
        );
        assert!(!content.automatic_retry_permitted);
        assert!(!content.automatic_delete_permitted);
    }

    #[test]
    fn m207_published_sqlcipher_receipt_survives_fresh_process_validation() {
        use crate::recovery_receipt::{
            fixture_recovery_receipt, inspect_fixture_recovery_receipt,
            write_fixture_recovery_receipt, ReceiptInspection,
        };
        use std::io::Write;
        use std::process::{Command, Stdio};

        let root = target_volume_fixture();
        let source = root.join("source.sqlite3");
        let backup = root.join("backup.sqlite3");
        let target = root.join("destination.sqlite3");
        let original_fixture = fixture(false);
        fs::copy(&original_fixture, &source).unwrap();
        fs::remove_file(original_fixture).unwrap();
        fs::copy(&source, &backup).unwrap();
        let source_bytes = fs::read(&source).unwrap();
        let proof =
            publish_disposable_fixture_copy(&source, &target, "", "NewKey123!", &[]).unwrap();
        assert!(proof.encrypted_destination_verified);
        let receipt =
            fixture_recovery_receipt(&source, &backup, &target, &target, &[], &[]).unwrap();
        let receipt_path = write_fixture_recovery_receipt(&root, &receipt).unwrap();
        let result = Command::new(std::env::current_exe().unwrap())
            .arg("--exact")
            .arg("encrypted_copy_preflight::tests::m207_recovery_receipt_fresh_process_reader")
            .arg("--nocapture")
            .env("MINGLEFIELD_M207_RECEIPT_PARENT", &root)
            .env("MINGLEFIELD_M207_RECEIPT_OPERATION", &receipt.operation_id)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .expect("Cannot launch independent receipt reader");
        assert!(
            result.success(),
            "Independent recovery receipt reader rejected the fixture"
        );
        assert_eq!(fs::read(&source).unwrap(), source_bytes);
        assert_eq!(fs::read(&backup).unwrap(), source_bytes);
        assert!(write_fixture_recovery_receipt(&root, &receipt).is_err());

        // A matching database is not sufficient if the stored operation
        // receipt has been altered. Never infer recovery authorization.
        fs::OpenOptions::new()
            .append(true)
            .open(&receipt_path)
            .unwrap()
            .write_all(b"tampered=yes\n")
            .unwrap();
        assert_eq!(
            inspect_fixture_recovery_receipt(
                &receipt_path,
                &receipt.operation_id,
                &source,
                &backup,
                &target,
                &target,
                &[],
                &[],
            )
            .unwrap(),
            ReceiptInspection::Unverified,
        );
        assert_eq!(fs::read(&source).unwrap(), source_bytes);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn m207_abrupt_exit_worker() {
        use std::process;

        let parent = match std::env::var_os("MINGLEFIELD_M207_TEST_CHILD_PARENT") {
            Some(value) => PathBuf::from(value),
            None => return,
        };
        let fault = std::env::var("MINGLEFIELD_M207_TEST_CHILD_CHECKPOINT")
            .expect("A fixture checkpoint must be provided");
        // Constrain this test-only subprocess to a freshly created disposable
        // directory. Never accept source/target paths from a real installation.
        let temp = fs::canonicalize(std::env::temp_dir()).unwrap();
        let parent = fs::canonicalize(&parent).unwrap();
        assert_eq!(parent.parent(), Some(temp.as_path()));
        assert!(parent
            .file_name()
            .unwrap()
            .to_string_lossy()
            .starts_with("minglefield-target-volume-"));
        let source = parent.join("source.sqlite3");
        let target = parent.join("target.sqlite3");
        assert!(source.is_file());
        assert!(!target.exists());
        let selected = match fault.as_str() {
            "before_staging" => CopyCheckpoint::BeforeStaging,
            "after_export" => CopyCheckpoint::AfterEncryptedExport,
            "before_publish" => CopyCheckpoint::BeforeFinalPublication,
            "after_publish" => CopyCheckpoint::AfterFinalPublication,
            "after_receipt" => CopyCheckpoint::AfterReceiptReserved,
            "final_verify" => CopyCheckpoint::DuringFinalVerification,
            _ => panic!("Unknown test-only interruption checkpoint"),
        };
        // No errors or panic: process::exit closes OS handles but does not
        // run destructors, unlike the earlier controlled interruption tests.
        let _ = rehearse_encrypted_test_copy_under_with_checkpoints(
            &source,
            "",
            "NewKey123!",
            &[],
            Some(&parent),
            Some(&target),
            &[],
            None,
            |point| {
                if point == selected {
                    process::exit(77);
                }
                Ok(())
            },
        );
        panic!("Selected process-termination checkpoint was not reached");
    }

    #[test]
    fn m207_real_subprocess_exit_and_fresh_process_recovery() {
        use std::process::{Command, Stdio};

        let cases = [
            ("before_staging", false, false),
            ("after_export", false, true),
            ("before_publish", false, true),
            ("after_publish", true, true),
            ("final_verify", true, true),
        ];
        let worker_binary = std::env::current_exe().unwrap();
        for (checkpoint, should_publish, should_leave_stage) in cases {
            let parent = target_volume_fixture();
            let original_fixture = fixture(false);
            let source = parent.join("source.sqlite3");
            fs::copy(&original_fixture, &source).unwrap();
            fs::remove_file(original_fixture).unwrap();
            let source_bytes = fs::read(&source).unwrap();
            let target = parent.join("target.sqlite3");
            let sentinel = parent.join("untouched-preexisting.dat");
            fs::write(&sentinel, b"do not mutate").unwrap();
            let exit = Command::new(&worker_binary)
                .arg("--exact")
                .arg("encrypted_copy_preflight::tests::m207_abrupt_exit_worker")
                .arg("--nocapture")
                .env("MINGLEFIELD_M207_TEST_CHILD_PARENT", &parent)
                .env("MINGLEFIELD_M207_TEST_CHILD_CHECKPOINT", checkpoint)
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status()
                .expect("Could not start the isolated fixture test process");
            assert_eq!(
                exit.code(),
                Some(77),
                "{checkpoint}: no actual process exit"
            );
            assert_eq!(fs::read(&source).unwrap(), source_bytes, "{checkpoint}");
            assert_eq!(
                fs::read(&sentinel).unwrap(),
                b"do not mutate",
                "{checkpoint}"
            );
            assert_eq!(target.exists(), should_publish, "{checkpoint}");
            let stages: Vec<_> = fs::read_dir(&parent)
                .unwrap()
                .map(|entry| entry.unwrap().path())
                .filter(|path| {
                    path.file_name()
                        .unwrap()
                        .to_string_lossy()
                        .starts_with("minglefield-stage-")
                })
                .collect();
            assert_eq!(
                stages.len(),
                usize::from(should_leave_stage),
                "{checkpoint}: actual process exit must not pretend RAII cleanup ran"
            );
            for path in &stages {
                assert!(path.is_dir(), "{checkpoint}");
            }
            // This executes in the test parent, after the child is gone:
            // the recovery reader is newly opened and may never mutate an
            // existing target, delete staging, or enable an automatic retry.
            let status =
                inspect_encrypted_copy_recovery(&source, &target, "", "NewKey123!", &[]).unwrap();
            assert_eq!(
                status.state,
                if should_publish {
                    EncryptedCopyRecoveryState::ExistingMatchesExpected
                } else {
                    EncryptedCopyRecoveryState::DestinationAbsent
                },
                "{checkpoint}"
            );
            assert!(!status.automatic_retry_permitted, "{checkpoint}");
            assert!(!status.automatic_delete_permitted, "{checkpoint}");
            if should_publish {
                let bad_key =
                    inspect_encrypted_copy_recovery(&source, &target, "", "WrongKey123!", &[])
                        .unwrap();
                assert_eq!(
                    bad_key.state,
                    EncryptedCopyRecoveryState::ExistingUnverified,
                    "{checkpoint}"
                );
            }
            assert_eq!(fs::read(&source).unwrap(), source_bytes, "{checkpoint}");
            assert_eq!(fs::read(&sentinel).unwrap(), b"do not mutate");
            // Test-owned files ONLY: explicit cleanup after observing the
            // real post-exit staging residue. No production sweep exists.
            fs::remove_dir_all(&parent).unwrap();
        }
    }

    #[test]
    fn injected_interruption_at_every_publication_boundary_keeps_source_and_occupied_files() {
        // Returning an error models a controlled process interruption and
        // exercises RAII cleanup; it is NOT a power-loss durability test.
        for fault in [
            CopyCheckpoint::BeforeStaging,
            CopyCheckpoint::AfterEncryptedExport,
            CopyCheckpoint::BeforeFinalPublication,
            CopyCheckpoint::AfterFinalPublication,
            CopyCheckpoint::DuringFinalVerification,
        ] {
            let source = fixture(false);
            let source_bytes = fs::read(&source).unwrap();
            let parent = target_volume_fixture();
            let destination = parent.join("verified-new-target.sqlite3");
            let untouched = parent.join("unrelated-preexisting.txt");
            fs::write(&untouched, b"untouched-existing-file").unwrap();
            let mut intercepted = 0;
            let result = rehearse_encrypted_test_copy_under_with_checkpoints(
                &source,
                "",
                "NewKey123!",
                &[],
                Some(&parent),
                Some(&destination),
                &[],
                None,
                |point| {
                    if point == fault {
                        intercepted += 1;
                        return Err("synthetic interruption before completion".to_owned());
                    }
                    Ok(())
                },
            );
            assert!(result.is_err(), "{fault:?}");
            assert_eq!(intercepted, 1, "{fault:?}");
            assert_eq!(fs::read(&source).unwrap(), source_bytes, "{fault:?}");
            assert_eq!(
                fs::read(&untouched).unwrap(),
                b"untouched-existing-file",
                "{fault:?}"
            );
            let published = matches!(
                fault,
                CopyCheckpoint::AfterFinalPublication | CopyCheckpoint::DuringFinalVerification
            );
            assert_eq!(destination.exists(), published, "{fault:?}");
            assert_eq!(
                fs::read_dir(&parent).unwrap().count(),
                if published { 2 } else { 1 },
                "No private staging remains after a caught interruption: {fault:?}"
            );
            let recovery =
                inspect_encrypted_copy_recovery(&source, &destination, "", "NewKey123!", &[])
                    .unwrap();
            assert_eq!(
                recovery.state,
                if published {
                    EncryptedCopyRecoveryState::ExistingMatchesExpected
                } else {
                    EncryptedCopyRecoveryState::DestinationAbsent
                },
                "{fault:?}"
            );
            assert!(!recovery.automatic_retry_permitted);
            assert!(!recovery.automatic_delete_permitted);
            fs::remove_dir_all(parent).unwrap();
            fs::remove_file(source).unwrap();
        }
    }

    #[test]
    fn injected_failure_with_staged_edits_leaves_complete_ciphertext_not_partial_target() {
        let source = editable_alpha_fixture(false);
        let original = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let destination = parent.join("edited-target.sqlite3");
        let changes = changes();
        assert!(rehearse_encrypted_test_copy_under_with_checkpoints(
            &source,
            "",
            "NewKey123!",
            &changes,
            Some(&parent),
            Some(&destination),
            &[],
            None,
            |point| {
                if point == CopyCheckpoint::DuringFinalVerification {
                    Err("synthetic post-link interruption".to_owned())
                } else {
                    Ok(())
                }
            },
        )
        .is_err());
        assert!(destination.is_file());
        let correct =
            inspect_encrypted_copy_recovery(&source, &destination, "", "NewKey123!", &changes)
                .unwrap();
        assert_eq!(
            correct.state,
            EncryptedCopyRecoveryState::ExistingMatchesExpected
        );
        let stale =
            inspect_encrypted_copy_recovery(&source, &destination, "", "NewKey123!", &[]).unwrap();
        assert_eq!(stale.state, EncryptedCopyRecoveryState::ExistingUnverified);
        assert!(!correct.automatic_delete_permitted);
        assert!(!stale.automatic_retry_permitted);
        assert_eq!(fs::read(&source).unwrap(), original);
        assert_eq!(fs::read_dir(&parent).unwrap().count(), 1);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[test]
    fn selected_missing_index_is_written_only_to_new_encrypted_destination() {
        let source_parent = target_volume_fixture();
        let source = source_parent.join("registered-alpha.sqlite3");
        crate::legacy_alpha_constraints::create_registered_alpha_test_file(&source).unwrap();
        {
            let db = Connection::open(&source).unwrap();
            db.execute_batch("DROP INDEX uq_game_install_one_active_project;")
                .unwrap();
        }
        let source_bytes = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let backup = parent.join("source-backup.sqlite3");
        let target = parent.join("encrypted-with-schema.sqlite3");
        fs::copy(&source, &backup).unwrap();
        let wanted = vec!["uq_game_install_one_active_project".to_owned()];
        let proof = execute_reviewed_encrypted_copy_with_schema(
            &source,
            &target,
            &backup,
            "",
            "NewKey123!",
            &[],
            &wanted,
            EXPERIMENTAL_COPY_CONFIRMATION,
        )
        .unwrap();
        assert!(proof.destination_created);
        assert_eq!(proof.added_schema_objects, wanted);
        assert_eq!(proof.schema_entries_checked, 59);
        let output =
            Connection::open_with_flags(&target, OpenFlags::SQLITE_OPEN_READ_ONLY).unwrap();
        output.pragma_update(None, "key", "NewKey123!").unwrap();
        let found: i64 = output
            .query_row(
                "SELECT count(*) FROM sqlite_schema WHERE name='uq_game_install_one_active_project'",
                [], |r| r.get(0),
            ).unwrap();
        assert_eq!(found, 1);
        drop(output);
        assert_eq!(fs::read(&source).unwrap(), source_bytes);
        assert_eq!(fs::read(&backup).unwrap(), source_bytes);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_dir_all(source_parent).unwrap();
    }

    #[test]
    fn conflicting_selected_schema_additions_refuse_publication_and_leave_backup_untouched() {
        let source_parent = target_volume_fixture();
        let source = source_parent.join("registered-alpha.sqlite3");
        crate::legacy_alpha_constraints::create_registered_alpha_test_file(&source).unwrap();
        {
            let db = Connection::open(&source).unwrap();
            db.execute_batch(
                "DROP INDEX uq_game_install_one_active_project;
                 INSERT INTO sec01_game_install_journal
                 (operation_id,host_id,owner_id,project_id,state,plan_sha256)
                 VALUES
                 ('a','host-one','owner','game-one','prepared','digest-one'),
                 ('b','host-one','owner','game-one','prepared','digest-two');",
            )
            .unwrap();
        }
        let parent = target_volume_fixture();
        let backup = parent.join("source-backup.sqlite3");
        let target = parent.join("should-not-exist.sqlite3");
        fs::copy(&source, &backup).unwrap();
        let before = fs::read(&source).unwrap();
        assert!(execute_reviewed_encrypted_copy_with_schema(
            &source,
            &target,
            &backup,
            "",
            "NewKey123!",
            &[],
            &["uq_game_install_one_active_project".to_owned()],
            EXPERIMENTAL_COPY_CONFIRMATION,
        )
        .is_err());
        assert!(!target.exists());
        assert_eq!(fs::read(&source).unwrap(), before);
        assert_eq!(fs::read(&backup).unwrap(), before);
        assert_eq!(fs::read_dir(&parent).unwrap().count(), 1);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_dir_all(source_parent).unwrap();
    }

    #[test]
    fn experimental_publication_requires_real_backup_and_explicit_consent() {
        let source = editable_alpha_fixture(false);
        let original = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let backup = parent.join("separate-verified-backup.sqlite3");
        let destination = parent.join("approved-encrypted.sqlite3");
        let args = |backup: &Path, confirmation: &str| {
            execute_reviewed_encrypted_copy(
                &source,
                &destination,
                backup,
                "",
                "NewKey123!",
                &changes(),
                confirmation,
            )
        };
        assert!(args(&backup, EXPERIMENTAL_COPY_CONFIRMATION).is_err());
        assert!(!destination.exists());
        fs::copy(&source, &backup).unwrap();
        assert!(args(&backup, "YES").is_err());
        assert!(!destination.exists());

        // An existing hard link is not an independent backup.
        let alias = parent.join("source-hardlink.sqlite3");
        fs::hard_link(&source, &alias).unwrap();
        assert!(args(&alias, EXPERIMENTAL_COPY_CONFIRMATION).is_err());
        fs::remove_file(&alias).unwrap();

        let result = args(&backup, EXPERIMENTAL_COPY_CONFIRMATION).unwrap();
        assert!(result.destination_created && result.encrypted_destination_verified);
        assert!(!result.execution_enabled);
        assert_eq!(result.staged_changes_verified, 7);
        assert!(result.temporary_files_removed && result.full_disk_copy_verified);
        assert_eq!(fs::read(&source).unwrap(), original);
        assert!(args(&backup, EXPERIMENTAL_COPY_CONFIRMATION).is_err());
        assert!(destination.exists());
        assert_eq!(fs::read_dir(&parent).unwrap().count(), 3);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[test]
    fn experimental_publication_accepts_separate_encrypted_source_backup() {
        let source = fixture(true);
        let source_bytes = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let backup = parent.join("separate-encrypted-backup.sqlite3");
        let destination = parent.join("rekeyed-source.sqlite3");
        fs::copy(&source, &backup).unwrap();
        assert!(execute_reviewed_encrypted_copy(
            &source,
            &destination,
            &backup,
            "WrongExistingKey",
            "NewKey123!",
            &[],
            EXPERIMENTAL_COPY_CONFIRMATION,
        )
        .is_err());
        assert!(!destination.exists());
        let result = execute_reviewed_encrypted_copy(
            &source,
            &destination,
            &backup,
            "ExistingKey9!",
            "NewKey123!",
            &[],
            EXPERIMENTAL_COPY_CONFIRMATION,
        )
        .unwrap();
        assert!(result.destination_created && result.encrypted_destination_verified);
        assert!(!result.execution_enabled);
        assert_eq!(fs::read(&source).unwrap(), source_bytes);
        assert_eq!(fs::read(&backup).unwrap(), source_bytes);
        assert_eq!(fs::read_dir(&parent).unwrap().count(), 3);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[test]
    fn experimental_publication_rejects_outdated_or_nonmatching_backup() {
        let source = editable_alpha_fixture(false);
        let original = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let backup = parent.join("backup.sqlite3");
        let destination = parent.join("new-encrypted.sqlite3");
        fs::copy(&source, &backup).unwrap();
        let db = Connection::open(&backup).unwrap();
        db.execute(
            "UPDATE alpha_users SET disabled=1 WHERE user_id='alice'",
            [],
        )
        .unwrap();
        drop(db);
        assert!(execute_reviewed_encrypted_copy(
            &source,
            &destination,
            &backup,
            "",
            "NewKey123!",
            &[],
            EXPERIMENTAL_COPY_CONFIRMATION,
        )
        .is_err());
        assert!(!destination.exists());
        assert_eq!(fs::read(&source).unwrap(), original);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_file(source).unwrap();
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
