//! M2.07: non-authorizing, persistent recovery receipt for isolated fixtures.
//! A matching SHA-256 fingerprint proves byte identity at inspection time,
//! NOT provenance, permission, exclusive ownership, crash durability or trust.
//! This module is not yet wired into production publication or installer GUI.

use crate::integrity::sha256_hex;
use crate::migration_destination::same_underlying_file;
use crate::migration_dry_run::ReviewCorrection;
use rusqlite::Connection;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Component, Path, PathBuf};

const HEADER: &str = "MINGLEFIELD_RECOVERY_RECEIPT_V1";
const MAX_RECEIPT_BYTES: u64 = 2048;
// The first slice is bounded to disposable, small Alpha fixtures. A
// streaming fingerprint and real directory durability are release gates.
const MAX_FIXTURE_FILE_BYTES: u64 = 64 * 1024 * 1024;

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
        || record.ciphertext_bytes > MAX_FIXTURE_FILE_BYTES
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
    if metadata.file_type().is_symlink()
        || !metadata.is_file()
        || metadata.len() > MAX_FIXTURE_FILE_BYTES
    {
        return Err("Recovery fixture is not a supported regular test file".into());
    }
    let data = fs::read(path).map_err(|_| "Cannot read recovery fixture bytes")?;
    if data.len() as u64 != metadata.len() {
        return Err("Recovery fixture size changed during inspection".into());
    }
    Ok((sha256_hex(&data), data.len() as u64))
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
    if source_sha256 != backup_sha256 || source_bytes != backup_bytes {
        return Err("Recovery source and independently copied backup differ".into());
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
    let bytes = fs::read(path).map_err(|_| "Cannot read recovery receipt")?;
    let receipt = parse_receipt(&bytes)?;
    if path.file_name().and_then(|name| name.to_str())
        != Some(recovery_receipt_filename(&receipt.operation_id)?.as_str())
    {
        return Err("Recovery receipt filename does not match operation identifier".into());
    }
    Ok(receipt)
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
        assert!(
            fixture_recovery_receipt(&source, &backup, &destination, &ciphertext, &[], &[],)
                .is_err()
        );
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
