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
    // Filename identity is a policy violation regardless of OS-dependent
    // directory lookup errors. Reject it before probing the target path.
    let file_name = destination
        .file_name()
        .ok_or(MigrationDestinationError::DestinationParentUnavailable)?;
    if file_name == source.file_name().unwrap_or_default() {
        return Err(MigrationDestinationError::SameFileName);
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


/// A *rehearsal-only* pinned parent identity. The open directory handle
/// survives path changes; revalidation checks that the selected path still
/// names the same directory. This is not directory-relative publication:
/// path-based creation still has TOCTOU exposure and remains disabled.
pub(crate) struct PinnedDestinationParent {
    preview: MigrationDestinationPreview,
    _directory: fs::File,
    identity: DirectoryIdentity,
}

#[cfg(unix)]
type DirectoryIdentity = (u64, u64);
#[cfg(windows)]
type DirectoryIdentity = (u32, u64);

#[cfg(unix)]
fn open_directory(path: &Path) -> Result<fs::File, String> {
    fs::File::open(path).map_err(|_| "Cannot pin destination directory".to_owned())
}

#[cfg(windows)]
fn open_directory(path: &Path) -> Result<fs::File, String> {
    use std::os::windows::fs::OpenOptionsExt;
    // FILE_FLAG_BACKUP_SEMANTICS permits a directory handle. Refusing
    // FILE_SHARE_DELETE helps prevent rename on Windows while it is held.
    // This is still not a handle-relative directory operation.
    fs::OpenOptions::new()
        .read(true)
        .custom_flags(0x0200_0000)
        .share_mode(0x0000_0001 | 0x0000_0002)
        .open(path)
        .map_err(|_| "Cannot pin destination directory".to_owned())
}

#[cfg(unix)]
fn directory_identity(file: &fs::File) -> Result<DirectoryIdentity, String> {
    use std::os::unix::fs::MetadataExt;
    let meta = file
        .metadata()
        .map_err(|_| "Cannot identify destination directory")?;
    if !meta.is_dir() {
        return Err("Destination handle is not a directory".to_owned());
    }
    Ok((meta.dev(), meta.ino()))
}

#[cfg(windows)]
#[repr(C)]
struct WindowsFileTime {
    low: u32,
    high: u32,
}

#[cfg(windows)]
#[repr(C)]
struct WindowsFileInformation {
    attributes: u32,
    created: WindowsFileTime,
    accessed: WindowsFileTime,
    modified: WindowsFileTime,
    volume_serial: u32,
    file_size_high: u32,
    file_size_low: u32,
    number_of_links: u32,
    index_high: u32,
    index_low: u32,
}

#[cfg(windows)]
#[link(name = "kernel32")]
unsafe extern "system" {
    #[link_name = "GetFileInformationByHandle"]
    fn get_file_information_by_handle(
        handle: *mut std::ffi::c_void,
        info: *mut WindowsFileInformation,
    ) -> i32;
}

#[cfg(windows)]
fn directory_identity(file: &fs::File) -> Result<DirectoryIdentity, String> {
    use std::os::windows::io::AsRawHandle;
    if !file
        .metadata()
        .map_err(|_| "Cannot identify destination directory")?
        .is_dir()
    {
        return Err("Destination handle is not a directory".to_owned());
    }
    // Stable Windows file-volume/index identity through native file handle;
    // std::os::windows::fs::MetadataExt::file_index is unstable on stable Rust.
    let mut info = std::mem::MaybeUninit::<WindowsFileInformation>::uninit();
    let success = unsafe { get_file_information_by_handle(file.as_raw_handle(), info.as_mut_ptr()) };
    if success == 0 {
        return Err("Cannot read destination directory file ID".to_owned());
    }
    let info = unsafe { info.assume_init() };
    Ok((
        info.volume_serial,
        (u64::from(info.index_high) << 32) | u64::from(info.index_low),
    ))
}

impl PinnedDestinationParent {
    pub(crate) fn open(preview: &MigrationDestinationPreview) -> Result<Self, String> {
        let parent = preview
            .destination
            .parent()
            .ok_or("Destination directory unavailable")?;
        let meta = fs::symlink_metadata(parent)
            .map_err(|_| "Cannot inspect destination directory")?;
        if meta.file_type().is_symlink() || !meta.is_dir() {
            return Err("Destination directory changed or is a symlink".to_owned());
        }
        let directory = open_directory(parent)?;
        let identity = directory_identity(&directory)?;
        let guard = Self {
            preview: preview.clone(),
            _directory: directory,
            identity,
        };
        guard.revalidate()?;
        Ok(guard)
    }

    pub(crate) fn revalidate(&self) -> Result<(), String> {
        let parent = self
            .preview
            .destination
            .parent()
            .ok_or("Destination directory unavailable")?;
        let meta = fs::symlink_metadata(parent)
            .map_err(|_| "Destination directory disappeared")?;
        if meta.file_type().is_symlink() || !meta.is_dir() {
            return Err("Destination directory changed or is a symlink".to_owned());
        }
        let path_handle = open_directory(parent)?;
        if directory_identity(&path_handle)? != self.identity {
            return Err("Destination directory identity changed".to_owned());
        }
        // This check also rejects an occupied final name or a changed source.
        if preview_migration_destination(&self.preview.source, &self.preview.destination)
            .map_err(|_| "Migration destination no longer valid")?
            != self.preview
        {
            return Err("Migration destination preview changed".to_owned());
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::{SystemTime, UNIX_EPOCH};

    static NEXT_TEST_ROOT: AtomicU64 = AtomicU64::new(0);

    fn temp_root() -> PathBuf {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let sequence = NEXT_TEST_ROOT.fetch_add(1, Ordering::Relaxed);
        std::env::temp_dir().join(format!(
            "minglefield-migration-{}-{stamp}-{sequence}",
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
    fn pins_destination_directory_without_creating_final_output() {
        let root = temp_root();
        let from = root.join("source");
        let to = root.join("target");
        fs::create_dir_all(&from).unwrap();
        fs::create_dir_all(&to).unwrap();
        let source = from.join("alpha.sqlite3");
        let target = to.join("encrypted.sqlite3");
        fs::write(&source, b"unchanged").unwrap();
        let preview = preview_migration_destination(&source, &target).unwrap();
        let guard = PinnedDestinationParent::open(&preview).unwrap();
        guard.revalidate().unwrap();
        assert!(!target.exists());
        assert_eq!(fs::read(&source).unwrap(), b"unchanged");
        // An occupied target is never permitted, even with a pinned parent.
        fs::write(&target, b"existing").unwrap();
        assert!(guard.revalidate().is_err());
        assert_eq!(fs::read(&target).unwrap(), b"existing");
        drop(guard);
        fs::remove_dir_all(root).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn detects_replaced_directory_even_if_path_text_is_identical() {
        let root = temp_root();
        let from = root.join("source");
        let parent = root.join("target");
        let moved = root.join("moved");
        fs::create_dir_all(&from).unwrap();
        fs::create_dir_all(&parent).unwrap();
        let source = from.join("alpha.sqlite3");
        fs::write(&source, b"unchanged").unwrap();
        let target = parent.join("encrypted.sqlite3");
        let preview = preview_migration_destination(&source, &target).unwrap();
        let guard = PinnedDestinationParent::open(&preview).unwrap();
        fs::rename(&parent, &moved).unwrap();
        fs::create_dir(&parent).unwrap();
        // Canonical path strings still match; the pinned inode does not.
        assert!(guard.revalidate().is_err());
        fs::remove_dir(&parent).unwrap();
        fs::rename(&moved, &parent).unwrap();
        guard.revalidate().unwrap();
        drop(guard);
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
