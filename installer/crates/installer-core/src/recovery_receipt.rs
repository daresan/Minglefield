//! M2.07: non-authorizing, persistent recovery receipt for isolated fixtures.
//! A matching SHA-256 fingerprint proves byte identity at inspection time,
//! NOT provenance, permission, exclusive ownership, crash durability or trust.
//! This module is not yet wired into production publication or installer GUI.

use crate::integrity::{sha256_hex, sha256_reader_hex};
use crate::migration_destination::same_underlying_file;
use crate::migration_dry_run::ReviewCorrection;
use rusqlite::Connection;
use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::path::{Component, Path, PathBuf};

const HEADER: &str = "MINGLEFIELD_RECOVERY_RECEIPT_V1";
const MAX_RECEIPT_BYTES: u64 = 2048;
// SHA-256 file verification is streaming; database size is not restricted
// to an arbitrary fixture cap. Directory crash durability is separate.

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RecoveryReceiptV1 {
    pub operation_id: String,
    pub source_sha256: String,
    pub backup_sha256: String,
    pub destination_path_sha256: String,
    pub ciphertext_sha256: String,
    pub corrections_sha256: String,
    pub schema_additions_sha256: String,
    pub ciphertext_bytes: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReceiptInspection {
    Missing,
    Matched,
    Unverified,
}

fn valid_lower_hex(value: &str, n: usize) -> bool {
    value.len() == n
        && value
            .bytes()
            .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
}

fn validate_receipt(record: &RecoveryReceiptV1) -> Result<(), String> {
    if !valid_lower_hex(&record.operation_id, 32)
        || ![
            &record.source_sha256,
            &record.backup_sha256,
            &record.destination_path_sha256,
            &record.ciphertext_sha256,
            &record.corrections_sha256,
            &record.schema_additions_sha256,
        ]
        .iter()
        .all(|hash| valid_lower_hex(hash, 64))
        || record.ciphertext_bytes < 16
    {
        return Err("Invalid bounded M2.07 recovery receipt fields".into());
    }
    Ok(())
}

pub fn new_recovery_operation_id() -> Result<String, String> {
    // SQLite's cryptographic randomblob is already an installer dependency.
    // This is a correlation ID only and NEVER an authorization credential.
    let db = Connection::open_in_memory()
        .map_err(|_| "Cannot initialize recovery operation identifier")?;
    let id: String = db
        .query_row("SELECT lower(hex(randomblob(16)))", [], |row| row.get(0))
        .map_err(|_| "Cannot generate recovery operation identifier")?;
    if !valid_lower_hex(&id, 32) {
        return Err("Invalid recovery operation identifier".into());
    }
    Ok(id)
}

fn checked_sha256_of_file(path: &Path) -> Result<(String, u64), String> {
    let metadata =
        fs::symlink_metadata(path).map_err(|_| "Cannot inspect recovery fixture file")?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err("Recovery input must be a regular non-symlink file".into());
    }
    let mut file = fs::File::open(path).map_err(|_| "Cannot open recovery file")?;
    if !file
        .metadata()
        .map_err(|_| "Cannot inspect open recovery file")?
        .is_file()
    {
        return Err("Recovery input is not a regular file".into());
    }
    let (digest, size) =
        sha256_reader_hex(&mut file).map_err(|_| "Cannot stream recovery file fingerprint")?;
    let after = file
        .metadata()
        .map_err(|_| "Cannot recheck recovery file")?;
    if size != metadata.len() || size != after.len() {
        return Err("Recovery file size changed during fingerprinting".into());
    }
    Ok((digest, size))
}

fn destination_name_digest(destination: &Path) -> Result<String, String> {
    if !destination.is_absolute()
        || destination
            .components()
            .any(|part| matches!(part, Component::ParentDir))
    {
        return Err("Recovery destination must be an absolute non-traversing path".into());
    }
    let filename = destination
        .file_name()
        .ok_or("Recovery destination has no filename")?;
    let parent = fs::canonicalize(
        destination
            .parent()
            .ok_or("Recovery destination has no parent")?,
    )
    .map_err(|_| "Cannot identify recovery destination parent")?;
    let absolute = parent.join(filename);
    let text = absolute
        .to_str()
        .ok_or("Recovery destination path is not valid Unicode")?;
    Ok(sha256_hex(text.as_bytes()))
}

fn schema_selection_digest(schema_additions: &[String]) -> Result<String, String> {
    let mut names = schema_additions.to_vec();
    if names.iter().any(|name| {
        name.is_empty()
            || name.len() > 128
            || !name
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_')
    }) {
        return Err("Invalid selected registered schema-object identifier".into());
    }
    names.sort_unstable();
    names.dedup();
    if names.len() != schema_additions.len() {
        return Err("Duplicate registered schema-object selection".into());
    }
    Ok(sha256_hex(names.join("\0").as_bytes()))
}

#[allow(clippy::too_many_arguments)]
fn receipt_for_known_operation(
    operation_id: &str,
    source: &Path,
    backup: &Path,
    destination: &Path,
    ciphertext: &Path,
    corrections: &[ReviewCorrection],
    schema_additions: &[String],
) -> Result<RecoveryReceiptV1, String> {
    if !valid_lower_hex(operation_id, 32) {
        return Err("Recovery operation ID must be a generated 128-bit identifier".into());
    }
    if same_underlying_file(source, backup)?
        || same_underlying_file(source, ciphertext)?
        || same_underlying_file(backup, ciphertext)?
    {
        return Err("Recovery source, backup and ciphertext must be different files".into());
    }
    let (source_sha256, source_bytes) = checked_sha256_of_file(source)?;
    let (backup_sha256, backup_bytes) = checked_sha256_of_file(backup)?;
    // The caller verifies logical SQLite/SQLCipher equivalence before
    // recording this receipt. Two legitimate snapshots may have different
    // on-disk layouts; bind BOTH hashes rather than demanding byte identity.
    if source_bytes == 0 || backup_bytes == 0 {
        return Err("Recovery source and backup must both be nonempty".into());
    }
    let (ciphertext_sha256, ciphertext_bytes) = checked_sha256_of_file(ciphertext)?;
    if ciphertext_bytes < 16 {
        return Err("Recovery ciphertext is truncated".into());
    }
    let mut header = [0u8; 16];
    let mut file = fs::File::open(ciphertext).map_err(|_| "Cannot open recovery ciphertext")?;
    use std::io::Read;
    file.read_exact(&mut header)
        .map_err(|_| "Cannot read recovery ciphertext header")?;
    if &header == b"SQLite format 3\0" {
        return Err("Unencrypted SQLite is not a recovery ciphertext fixture".into());
    }
    let receipt = RecoveryReceiptV1 {
        operation_id: operation_id.to_owned(),
        source_sha256,
        backup_sha256,
        destination_path_sha256: destination_name_digest(destination)?,
        ciphertext_sha256,
        corrections_sha256: sha256_hex(format!("{corrections:?}").as_bytes()),
        schema_additions_sha256: schema_selection_digest(schema_additions)?,
        ciphertext_bytes,
    };
    validate_receipt(&receipt)?;
    Ok(receipt)
}

/// For test-owned fixture files only. Do not promote this to a production
/// receipt writer until durable directory sync and ownership are checked.
pub fn fixture_recovery_receipt(
    source: &Path,
    backup: &Path,
    destination: &Path,
    ciphertext: &Path,
    corrections: &[ReviewCorrection],
    schema_additions: &[String],
) -> Result<RecoveryReceiptV1, String> {
    receipt_for_known_operation(
        &new_recovery_operation_id()?,
        source,
        backup,
        destination,
        ciphertext,
        corrections,
        schema_additions,
    )
}

pub fn recovery_receipt_filename(operation_id: &str) -> Result<String, String> {
    if !valid_lower_hex(operation_id, 32) {
        return Err("Invalid recovery receipt filename identifier".into());
    }
    Ok(format!("minglefield-recovery-{operation_id}.receipt"))
}

/// A deterministic, destination-specific filename is an exclusive operation
/// slot. A second attempt cannot silently write another random receipt for
/// the same canonical destination. This is not a native handle-relative lock.
pub fn reserved_destination_receipt_path(destination: &Path) -> Result<PathBuf, String> {
    let hash = destination_name_digest(destination)?;
    let parent = destination
        .parent()
        .ok_or("Recovery destination has no parent")?;
    Ok(parent.join(format!("minglefield-target-{hash}.receipt")))
}

#[derive(Debug, Clone)]
pub struct ReceiptReservation {
    pub operation_id: String,
    pub receipt_path: PathBuf,
    /// True only after Unix's explicit parent-directory sync. On Windows,
    /// file sync passes but durable directory publication remains unproven.
    pub directory_entry_synced: bool,
}

/// Only for the explicitly approved Alpha copy path or disposable fixtures.
/// This record is written after the ciphertext has been flushed and verified
/// but BEFORE the destination is linked into place. File creation is exclusive.
pub fn reserve_destination_recovery_receipt(
    destination: &Path,
    receipt: &RecoveryReceiptV1,
) -> Result<ReceiptReservation, String> {
    let expected = destination_name_digest(destination)?;
    if expected != receipt.destination_path_sha256 {
        return Err("Recovery receipt does not match chosen destination".into());
    }
    match fs::symlink_metadata(destination) {
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(_) => return Err("Cannot inspect destination before receipt reservation".into()),
        Ok(_) => return Err("Recovery destination already exists".into()),
    }
    let path = reserved_destination_receipt_path(destination)?;
    let parent = path.parent().ok_or("Recovery receipt parent unavailable")?;
    let info =
        fs::symlink_metadata(parent).map_err(|_| "Cannot inspect recovery receipt parent")?;
    if info.file_type().is_symlink() || !info.is_dir() {
        return Err("Recovery receipt parent must be a regular directory".into());
    }
    // Exclusive create_new is the inter-process winner selection. A receipt
    // deliberately remains after later failures, preventing silent retries.
    let data = receipt_text(receipt)?;
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options
        .open(&path)
        .map_err(|_| "Recovery destination reservation already exists or cannot be created")?;
    file.write_all(data.as_bytes())
        .map_err(|_| "Cannot write exclusive recovery receipt")?;
    file.sync_all()
        .map_err(|_| "Cannot flush exclusive recovery receipt")?;
    let directory_entry_synced = sync_recovery_parent_directory(parent)?;
    Ok(ReceiptReservation {
        operation_id: receipt.operation_id.clone(),
        receipt_path: path,
        directory_entry_synced,
    })
}

#[cfg(unix)]
fn sync_recovery_parent_directory(parent: &Path) -> Result<bool, String> {
    fs::File::open(parent)
        .map_err(|_| "Cannot open recovery receipt parent for sync")?
        .sync_all()
        .map_err(|_| "Cannot sync recovery receipt directory entry")?;
    Ok(true)
}

#[cfg(windows)]
fn sync_recovery_parent_directory(_parent: &Path) -> Result<bool, String> {
    // File::sync_all on the receipt is still required. Windows directory
    // FlushFileBuffers needs a separately proven native handle strategy.
    // Never advertise directory durability from this Alpha-only slice.
    Ok(false)
}

/// Flush a newly published destination's containing directory where a
/// tested native API exists. Windows returns false, rather than pretending
/// that syncing the ciphertext file also durably committed its directory.
pub fn sync_published_destination_parent(destination: &Path) -> Result<bool, String> {
    let parent = destination
        .parent()
        .ok_or("Published destination parent is missing")?;
    let meta =
        fs::symlink_metadata(parent).map_err(|_| "Cannot inspect published destination parent")?;
    if meta.file_type().is_symlink() || !meta.is_dir() {
        return Err("Published destination parent changed or is a symlink".into());
    }
    sync_recovery_parent_directory(parent)
}

#[allow(clippy::too_many_arguments)]
pub fn inspect_reserved_destination_recovery_receipt(
    source: &Path,
    backup: &Path,
    destination: &Path,
    ciphertext: &Path,
    corrections: &[ReviewCorrection],
    schema_additions: &[String],
) -> Result<ReceiptInspection, String> {
    let path = reserved_destination_receipt_path(destination)?;
    match fs::symlink_metadata(&path) {
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(ReceiptInspection::Missing);
        }
        Err(_) => return Err("Cannot read destination recovery reservation".into()),
        Ok(_) => {}
    }
    let expected = match read_receipt(&path) {
        Ok(record) => record,
        Err(_) => return Ok(ReceiptInspection::Unverified),
    };
    let verified = receipt_for_known_operation(
        &expected.operation_id,
        source,
        backup,
        destination,
        ciphertext,
        corrections,
        schema_additions,
    );
    Ok(if verified.is_ok_and(|value| value == expected) {
        ReceiptInspection::Matched
    } else {
        ReceiptInspection::Unverified
    })
}

fn receipt_text(receipt: &RecoveryReceiptV1) -> Result<String, String> {
    validate_receipt(receipt)?;
    Ok(format!(
        "{HEADER}\noperation_id={}\nsource_sha256={}\nbackup_sha256={}\ndestination_path_sha256={}\nciphertext_sha256={}\ncorrections_sha256={}\nschema_additions_sha256={}\nciphertext_bytes={}\n",
        receipt.operation_id,
        receipt.source_sha256,
        receipt.backup_sha256,
        receipt.destination_path_sha256,
        receipt.ciphertext_sha256,
        receipt.corrections_sha256,
        receipt.schema_additions_sha256,
        receipt.ciphertext_bytes,
    ))
}

fn parse_receipt(bytes: &[u8]) -> Result<RecoveryReceiptV1, String> {
    let text = std::str::from_utf8(bytes).map_err(|_| "Receipt is not UTF-8")?;
    let lines: Vec<_> = text.lines().collect();
    if lines.len() != 9 || lines[0] != HEADER {
        return Err("Unsupported or truncated recovery receipt".into());
    }
    fn field<'a>(line: &'a str, prefix: &str) -> Result<&'a str, String> {
        line.strip_prefix(prefix)
            .ok_or("Recovery receipt field name or order mismatch".into())
    }
    let record = RecoveryReceiptV1 {
        operation_id: field(lines[1], "operation_id=")?.to_owned(),
        source_sha256: field(lines[2], "source_sha256=")?.to_owned(),
        backup_sha256: field(lines[3], "backup_sha256=")?.to_owned(),
        destination_path_sha256: field(lines[4], "destination_path_sha256=")?.to_owned(),
        ciphertext_sha256: field(lines[5], "ciphertext_sha256=")?.to_owned(),
        corrections_sha256: field(lines[6], "corrections_sha256=")?.to_owned(),
        schema_additions_sha256: field(lines[7], "schema_additions_sha256=")?.to_owned(),
        ciphertext_bytes: field(lines[8], "ciphertext_bytes=")?
            .parse()
            .map_err(|_| "Invalid recovery ciphertext byte count")?,
    };
    validate_receipt(&record)?;
    if receipt_text(&record)?.as_bytes() != bytes {
        return Err("Recovery receipt has noncanonical or extra data".into());
    }
    Ok(record)
}

/// Write a *new* receipt, never overwrite an existing record. Syncing this
/// file alone does NOT prove its parent directory entry survived power loss.
pub fn write_fixture_recovery_receipt(
    fixture_parent: &Path,
    receipt: &RecoveryReceiptV1,
) -> Result<PathBuf, String> {
    let data = receipt_text(receipt)?;
    let meta = fs::symlink_metadata(fixture_parent)
        .map_err(|_| "Cannot inspect recovery receipt directory")?;
    if meta.file_type().is_symlink() || !meta.is_dir() {
        return Err("Recovery receipt directory is not a regular directory".into());
    }
    let file_path = fixture_parent.join(recovery_receipt_filename(&receipt.operation_id)?);
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options
        .open(&file_path)
        .map_err(|_| "Recovery receipt already exists or cannot be created")?;
    file.write_all(data.as_bytes())
        .map_err(|_| "Cannot write recovery receipt")?;
    file.sync_all()
        .map_err(|_| "Cannot sync recovery receipt file contents")?;
    Ok(file_path)
}

fn read_receipt(path: &Path) -> Result<RecoveryReceiptV1, String> {
    let meta =
        fs::symlink_metadata(path).map_err(|_| "Cannot inspect recovery receipt metadata")?;
    if meta.file_type().is_symlink() || !meta.is_file() || meta.len() > MAX_RECEIPT_BYTES {
        return Err("Recovery receipt is not a small regular file".into());
    }
    // The initial pathname check is advisory: opening a separate handle can
    // race a local rename. Recheck the opened object and bound reads to 2 KiB
    // so a switched-in large file cannot force unbounded allocation.
    let mut file = fs::File::open(path).map_err(|_| "Cannot open recovery receipt")?;
    let opened = file
        .metadata()
        .map_err(|_| "Cannot inspect opened recovery receipt")?;
    if !opened.is_file() || opened.len() > MAX_RECEIPT_BYTES || opened.len() != meta.len() {
        return Err("Recovery receipt changed before reading".into());
    }
    let mut bytes = Vec::new();
    Read::by_ref(&mut file)
        .take(MAX_RECEIPT_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "Cannot read bounded recovery receipt")?;
    let after = fs::symlink_metadata(path).map_err(|_| "Cannot recheck recovery receipt path")?;
    if bytes.len() as u64 != opened.len()
        || bytes.len() as u64 > MAX_RECEIPT_BYTES
        || after.file_type().is_symlink()
        || !after.is_file()
        || after.len() != opened.len()
    {
        return Err("Recovery receipt changed during reading".into());
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if meta.dev() != opened.dev()
            || meta.ino() != opened.ino()
            || after.dev() != opened.dev()
            || after.ino() != opened.ino()
        {
            return Err("Recovery receipt file identity changed".into());
        }
    }
    // This bounds accidental/adversarial reads; it is not an authenticated
    // receipt or a native handle-relative Windows pathname-race guarantee.
    let receipt = parse_receipt(&bytes)?;
    let name = path.file_name().and_then(|name| name.to_str());
    let by_id = recovery_receipt_filename(&receipt.operation_id)?;
    let by_target = format!(
        "minglefield-target-{}.receipt",
        receipt.destination_path_sha256
    );
    if name != Some(by_id.as_str()) && name != Some(by_target.as_str()) {
        return Err("Recovery receipt filename does not match record identity".into());
    }
    Ok(receipt)
}

/// Read a destination-reserved operation identifier without accepting the
/// record as authenticated provenance or changing either file. An invalid
/// receipt is an error rather than a new available operation slot.
pub fn read_reserved_destination_operation_id(
    destination: &Path,
) -> Result<Option<String>, String> {
    let path = reserved_destination_receipt_path(destination)?;
    match fs::symlink_metadata(&path) {
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(_) => return Err("Cannot inspect existing recovery reservation".into()),
        Ok(_) => {}
    }
    let receipt = read_receipt(&path)?;
    if receipt.destination_path_sha256 != destination_name_digest(destination)? {
        return Err("Recovery reservation belongs to a different destination".into());
    }
    Ok(Some(receipt.operation_id))
}

/// Purely observational: matching a self-asserted receipt is NEVER approval
/// to delete, retry, roll back, install or activate a Host.
#[allow(clippy::too_many_arguments)]
pub fn inspect_fixture_recovery_receipt(
    path: &Path,
    operation_id: &str,
    source: &Path,
    backup: &Path,
    destination: &Path,
    ciphertext: &Path,
    corrections: &[ReviewCorrection],
    schema_additions: &[String],
) -> Result<ReceiptInspection, String> {
    match fs::symlink_metadata(path) {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            return Ok(ReceiptInspection::Missing);
        }
        Err(_) => return Err("Cannot access recovery receipt".into()),
        Ok(_) => {}
    }
    let present = match read_receipt(path) {
        Ok(value) => value,
        Err(_) => return Ok(ReceiptInspection::Unverified),
    };
    let current = receipt_for_known_operation(
        operation_id,
        source,
        backup,
        destination,
        ciphertext,
        corrections,
        schema_additions,
    );
    Ok(if current.is_ok_and(|value| present == value) {
        ReceiptInspection::Matched
    } else {
        ReceiptInspection::Unverified
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::{SystemTime, UNIX_EPOCH};

    static NEXT: AtomicU64 = AtomicU64::new(0);
    fn directory() -> PathBuf {
        let id = NEXT.fetch_add(1, Ordering::Relaxed);
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!(
            "minglefield-m207-receipt-test-{}-{nanos}-{id}",
            std::process::id()
        ));
        fs::create_dir(&dir).unwrap();
        dir
    }

    fn fixture(root: &Path) -> (PathBuf, PathBuf, PathBuf, PathBuf) {
        let source = root.join("source.sqlite3");
        let backup = root.join("backup.sqlite3");
        let destination = root.join("final-sqlcipher.sqlite3");
        let ciphertext = root.join("stage-sqlcipher.sqlite3");
        fs::write(&source, b"fixture-source-original").unwrap();
        fs::copy(&source, &backup).unwrap();
        fs::write(
            &ciphertext,
            b"\x31\x07\xff\x12ciphertext fixture not actual SQLCipher",
        )
        .unwrap();
        (source, backup, destination, ciphertext)
    }

    #[test]
    fn receipt_is_persistent_and_binds_every_fixture_input_without_secrets() {
        let root = directory();
        let (source, backup, destination, ciphertext) = fixture(&root);
        let schema = ["uq_game_install_one_active_project".to_owned()];
        let record =
            fixture_recovery_receipt(&source, &backup, &destination, &ciphertext, &[], &schema)
                .unwrap();
        let path = write_fixture_recovery_receipt(&root, &record).unwrap();
        let bytes = fs::read(&path).unwrap();
        assert!(std::str::from_utf8(&bytes).unwrap().starts_with(HEADER));
        assert!(!String::from_utf8_lossy(&bytes).contains("fixture-source-original"));
        assert!(!String::from_utf8_lossy(&bytes).contains("NewKey123!"));
        assert!(!String::from_utf8_lossy(&bytes).contains("source.sqlite3"));
        assert!(write_fixture_recovery_receipt(&root, &record).is_err());
        let inspect = |backup_path: &Path, selected: &[String], target: &Path| {
            inspect_fixture_recovery_receipt(
                &path,
                &record.operation_id,
                &source,
                backup_path,
                target,
                &ciphertext,
                &[],
                selected,
            )
            .unwrap()
        };
        assert_eq!(
            inspect(&backup, &schema, &destination),
            ReceiptInspection::Matched,
        );
        assert_eq!(
            inspect(&backup, &[], &destination),
            ReceiptInspection::Unverified,
        );
        assert_eq!(
            inspect(&backup, &schema, &root.join("other-target.sqlite3")),
            ReceiptInspection::Unverified,
        );
        fs::write(&ciphertext, b"\x31\x07\xff\x12tampered encrypted content").unwrap();
        assert_eq!(
            inspect(&backup, &schema, &destination),
            ReceiptInspection::Unverified,
        );
        fs::remove_file(&path).unwrap();
        assert_eq!(
            inspect(&backup, &schema, &destination),
            ReceiptInspection::Missing,
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn receipt_rejects_backup_alias_mismatch_and_unrecognized_metadata() {
        let root = directory();
        let (source, backup, destination, ciphertext) = fixture(&root);
        assert!(
            fixture_recovery_receipt(&source, &source, &destination, &ciphertext, &[], &[],)
                .is_err()
        );
        let alias = root.join("backup-hardlink.sqlite3");
        fs::hard_link(&source, &alias).unwrap();
        assert!(
            fixture_recovery_receipt(&source, &alias, &destination, &ciphertext, &[], &[],)
                .is_err()
        );
        fs::write(&backup, b"changed backup").unwrap();
        // The receipt layer captures both hashes; logical equivalence
        // belongs to the separately verified SQLCipher source/backup guard.
        let other_layout =
            fixture_recovery_receipt(&source, &backup, &destination, &ciphertext, &[], &[])
                .unwrap();
        assert_ne!(other_layout.source_sha256, other_layout.backup_sha256);
        fs::copy(&source, &backup).unwrap();
        let record =
            fixture_recovery_receipt(&source, &backup, &destination, &ciphertext, &[], &[])
                .unwrap();
        let path = write_fixture_recovery_receipt(&root, &record).unwrap();
        fs::OpenOptions::new()
            .append(true)
            .open(&path)
            .unwrap()
            .write_all(b"unexpected_field=yes\n")
            .unwrap();
        assert_eq!(
            inspect_fixture_recovery_receipt(
                &path,
                &record.operation_id,
                &source,
                &backup,
                &destination,
                &ciphertext,
                &[],
                &[],
            )
            .unwrap(),
            ReceiptInspection::Unverified,
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn target_reservation_is_exclusive_and_reports_directory_sync_scope() {
        let root = directory();
        let (source, backup, destination, ciphertext) = fixture(&root);
        let receipt =
            fixture_recovery_receipt(&source, &backup, &destination, &ciphertext, &[], &[])
                .unwrap();
        let reserved = reserve_destination_recovery_receipt(&destination, &receipt).unwrap();
        assert_eq!(reserved.operation_id, receipt.operation_id);
        assert_eq!(
            reserved.receipt_path,
            reserved_destination_receipt_path(&destination).unwrap()
        );
        assert!(reserved.receipt_path.is_file());
        #[cfg(unix)]
        assert!(reserved.directory_entry_synced);
        #[cfg(windows)]
        assert!(!reserved.directory_entry_synced);
        assert_eq!(
            inspect_reserved_destination_recovery_receipt(
                &source,
                &backup,
                &destination,
                &ciphertext,
                &[],
                &[],
            )
            .unwrap(),
            ReceiptInspection::Matched,
        );
        let other = fixture_recovery_receipt(&source, &backup, &destination, &ciphertext, &[], &[])
            .unwrap();
        assert_ne!(receipt.operation_id, other.operation_id);
        assert!(reserve_destination_recovery_receipt(&destination, &other).is_err());
        assert_eq!(
            inspect_reserved_destination_recovery_receipt(
                &source,
                &backup,
                &destination,
                &ciphertext,
                &[],
                &[],
            )
            .unwrap(),
            ReceiptInspection::Matched,
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn reserved_receipt_is_persisted_before_publication_and_does_not_authorize_retry() {
        let root = directory();
        let (source, backup, destination, ciphertext) = fixture(&root);
        let receipt =
            fixture_recovery_receipt(&source, &backup, &destination, &ciphertext, &[], &[])
                .unwrap();
        let reserved = reserve_destination_recovery_receipt(&destination, &receipt).unwrap();
        assert!(!destination.exists());
        // A missing target does not imply a free operation slot.
        assert!(reserve_destination_recovery_receipt(&destination, &receipt).is_err());
        assert!(reserved.receipt_path.is_file());
        fs::hard_link(&ciphertext, &destination).unwrap();
        assert!(reserve_destination_recovery_receipt(&destination, &receipt).is_err());
        assert_eq!(
            inspect_reserved_destination_recovery_receipt(
                &source,
                &backup,
                &destination,
                &destination,
                &[],
                &[],
            )
            .unwrap(),
            ReceiptInspection::Matched,
        );
        fs::write(&destination, b"changed-existing-file").unwrap();
        assert_eq!(
            inspect_reserved_destination_recovery_receipt(
                &source,
                &backup,
                &destination,
                &destination,
                &[],
                &[],
            )
            .unwrap(),
            ReceiptInspection::Unverified,
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn oversized_or_replaced_receipt_never_reopens_a_recovery_slot() {
        let root = directory();
        let (source, backup, destination, ciphertext) = fixture(&root);
        let original = fs::read(&source).unwrap();
        let receipt =
            fixture_recovery_receipt(&source, &backup, &destination, &ciphertext, &[], &[])
                .unwrap();
        let reservation = reserve_destination_recovery_receipt(&destination, &receipt).unwrap();
        fs::OpenOptions::new()
            .append(true)
            .open(&reservation.receipt_path)
            .unwrap()
            .write_all(&vec![b'X'; MAX_RECEIPT_BYTES as usize])
            .unwrap();
        assert!(read_reserved_destination_operation_id(&destination).is_err());
        assert_eq!(
            inspect_reserved_destination_recovery_receipt(
                &source,
                &backup,
                &destination,
                &ciphertext,
                &[],
                &[],
            )
            .unwrap(),
            ReceiptInspection::Unverified,
        );
        assert!(reserve_destination_recovery_receipt(&destination, &receipt).is_err());
        #[cfg(unix)]
        {
            fs::remove_file(&reservation.receipt_path).unwrap();
            std::os::unix::fs::symlink(&ciphertext, &reservation.receipt_path).unwrap();
            assert!(read_reserved_destination_operation_id(&destination).is_err());
            assert_eq!(
                inspect_reserved_destination_recovery_receipt(
                    &source,
                    &backup,
                    &destination,
                    &ciphertext,
                    &[],
                    &[],
                )
                .unwrap(),
                ReceiptInspection::Unverified,
            );
        }
        assert_eq!(fs::read(&source).unwrap(), original);
        assert_eq!(fs::read(&backup).unwrap(), original);
        assert!(!destination.exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn different_but_logically_equivalent_backup_bytes_can_be_fingerprinted() {
        let root = directory();
        let (source, backup, destination, ciphertext) = fixture(&root);
        fs::write(&backup, b"other layout of a caller-verified backup").unwrap();
        // The receipt layer records raw bytes; SQLite logical equality is
        // already established by the higher-level migration guard.
        let record =
            fixture_recovery_receipt(&source, &backup, &destination, &ciphertext, &[], &[])
                .unwrap();
        assert_ne!(record.source_sha256, record.backup_sha256);
        let reserved = reserve_destination_recovery_receipt(&destination, &record).unwrap();
        assert!(reserved.receipt_path.is_file());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn receipt_refuses_plaintext_target_and_duplicate_schema_selection() {
        let root = directory();
        let (source, backup, destination, ciphertext) = fixture(&root);
        fs::write(&ciphertext, b"SQLite format 3\0plaintext fixture data").unwrap();
        assert!(
            fixture_recovery_receipt(&source, &backup, &destination, &ciphertext, &[], &[],)
                .is_err()
        );
        fs::write(
            &ciphertext,
            b"\x31\x07\xff\x12ciphertext fixture not actual SQLCipher",
        )
        .unwrap();
        let duplicate = ["idx_name".to_owned(), "idx_name".to_owned()];
        assert!(fixture_recovery_receipt(
            &source,
            &backup,
            &destination,
            &ciphertext,
            &[],
            &duplicate,
        )
        .is_err());
        fs::remove_dir_all(root).unwrap();
    }
}
