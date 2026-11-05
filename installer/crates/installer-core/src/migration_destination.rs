//! Non-destructive migration destination preflight.
//! Pure validation: this module never creates, replaces or deletes files.
//! A successful preflight is not authorization to execute a migration.

use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MigrationDestinationError {
    SourceUnavailable,
    SourceNotRegularFile,
    DestinationExists,
    DestinationParentUnavailable,
    DestinationParentNotDirectory,
    DestinationParentIsSymlink,
    SamePath,
    SameFileName,
    ProtectedSourceSidecar,
    IoError,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MigrationDestinationPreview {
    pub source: PathBuf,
    pub destination: PathBuf,
    pub preserves_source: bool,
    pub execution_enabled: bool,
}

/// Fail closed when the source is missing, the destination exists, or a path
/// cannot be validated. The destination may share the source directory,
/// but must use a different filename; it must not replace a WAL/SHM sidecar.
/// An eventual execution layer must recheck all paths atomically and create
/// the destination exclusively before any writes.
pub fn preview_migration_destination(
    source: &Path,
    destination: &Path,
) -> Result<MigrationDestinationPreview, MigrationDestinationError> {
    let source_metadata =
        fs::symlink_metadata(source).map_err(|_| MigrationDestinationError::SourceUnavailable)?;
    if source_metadata.file_type().is_symlink() || !source_metadata.is_file() {
        return Err(MigrationDestinationError::SourceNotRegularFile);
    }
    let source = fs::canonicalize(source).map_err(|_| MigrationDestinationError::IoError)?;
    if destination.as_os_str().is_empty() {
        return Err(MigrationDestinationError::DestinationParentUnavailable);
    }
    match fs::symlink_metadata(destination) {
        Ok(_) => return Err(MigrationDestinationError::DestinationExists),
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {}
        Err(_) => return Err(MigrationDestinationError::IoError),
    }
    let parent = destination
        .parent()
        .ok_or(MigrationDestinationError::DestinationParentUnavailable)?;
    let parent_metadata = fs::symlink_metadata(parent)
        .map_err(|_| MigrationDestinationError::DestinationParentUnavailable)?;
    if parent_metadata.file_type().is_symlink() {
        return Err(MigrationDestinationError::DestinationParentIsSymlink);
    }
    if !parent_metadata.is_dir() {
        return Err(MigrationDestinationError::DestinationParentNotDirectory);
    }
    let parent = fs::canonicalize(parent).map_err(|_| MigrationDestinationError::IoError)?;
    let file_name = destination
        .file_name()
        .ok_or(MigrationDestinationError::DestinationParentUnavailable)?;
    if file_name == source.file_name().unwrap_or_default() {
        return Err(MigrationDestinationError::SameFileName);
    }
    // A same-directory destination must never claim one of SQLite's possible
    // live sidecar filenames, even when that sidecar does not exist yet.
    if parent == source.parent().unwrap_or_else(|| Path::new("")) {
        let original = source.file_name().unwrap_or_default().to_string_lossy();
        let candidate = file_name.to_string_lossy();
        if ["-wal", "-shm", "-journal"]
            .iter()
            .any(|suffix| candidate.eq_ignore_ascii_case(&format!("{original}{suffix}")))
        {
            return Err(MigrationDestinationError::ProtectedSourceSidecar);
        }
    }
    let destination = parent.join(file_name);
    if destination == source {
        return Err(MigrationDestinationError::SamePath);
    }
    Ok(MigrationDestinationPreview {
        source,
        destination,
        preserves_source: true,
        execution_enabled: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_root() -> PathBuf {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!(
            "minglefield-migration-{}-{stamp}",
            std::process::id()
        ))
    }

    #[test]
    fn accepts_distinct_destination_without_touching_source() {
        let root = temp_root();
        let source_dir = root.join("original");
        let target_dir = root.join("new");
        fs::create_dir_all(&source_dir).unwrap();
        fs::create_dir_all(&target_dir).unwrap();
        let source = source_dir.join("alpha.sqlite3");
        fs::write(&source, b"fixture").unwrap();
        let destination = target_dir.join("alpha-v1.sqlite3");
        let preview = preview_migration_destination(&source, &destination).unwrap();
        assert!(preview.preserves_source);
        assert!(!preview.execution_enabled);
        assert_eq!(fs::read(&source).unwrap(), b"fixture");
        assert!(!destination.exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_existing_target_and_same_directory() {
        let root = temp_root();
        let source_dir = root.join("original");
        let target_dir = root.join("new");
        fs::create_dir_all(&source_dir).unwrap();
        fs::create_dir_all(&target_dir).unwrap();
        let source = source_dir.join("alpha.sqlite3");
        fs::write(&source, b"fixture").unwrap();
        let in_place = source_dir.join("new.sqlite3");
        let preview = preview_migration_destination(&source, &in_place).unwrap();
        assert_eq!(
            preview.destination,
            fs::canonicalize(&source_dir).unwrap().join("new.sqlite3")
        );
        assert!(preview.preserves_source);
        assert!(!in_place.exists());
        for suffix in ["-wal", "-shm", "-journal"] {
            assert_eq!(
                preview_migration_destination(
                    &source,
                    &source_dir.join(format!("alpha.sqlite3{suffix}"))
                ),
                Err(MigrationDestinationError::ProtectedSourceSidecar)
            );
        }
        assert_eq!(
            preview_migration_destination(&source, &target_dir.join("alpha.sqlite3")),
            Err(MigrationDestinationError::SameFileName)
        );
        let destination = target_dir.join("new.sqlite3");
        fs::write(&destination, b"existing").unwrap();
        assert_eq!(
            preview_migration_destination(&source, &destination),
            Err(MigrationDestinationError::DestinationExists)
        );
        assert_eq!(fs::read(&destination).unwrap(), b"existing");
        fs::remove_dir_all(root).unwrap();
    }
}
