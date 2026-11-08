//! Isolated on-disk SQLCipher export rehearsal. No final destination writes.
use crate::database_password::validate_new_database_password;
use crate::legacy_alpha_constraints::add_selected_registered_schema_objects;
use crate::migration_destination::{
    preview_migration_destination, same_underlying_file, PinnedDestinationParent,
};
use crate::migration_dry_run::{
    apply_staged_to_isolated_copy, table_counts, validate_alpha_schema, ReviewCorrection,
};
use crate::recovery_receipt::{
    fixture_recovery_receipt, inspect_reserved_destination_recovery_receipt,
    read_reserved_destination_operation_id, reserve_destination_recovery_receipt,
    sync_published_destination_parent, ReceiptInspection,
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
                source_path,
                backup,
                target,
                &staged,
                corrections,
                schema_additions,
            )?;
            let reserved = reserve_destination_recovery_receipt(target, &record)?;
            if inspect_reserved_destination_recovery_receipt(
                source_path,
                backup,
                target,
                &staged,
                corrections,
                schema_additions,
            )? != ReceiptInspection::Matched
            {
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
                source_path,
                backup,
                target,
                target,
                corrections,
                schema_additions,
            )? != ReceiptInspection::Matched
            {
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

/// Normal end-user installation: a single consented SQLCipher destination,
/// NOT the experimental copy/recovery fixture protocol.
///
/// The selected original database is only opened read-only. Reviewed edits
/// and selected schema additions are applied on an independently verified
/// memory copy, then exported straight to the requested NEW encrypted file.
/// Stale recovery receipts, abandoned test staging directories and earlier
/// source-backup artifacts are not consulted and cannot reserve this name.
///
/// Crashes/replay and concurrent Setup Manager processes are outside this
/// product installer operation's scope; a normally reported failure cleans
/// up only the destination that this exact call created. An existing target
/// is NEVER silently overwritten; it is handled separately by the caller.
fn reviewed_installer_memory(
    source_path: &Path,
    existing_password: &str,
    corrections: &[ReviewCorrection],
    schema_additions: &[String],
) -> Result<(Connection, Vec<String>), String> {
    let (original, inspection) = open_inspected_snapshot(source_path, existing_password)
        .map_err(|_| "Cannot inspect original installation source")?;
    if !inspection.integrity_ok || inspection.foreign_key_violations != 0 {
        return Err("Installation source failed integrity verification".into());
    }
    let source_key = if inspection.source_encrypted {
        existing_password
    } else {
        ""
    };
    let (mut memory, source_proof) = create_verified_memory_copy(&original, source_key)?;
    if !source_proof.values_verified {
        return Err("Source memory snapshot did not verify".into());
    }
    if !corrections.is_empty() {
        validate_alpha_schema(&inspection)?;
        let counts = table_counts(&original, &inspection)?;
        apply_staged_to_isolated_copy(&mut memory, &inspection, &counts, corrections, true)?;
    }
    let additions =
        add_selected_registered_schema_objects(&mut memory, schema_additions)?.added_objects;
    Ok((memory, additions))
}

/// Publish an already reviewed in-memory snapshot under a NEW, unoccupied
/// filename. Used by both new installations and explicitly approved
/// replacements. No scratch SQLCipher database or recovery receipt is made.
fn publish_installer_memory(
    preview_source: &Path,
    destination_path: &Path,
    new_password: &str,
    memory: &Connection,
    corrections_count: usize,
    additions: Vec<String>,
) -> Result<EncryptedTestCopy, String> {
    crate::migration_destination::create_missing_destination_parent(destination_path)?;
    let preview = preview_migration_destination(preview_source, destination_path)
        .map_err(|_| "Installer encrypted destination is unavailable")?;
    let guard = PinnedDestinationParent::open(&preview)?;
    let created = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&preview.destination)
        .map_err(|_| "Selected database destination already exists or is unavailable")?;
    drop(created);
    let outcome = (|| -> Result<EncryptedTestCopy, String> {
        export(memory, &preview.destination, new_password)?;
        let mut header = [0u8; 16];
        fs::File::open(&preview.destination)
            .map_err(|_| "Cannot reopen installed SQLCipher destination")?
            .read_exact(&mut header)
            .map_err(|_| "Installed SQLCipher destination header is truncated")?;
        if &header == b"SQLite format 3\0" {
            return Err("Installed destination has an unencrypted SQLite header".into());
        }
        let verified =
            Connection::open_with_flags(&preview.destination, OpenFlags::SQLITE_OPEN_READ_ONLY)
                .map_err(|_| "Cannot reopen installed SQLCipher data")?;
        verified
            .pragma_update(None, "key", new_password)
            .map_err(|_| "Cannot unlock installed encrypted database")?;
        let fidelity = verify_snapshot_equality(memory, &verified)?;
        if !fidelity.values_verified {
            return Err("Installed encrypted database differs from reviewed memory copy".into());
        }
        drop(verified);
        sync_verified_ciphertext_stage(&preview.destination)?;
        guard.revalidate_identity()?;
        Ok(EncryptedTestCopy {
            full_source_verified: true,
            ciphertext_header_verified: true,
            wrong_key_rejected: false,
            atomic_temporary_publication_verified: false,
            full_disk_copy_verified: true,
            staged_changes_verified: corrections_count,
            staged_values_match_ciphertext: true,
            rows_checked: fidelity.rows_checked,
            tables_checked: fidelity.tables_checked,
            schema_entries_checked: fidelity.schema_entries_checked,
            added_schema_objects: additions,
            recovery_operation_id: None,
            recovery_receipt_directory_synced: false,
            destination_directory_synced: false,
            temporary_files_removed: true,
            destination_created: true,
            encrypted_destination_verified: true,
            execution_enabled: true,
        })
    })();
    if outcome.is_err() {
        // Remove only the newly created failed output, never the original
        // source, an archived previous target or old test artifacts.
        let _ = fs::remove_file(&preview.destination);
    }
    outcome
}

pub fn export_installer_encrypted_database(
    source_path: &Path,
    destination_path: &Path,
    existing_password: &str,
    new_password: &str,
    corrections: &[ReviewCorrection],
    schema_additions: &[String],
) -> Result<EncryptedTestCopy, String> {
    validate_new_database_password(new_password)
        .map_err(|_| "A strong new SQLCipher password is required")?;
    if !existing_password.is_empty() && existing_password == new_password {
        return Err("New SQLCipher key must differ from the existing key".into());
    }
    // The original must remain untouched. Require a distinct unused output
    // for normal migration; replacement uses the separate approved path.
    let _ = preview_migration_destination(source_path, destination_path)
        .map_err(|_| "Installer encrypted destination is unavailable")?;
    let (memory, additions) = reviewed_installer_memory(
        source_path,
        existing_password,
        corrections,
        schema_additions,
    )?;
    publish_installer_memory(
        source_path,
        destination_path,
        new_password,
        &memory,
        corrections.len(),
        additions,
    )
}

/// After explicit existing-target confirmation, preserve the previous
/// selected file by RENAMING it to a unique named archive, not by making a
/// second temporary disk copy. Then export the reviewed memory snapshot
/// directly at the requested destination. The normal error path restores
/// the original name. No crash-recovery or concurrent-installer machinery.
///
/// This also supports a user explicitly choosing the SAME source and target
/// path: the source is fully loaded and independently checked in RAM before
/// any rename, and the original is retained as the named previous version.
pub fn replace_installer_encrypted_database(
    source_path: &Path,
    destination_path: &Path,
    existing_password: &str,
    new_password: &str,
    corrections: &[ReviewCorrection],
    schema_additions: &[String],
) -> Result<EncryptedTestCopy, String> {
    validate_new_database_password(new_password)
        .map_err(|_| "A strong SQLCipher password is required")?;
    let target_meta = fs::symlink_metadata(destination_path)
        .map_err(|_| "Selected existing database destination is unavailable")?;
    if target_meta.file_type().is_symlink() || !target_meta.is_file() {
        return Err("Selected database destination must be a regular file".into());
    }
    let source_id =
        fs::canonicalize(source_path).map_err(|_| "Cannot identify selected original database")?;
    let target_id = fs::canonicalize(destination_path)
        .map_err(|_| "Cannot identify existing destination database")?;
    let same_source =
        source_id == target_id || same_underlying_file(source_path, destination_path)?;

    // All source reads, source-key verification, typed edits and DDL changes
    // finish before touching the occupied destination pathname.
    let (memory, additions) = reviewed_installer_memory(
        source_path,
        existing_password,
        corrections,
        schema_additions,
    )?;
    let parent = destination_path
        .parent()
        .ok_or("Destination parent unavailable")?;
    let file_name = destination_path
        .file_name()
        .ok_or("Destination filename unavailable")?
        .to_string_lossy();
    let mut archive = None;
    for _ in 0..8 {
        let id: String = Connection::open_in_memory()
            .and_then(|db| db.query_row("SELECT lower(hex(randomblob(16)))", [], |row| row.get(0)))
            .map_err(|_| "Cannot choose previous database archive name")?;
        let candidate = parent.join(format!("{file_name}.minglefield-previous-{id}.sqlite3"));
        match fs::symlink_metadata(&candidate) {
            Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
                archive = Some(candidate);
                break;
            }
            Ok(_) => {}
            Err(_) => return Err("Cannot inspect previous database archive name".into()),
        }
    }
    let archive = archive.ok_or("Cannot choose unique previous database archive name")?;
    fs::rename(destination_path, &archive)
        .map_err(|_| "Cannot preserve existing database as previous version")?;
    let preview_source = if same_source { &archive } else { source_path };
    let outcome = publish_installer_memory(
        preview_source,
        destination_path,
        new_password,
        &memory,
        corrections.len(),
        additions,
    );
    match outcome {
        Ok(proof) => Ok(proof),
        Err(reason) => {
            // Restore only on a normal, reported installation error. If the
            // new path exists, it was created by publish_installer_memory.
            if fs::symlink_metadata(destination_path).is_ok()
                && fs::remove_file(destination_path).is_err()
            {
                return Err(format!(
                    "{reason}; previous database preserved at {} (destination could not be cleared)",
                    archive.display()
                ));
            }
            fs::rename(&archive, destination_path).map_err(|_| {
                format!(
                    "{reason}; previous database preserved at {} (could not restore original name)",
                    archive.display()
                )
            })?;
            Err(reason)
        }
    }
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
    crate::migration_destination::create_missing_destination_parent(&before.destination)?;
    // Newly created parents must still resolve to the same approved path;
    // an existing symlink or occupied destination is never accepted.
    let checked = preview_migration_destination(source, destination_path)
        .map_err(|_| "Migration destination changed before publication")?;
    if checked.destination != before.destination {
        return Err("Migration destination path changed".into());
    }
    let guard = PinnedDestinationParent::open(&checked)?;
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
        || report.recovery_operation_id.is_none()
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
    inspect_encrypted_copy_recovery_with_schema(
        source_path,
        destination_path,
        source_password,
        destination_password,
        corrections,
        &[],
    )
}

/// Read-only expected-copy comparison including optional reviewed schema
/// additions. An exact data match still confers no recovery authorization.
pub fn inspect_encrypted_copy_recovery_with_schema(
    source_path: &Path,
    destination_path: &Path,
    source_password: &str,
    destination_password: &str,
    corrections: &[ReviewCorrection],
    schema_additions: &[String],
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
    if !schema_additions.is_empty() {
        add_selected_registered_schema_objects(&mut expected, schema_additions)?;
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

/// Read-only operator-facing interpretation of an interrupted Alpha copy.
/// A source/backup/receipt/ciphertext match is evidence of consistency, not
/// proof of who created the files or a permission to restart or delete them.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InterruptedEncryptedCopyState {
    NoRecordedOperation,
    UnrecordedDestination,
    ReservationWithoutDestination,
    PublishedContentMatches,
    ManualReviewRequired,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InterruptedEncryptedCopyAssessment {
    pub state: InterruptedEncryptedCopyState,
    pub operation_id: Option<String>,
    pub automatic_retry_permitted: bool,
    pub automatic_delete_permitted: bool,
    pub installation_enabled: bool,
}

/// This function never creates, writes, deletes, renames or replays files.
/// A malformed sidecar or any mismatch produces ManualReviewRequired.
#[allow(clippy::too_many_arguments)]
pub fn inspect_interrupted_encrypted_copy(
    source_path: &Path,
    backup_path: &Path,
    destination_path: &Path,
    source_password: &str,
    destination_password: &str,
    corrections: &[ReviewCorrection],
    schema_additions: &[String],
) -> Result<InterruptedEncryptedCopyAssessment, String> {
    use InterruptedEncryptedCopyState as S;

    let result = |state, operation_id| InterruptedEncryptedCopyAssessment {
        state,
        operation_id,
        automatic_retry_permitted: false,
        automatic_delete_permitted: false,
        installation_enabled: false,
    };
    // A name collision is not a clean state. Refuse symlinks or directories
    // rather than assuming the final target is a trustworthy ciphertext.
    let target_present = match fs::symlink_metadata(destination_path) {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => false,
        Ok(_) => true,
        Err(_) => return Err("Cannot inspect interrupted encrypted target".into()),
    };
    let operation_id = match read_reserved_destination_operation_id(destination_path) {
        Ok(value) => value,
        Err(_) => return Ok(result(S::ManualReviewRequired, None)),
    };
    if operation_id.is_none() {
        return Ok(result(
            if target_present {
                S::UnrecordedDestination
            } else {
                S::NoRecordedOperation
            },
            None,
        ));
    }
    if !target_present {
        // No claim about the surviving private staging or original file
        // contents: this is a reservation only, not a completed migration.
        return Ok(result(S::ReservationWithoutDestination, operation_id));
    }
    let verified = (|| -> Result<(), String> {
        let (source_db, source_info) = open_inspected_snapshot(source_path, source_password)
            .map_err(|_| "Cannot reopen original source for recovery")?;
        let (backup_db, backup_info) = open_inspected_snapshot(backup_path, source_password)
            .map_err(|_| "Cannot reopen independent backup for recovery")?;
        if !source_info.integrity_ok
            || !backup_info.integrity_ok
            || source_info.foreign_key_violations != 0
            || backup_info.foreign_key_violations != 0
            || same_underlying_file(source_path, backup_path)?
        {
            return Err("Recovery source or backup is invalid".into());
        }
        if !verify_snapshot_equality(&source_db, &backup_db)?.values_verified {
            return Err("Recovery backup no longer matches source".into());
        }
        if inspect_reserved_destination_recovery_receipt(
            source_path,
            backup_path,
            destination_path,
            destination_path,
            corrections,
            schema_additions,
        )? != ReceiptInspection::Matched
        {
            return Err("Recovery destination does not match saved operation receipt".into());
        }
        let destination = inspect_encrypted_copy_recovery_with_schema(
            source_path,
            destination_path,
            source_password,
            destination_password,
            corrections,
            schema_additions,
        )?;
        if destination.state != EncryptedCopyRecoveryState::ExistingMatchesExpected {
            return Err("Recovery SQLCipher contents differ from expected source".into());
        }
        Ok(())
    })();
    Ok(result(
        if verified.is_ok() {
            S::PublishedContentMatches
        } else {
            S::ManualReviewRequired
        },
        operation_id,
    ))
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
    fn product_install_exports_one_db_ignoring_old_receipts_and_stage_garbage() {
        let source = fixture(false);
        let original = fs::read(&source).unwrap();
        let output_dir = source.with_extension("product-migration");
        fs::create_dir(&output_dir).unwrap();
        let target = output_dir.join("minglefield.sqlite3");

        // These are residues from OLD installations, not active operations.
        // The normal installer must never read, delete or honor them.
        let prior_receipt =
            crate::recovery_receipt::reserved_destination_receipt_path(&target).unwrap();
        fs::write(&prior_receipt, b"unrelated old test receipt").unwrap();
        fs::create_dir(output_dir.join("minglefield-stage-old")).unwrap();
        fs::create_dir(output_dir.join(".minglefield-source-backup-old")).unwrap();

        let report = export_installer_encrypted_database(
            &source,
            &target,
            "",
            "StrongCipherPass123!",
            &[],
            &[],
        )
        .unwrap();
        assert!(report.destination_created && report.encrypted_destination_verified);
        assert!(report.full_disk_copy_verified && report.staged_values_match_ciphertext);
        assert!(report.recovery_operation_id.is_none());
        assert_eq!(fs::read(&source).unwrap(), original);
        assert_eq!(
            fs::read(&prior_receipt).unwrap(),
            b"unrelated old test receipt"
        );

        let original_db = Connection::open(&source).unwrap();
        let output = Connection::open(&target).unwrap();
        output
            .pragma_update(None, "key", "StrongCipherPass123!")
            .unwrap();
        let data = verify_snapshot_equality(&original_db, &output).unwrap();
        assert!(data.values_verified);
        drop(output);
        drop(original_db);
        let before = fs::read(&target).unwrap();
        assert!(export_installer_encrypted_database(
            &source,
            &target,
            "",
            "StrongCipherPass123!",
            &[],
            &[]
        )
        .is_err());
        assert_eq!(fs::read(&target).unwrap(), before);
        let entries: Vec<_> = fs::read_dir(&output_dir)
            .unwrap()
            .map(|entry| entry.unwrap().file_name())
            .collect();
        assert_eq!(entries.len(), 4); // output DB + three untouched old artifacts
        fs::remove_dir_all(output_dir).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[test]
    fn consented_existing_target_is_archived_and_new_ciphertext_uses_same_name() {
        let source = fixture(false);
        let parent = target_volume_fixture();
        let target = parent.join("minglefield.sqlite3");
        {
            let db = Connection::open(&target).unwrap();
            db.pragma_update(None, "key", "PreviousPassword123!")
                .unwrap();
            db.execute_batch(
                "CREATE TABLE old_user_data(notes TEXT);
                              INSERT INTO old_user_data VALUES('retain as archive');",
            )
            .unwrap();
        }
        let original_target = fs::read(&target).unwrap();
        let original_source = fs::read(&source).unwrap();
        let report = replace_installer_encrypted_database(
            &source,
            &target,
            "",
            "NewCipherPassword123!",
            &[],
            &[],
        )
        .unwrap();
        assert!(report.destination_created && report.encrypted_destination_verified);
        assert_eq!(fs::read(&source).unwrap(), original_source);
        let archived = fs::read_dir(&parent)
            .unwrap()
            .filter_map(Result::ok)
            .map(|entry| entry.path())
            .filter(|path| path.to_string_lossy().contains(".minglefield-previous-"))
            .collect::<Vec<_>>();
        assert_eq!(archived.len(), 1);
        assert_eq!(fs::read(&archived[0]).unwrap(), original_target);
        let old = Connection::open(&archived[0]).unwrap();
        old.pragma_update(None, "key", "PreviousPassword123!")
            .unwrap();
        assert_eq!(
            old.query_row("SELECT notes FROM old_user_data", [], |row| row
                .get::<_, String>(0))
                .unwrap(),
            "retain as archive"
        );
        drop(old);
        let new = Connection::open(&target).unwrap();
        new.pragma_update(None, "key", "NewCipherPassword123!")
            .unwrap();
        let old_source = Connection::open(&source).unwrap();
        assert!(
            verify_snapshot_equality(&old_source, &new)
                .unwrap()
                .values_verified
        );
        drop(new);
        drop(old_source);
        assert_eq!(fs::read_dir(&parent).unwrap().count(), 2);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[test]
    fn consented_same_source_and_target_path_exports_from_memory_and_preserves_original() {
        let parent = target_volume_fixture();
        let target = parent.join("legacy-source-and-target.sqlite3");
        {
            let source = Connection::open(&target).unwrap();
            source
                .execute_batch(
                    "CREATE TABLE olddata(user_id TEXT PRIMARY KEY);
                                INSERT INTO olddata VALUES('user.daniel');",
                )
                .unwrap();
        }
        let original = fs::read(&target).unwrap();
        let report = replace_installer_encrypted_database(
            &target,
            &target,
            "",
            "NewCipherPassword123!",
            &[],
            &[],
        )
        .unwrap();
        assert!(report.destination_created && report.encrypted_destination_verified);
        let archived = fs::read_dir(&parent)
            .unwrap()
            .filter_map(Result::ok)
            .map(|entry| entry.path())
            .filter(|path| path.to_string_lossy().contains(".minglefield-previous-"))
            .collect::<Vec<_>>();
        assert_eq!(archived.len(), 1);
        assert_eq!(fs::read(&archived[0]).unwrap(), original);
        let new = Connection::open(&target).unwrap();
        new.pragma_update(None, "key", "NewCipherPassword123!")
            .unwrap();
        assert_eq!(
            new.query_row("SELECT user_id FROM olddata", [], |row| row
                .get::<_, String>(0))
                .unwrap(),
            "user.daniel"
        );
        drop(new);
        assert_eq!(fs::read_dir(&parent).unwrap().count(), 2);
        fs::remove_dir_all(parent).unwrap();
    }

    #[test]
    fn product_install_applies_page_five_edits_and_schema_to_single_encrypted_db() {
        use crate::migration_dry_run::RawCell;
        let parent = target_volume_fixture();
        let source = parent.join("legacy.sqlite3");
        let dest = parent.join("minglefield.sqlite3");
        crate::legacy_alpha_constraints::create_registered_alpha_test_file(&source).unwrap();
        {
            let db = Connection::open(&source).unwrap();
            db.execute_batch(
                "DROP INDEX uq_game_install_one_active_project;
                 INSERT INTO alpha_users(user_id,disabled) VALUES('old-user',0);",
            )
            .unwrap();
        }
        let original_bytes = fs::read(&source).unwrap();
        let change = ReviewCorrection::FullRow {
            table: "alpha_users".into(),
            row_id: Some("1".into()),
            columns: vec!["user_id".into(), "disabled".into()],
            before: vec![
                RawCell {
                    kind: "text".into(),
                    value: Some("old-user".into()),
                },
                RawCell {
                    kind: "integer".into(),
                    value: Some("0".into()),
                },
            ],
            after: vec![
                RawCell {
                    kind: "text".into(),
                    value: Some("old-user".into()),
                },
                RawCell {
                    kind: "integer".into(),
                    value: Some("1".into()),
                },
            ],
        };
        let addition = vec!["uq_game_install_one_active_project".to_owned()];
        let report = export_installer_encrypted_database(
            &source,
            &dest,
            "",
            "NewCipherPassword123!",
            &[change],
            &addition,
        )
        .unwrap();
        assert_eq!(report.staged_changes_verified, 1);
        assert_eq!(report.added_schema_objects, addition);
        assert!(report.encrypted_destination_verified);
        assert_eq!(fs::read(&source).unwrap(), original_bytes);
        let db = Connection::open(&dest).unwrap();
        db.pragma_update(None, "key", "NewCipherPassword123!")
            .unwrap();
        let value: i64 = db
            .query_row(
                "SELECT disabled FROM alpha_users WHERE user_id='old-user'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(value, 1);
        let count: i64 = db.query_row(
            "SELECT count(*) FROM sqlite_schema WHERE name='uq_game_install_one_active_project'",
            [], |r| r.get(0),
        ).unwrap();
        assert_eq!(count, 1);
        drop(db);
        let entries: Vec<_> = fs::read_dir(&parent).unwrap().collect();
        assert_eq!(entries.len(), 2); // unchanged source + sole output DB
        fs::remove_dir_all(parent).unwrap();
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
    fn interrupted_copy_status_is_read_only_for_unknown_verified_and_tampered_states() {
        use crate::recovery_receipt::reserved_destination_receipt_path;
        use std::io::Write;

        let source = fixture(false);
        let before = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let backup = parent.join("backup.sqlite3");
        let destination = parent.join("encrypted-final.sqlite3");
        fs::copy(&source, &backup).unwrap();
        let check = |destination_password: &str| {
            inspect_interrupted_encrypted_copy(
                &source,
                &backup,
                &destination,
                "",
                destination_password,
                &[],
                &[],
            )
            .unwrap()
        };
        // A freshly restarted installer can inspect the destination/receipt
        // before the operator supplies either SQLCipher key or source backup.
        // This is only a provisional status, never content verification.
        let brief = || {
            inspect_interrupted_encrypted_copy(
                Path::new(""),
                Path::new(""),
                &destination,
                "",
                "",
                &[],
                &[],
            )
            .unwrap()
        };
        let absent = check("NewKey123!");
        assert_eq!(
            absent.state,
            InterruptedEncryptedCopyState::NoRecordedOperation
        );
        assert_eq!(
            brief().state,
            InterruptedEncryptedCopyState::NoRecordedOperation
        );
        assert!(!absent.automatic_retry_permitted && !absent.automatic_delete_permitted);
        fs::write(&destination, b"unrelated-occupied-file").unwrap();
        assert_eq!(
            check("NewKey123!").state,
            InterruptedEncryptedCopyState::UnrecordedDestination
        );
        assert_eq!(
            brief().state,
            InterruptedEncryptedCopyState::UnrecordedDestination
        );
        assert_eq!(fs::read(&destination).unwrap(), b"unrelated-occupied-file");
        fs::remove_file(&destination).unwrap();

        let proof = execute_reviewed_encrypted_copy(
            &source,
            &destination,
            &backup,
            "",
            "NewKey123!",
            &[],
            EXPERIMENTAL_COPY_CONFIRMATION,
        )
        .unwrap();
        assert!(proof.encrypted_destination_verified);
        let correct = check("NewKey123!");
        assert_eq!(
            correct.state,
            InterruptedEncryptedCopyState::PublishedContentMatches
        );
        assert_eq!(correct.operation_id, proof.recovery_operation_id);
        let unverified_brief = brief();
        assert_eq!(
            unverified_brief.state,
            InterruptedEncryptedCopyState::ManualReviewRequired
        );
        assert_eq!(unverified_brief.operation_id, correct.operation_id);
        assert!(!unverified_brief.automatic_retry_permitted);
        assert!(!unverified_brief.automatic_delete_permitted);
        assert!(!unverified_brief.installation_enabled);
        assert!(!correct.automatic_retry_permitted);
        assert!(!correct.automatic_delete_permitted);
        assert!(!correct.installation_enabled);
        assert_eq!(
            check("WrongNewKey123!").state,
            InterruptedEncryptedCopyState::ManualReviewRequired
        );
        fs::write(&backup, b"corrupted-backup").unwrap();
        assert_eq!(
            check("NewKey123!").state,
            InterruptedEncryptedCopyState::ManualReviewRequired
        );
        fs::copy(&source, &backup).unwrap();
        let receipt = reserved_destination_receipt_path(&destination).unwrap();
        fs::OpenOptions::new()
            .append(true)
            .open(&receipt)
            .unwrap()
            .write_all(b"unexpected=yes\n")
            .unwrap();
        let tampered = check("NewKey123!");
        assert_eq!(
            tampered.state,
            InterruptedEncryptedCopyState::ManualReviewRequired
        );
        assert_eq!(tampered.operation_id, None);
        assert_eq!(fs::read(&source).unwrap(), before);
        assert_eq!(fs::read(&backup).unwrap(), before);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[test]
    fn interrupted_copy_status_recognizes_receipt_without_target_and_blocks_retry() {
        let source = fixture(false);
        let original = fs::read(&source).unwrap();
        let parent = target_volume_fixture();
        let backup = parent.join("backup.sqlite3");
        let destination = parent.join("final.sqlite3");
        fs::copy(&source, &backup).unwrap();
        assert!(rehearse_encrypted_test_copy_under_with_checkpoints(
            &source,
            "",
            "NewKey123!",
            &[],
            Some(&parent),
            Some(&destination),
            &[],
            Some(&backup),
            |point| {
                if point == CopyCheckpoint::AfterReceiptReserved {
                    Err("injected interrupted receipt reservation".to_owned())
                } else {
                    Ok(())
                }
            },
        )
        .is_err());
        assert!(!destination.exists());
        let status = inspect_interrupted_encrypted_copy(
            &source,
            &backup,
            &destination,
            "",
            "NewKey123!",
            &[],
            &[],
        )
        .unwrap();
        assert_eq!(
            status.state,
            InterruptedEncryptedCopyState::ReservationWithoutDestination
        );
        assert!(status.operation_id.is_some());
        let without_passwords = inspect_interrupted_encrypted_copy(
            Path::new(""),
            Path::new(""),
            &destination,
            "",
            "",
            &[],
            &[],
        )
        .unwrap();
        assert_eq!(
            without_passwords.state,
            InterruptedEncryptedCopyState::ReservationWithoutDestination
        );
        assert_eq!(without_passwords.operation_id, status.operation_id);
        assert!(!without_passwords.automatic_retry_permitted);
        assert!(!without_passwords.automatic_delete_permitted);
        assert!(!status.automatic_retry_permitted);
        assert!(!status.automatic_delete_permitted);
        assert!(!status.installation_enabled);
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
        assert_eq!(fs::read(&backup).unwrap(), original);
        fs::remove_dir_all(parent).unwrap();
        fs::remove_file(source).unwrap();
    }

    #[test]
    fn interrupted_copy_status_verifies_selected_missing_schema_objects() {
        let parent = target_volume_fixture();
        let source = parent.join("registered-source.sqlite3");
        crate::legacy_alpha_constraints::create_registered_alpha_test_file(&source).unwrap();
        {
            let db = Connection::open(&source).unwrap();
            db.execute_batch("DROP INDEX uq_game_install_one_active_project;")
                .unwrap();
        }
        let backup = parent.join("backup.sqlite3");
        let target = parent.join("encrypted-with-selected-index.sqlite3");
        fs::copy(&source, &backup).unwrap();
        let selected = vec!["uq_game_install_one_active_project".to_owned()];
        let published = execute_reviewed_encrypted_copy_with_schema(
            &source,
            &target,
            &backup,
            "",
            "NewKey123!",
            &[],
            &selected,
            EXPERIMENTAL_COPY_CONFIRMATION,
        )
        .unwrap();
        assert_eq!(published.added_schema_objects, selected);
        let verified = inspect_interrupted_encrypted_copy(
            &source,
            &backup,
            &target,
            "",
            "NewKey123!",
            &[],
            &selected,
        )
        .unwrap();
        assert_eq!(
            verified.state,
            InterruptedEncryptedCopyState::PublishedContentMatches
        );
        assert_eq!(verified.operation_id, published.recovery_operation_id);
        let missing_selection = inspect_interrupted_encrypted_copy(
            &source,
            &backup,
            &target,
            "",
            "NewKey123!",
            &[],
            &[],
        )
        .unwrap();
        assert_eq!(
            missing_selection.state,
            InterruptedEncryptedCopyState::ManualReviewRequired
        );
        fs::remove_dir_all(parent).unwrap();
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
        let with_receipt = std::env::var("MINGLEFIELD_M207_WITH_RECEIPT").as_deref() == Ok("1");
        let backup = parent.join("backup.sqlite3");
        if with_receipt {
            assert!(backup.is_file());
        }
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
            if with_receipt {
                Some(backup.as_path())
            } else {
                None
            },
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
    fn m207_abrupt_exit_after_receipt_reservation_is_exclusively_classified() {
        use crate::recovery_receipt::{
            inspect_reserved_destination_recovery_receipt, reserved_destination_receipt_path,
            ReceiptInspection,
        };
        use std::process::{Command, Stdio};

        for (fault, final_expected) in [("after_receipt", false), ("after_publish", true)] {
            let parent = target_volume_fixture();
            let source = parent.join("source.sqlite3");
            let backup = parent.join("backup.sqlite3");
            let target = parent.join("target.sqlite3");
            let fixture_path = fixture(false);
            fs::copy(&fixture_path, &source).unwrap();
            fs::remove_file(fixture_path).unwrap();
            fs::copy(&source, &backup).unwrap();
            let original = fs::read(&source).unwrap();
            let worker = Command::new(std::env::current_exe().unwrap())
                .arg("--exact")
                .arg("encrypted_copy_preflight::tests::m207_abrupt_exit_worker")
                .arg("--nocapture")
                .env("MINGLEFIELD_M207_TEST_CHILD_PARENT", &parent)
                .env("MINGLEFIELD_M207_TEST_CHILD_CHECKPOINT", fault)
                .env("MINGLEFIELD_M207_WITH_RECEIPT", "1")
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status()
                .expect("Cannot launch recovery receipt interruption fixture worker");
            assert_eq!(worker.code(), Some(77), "{fault}");
            let receipt_path = reserved_destination_receipt_path(&target).unwrap();
            assert!(receipt_path.is_file(), "{fault}");
            assert_eq!(target.exists(), final_expected, "{fault}");
            assert_eq!(fs::read(&source).unwrap(), original, "{fault}");
            assert_eq!(fs::read(&backup).unwrap(), original, "{fault}");

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
            assert_eq!(stages.len(), 1, "{fault}");
            let expected_ciphertext = if final_expected {
                target.clone()
            } else {
                stages[0].join("temporary-encrypted.sqlite3")
            };
            assert_eq!(
                inspect_reserved_destination_recovery_receipt(
                    &source,
                    &backup,
                    &target,
                    &expected_ciphertext,
                    &[],
                    &[],
                )
                .unwrap(),
                ReceiptInspection::Matched,
                "{fault}"
            );
            // No final file after the receipt-only crash, but that does NOT
            // make the target available for a second operation.
            let separate = crate::recovery_receipt::fixture_recovery_receipt(
                &source,
                &backup,
                &target,
                &expected_ciphertext,
                &[],
                &[],
            )
            .unwrap();
            assert!(
                crate::recovery_receipt::reserve_destination_recovery_receipt(&target, &separate,)
                    .is_err(),
                "{fault}"
            );
            assert_eq!(
                inspect_encrypted_copy_recovery(&source, &target, "", "NewKey123!", &[],)
                    .unwrap()
                    .state,
                if final_expected {
                    EncryptedCopyRecoveryState::ExistingMatchesExpected
                } else {
                    EncryptedCopyRecoveryState::DestinationAbsent
                },
                "{fault}"
            );
            // The Tauri-facing classifier must also work after the
            // worker has exited, without inherited migration state.
            let resumed = inspect_interrupted_encrypted_copy(
                &source,
                &backup,
                &target,
                "",
                "NewKey123!",
                &[],
                &[],
            )
            .unwrap();
            assert_eq!(
                resumed.state,
                if final_expected {
                    InterruptedEncryptedCopyState::PublishedContentMatches
                } else {
                    InterruptedEncryptedCopyState::ReservationWithoutDestination
                },
                "{fault}"
            );
            assert!(resumed.operation_id.is_some(), "{fault}");
            // A fresh GUI is allowed to classify the reserved target
            // without reentering the prior SQLCipher keys.
            let brief_resumed = inspect_interrupted_encrypted_copy(
                Path::new(""),
                Path::new(""),
                &target,
                "",
                "",
                &[],
                &[],
            )
            .unwrap();
            assert_eq!(
                brief_resumed.state,
                if final_expected {
                    InterruptedEncryptedCopyState::ManualReviewRequired
                } else {
                    InterruptedEncryptedCopyState::ReservationWithoutDestination
                },
                "{fault}"
            );
            assert_eq!(brief_resumed.operation_id, resumed.operation_id);
            assert!(!brief_resumed.automatic_retry_permitted);
            assert!(!brief_resumed.automatic_delete_permitted);
            assert!(!brief_resumed.installation_enabled);
            assert!(!resumed.automatic_retry_permitted);
            assert!(!resumed.automatic_delete_permitted);
            assert!(!resumed.installation_enabled);
            // Deliberately remove only our disposable test fixture tree.
            fs::remove_dir_all(parent).unwrap();
        }
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
    fn one_consent_preserves_source_while_applying_edited_rows_and_selected_schema() {
        // The exact two user-facing page-five options travel through the SAME
        // real encrypted destination transaction. This is a CI-only test.
        use crate::migration_dry_run::RawCell;
        let parent = target_volume_fixture();
        let source = parent.join("page-five-source.sqlite3");
        crate::legacy_alpha_constraints::create_registered_alpha_test_file(&source).unwrap();
        {
            let db = Connection::open(&source).unwrap();
            db.execute_batch(
                "DROP INDEX uq_game_install_one_active_project;
                 INSERT INTO alpha_users(user_id,disabled) VALUES('old-user',0);",
            )
            .unwrap();
        }
        let backup = parent.join("page-five-source-backup.sqlite3");
        let destination = parent.join("page-five-encrypted.sqlite3");
        let original_bytes = fs::read(&source).unwrap();
        fs::copy(&source, &backup).unwrap();
        let correction = ReviewCorrection::FullRow {
            table: "alpha_users".into(),
            row_id: Some("1".into()),
            columns: vec!["user_id".into(), "disabled".into()],
            before: vec![
                RawCell {
                    kind: "text".into(),
                    value: Some("old-user".into()),
                },
                RawCell {
                    kind: "integer".into(),
                    value: Some("0".into()),
                },
            ],
            after: vec![
                RawCell {
                    kind: "text".into(),
                    value: Some("old-user".into()),
                },
                RawCell {
                    kind: "integer".into(),
                    value: Some("1".into()),
                },
            ],
        };
        let selected = vec!["uq_game_install_one_active_project".to_owned()];
        let result = execute_reviewed_encrypted_copy_with_schema(
            &source,
            &destination,
            &backup,
            "",
            "NewKey123!",
            &[correction],
            &selected,
            EXPERIMENTAL_COPY_CONFIRMATION,
        )
        .unwrap();
        assert!(result.destination_created);
        assert!(result.encrypted_destination_verified);
        assert!(result.staged_values_match_ciphertext);
        assert_eq!(result.staged_changes_verified, 1);
        assert_eq!(result.added_schema_objects, selected);
        let target =
            Connection::open_with_flags(&destination, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY)
                .unwrap();
        target.pragma_update(None, "key", "NewKey123!").unwrap();
        let user_disabled: i64 = target
            .query_row(
                "SELECT disabled FROM alpha_users WHERE user_id='old-user'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(user_disabled, 1);
        let registered_index: i64 = target
            .query_row(
                "SELECT count(*) FROM sqlite_schema WHERE type='index' AND name='uq_game_install_one_active_project'",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(registered_index, 1);
        drop(target);
        assert_eq!(fs::read(&source).unwrap(), original_bytes);
        assert_eq!(fs::read(&backup).unwrap(), original_bytes);
        let original = Connection::open(&source).unwrap();
        assert_eq!(
            original
                .query_row(
                    "SELECT disabled FROM alpha_users WHERE user_id='old-user'",
                    [],
                    |r| r.get::<_, i64>(0),
                )
                .unwrap(),
            0
        );
        drop(original);
        fs::remove_dir_all(parent).unwrap();
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
    fn one_real_copy_preserves_extensions_adds_missing_schema_and_creates_new_directories() {
        // End-user acceptance regression: no mandatory preliminary disk test,
        // no source checkout, no preexisting destination parent and no need
        // to rename the user's original database basename.
        let root = target_volume_fixture();
        let source_parent = root.join("source");
        fs::create_dir(&source_parent).unwrap();
        let source = source_parent.join("alpha.sqlite3");
        crate::legacy_alpha_constraints::create_registered_alpha_test_file(&source).unwrap();
        {
            let db = Connection::open(&source).unwrap();
            db.execute_batch(
                "DROP TABLE sec01_host_rules;
                 CREATE TABLE legacy_extension(note TEXT NOT NULL);
                 INSERT INTO legacy_extension VALUES('preserve-this-value');",
            )
            .unwrap();
        }
        let before = fs::read(&source).unwrap();
        let backup = root.join("independent-backup.sqlite3");
        fs::copy(&source, &backup).unwrap();
        let dest = root.join("new-data").join("nested").join("alpha.sqlite3");
        assert!(!dest.parent().unwrap().exists());
        let selected = vec!["sec01_host_rules".to_owned()];
        let created = execute_reviewed_encrypted_copy_with_schema(
            &source,
            &dest,
            &backup,
            "",
            "NewKey123!",
            &[],
            &selected,
            EXPERIMENTAL_COPY_CONFIRMATION,
        )
        .unwrap();
        assert!(created.destination_created && created.encrypted_destination_verified);
        assert!(created.added_schema_objects.contains(&selected[0]));
        // Restoring the registered table also restores the implicit SQLite
        // PRIMARY KEY autoindex. It is not a separate user-selected object.
        assert!(created
            .added_schema_objects
            .contains(&"sqlite_autoindex_sec01_host_rules_1".to_owned()));
        assert!(dest.exists());
        let encrypted =
            Connection::open_with_flags(&dest, OpenFlags::SQLITE_OPEN_READ_ONLY).unwrap();
        encrypted.pragma_update(None, "key", "NewKey123!").unwrap();
        let restored: i64 = encrypted
            .query_row(
                "SELECT COUNT(*) FROM sqlite_schema WHERE name='sec01_host_rules'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(restored, 1);
        let original: String = encrypted
            .query_row("SELECT note FROM legacy_extension", [], |row| row.get(0))
            .unwrap();
        assert_eq!(original, "preserve-this-value");
        drop(encrypted);
        assert_eq!(fs::read(&source).unwrap(), before);
        assert_eq!(fs::read(&backup).unwrap(), before);
        fs::remove_dir_all(root).unwrap();
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
