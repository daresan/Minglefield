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

fn inspected_future_parent(parent: &Path) -> Result<PathBuf, MigrationDestinationError> {
    let mut cursor = parent.to_path_buf();
    let mut absent = Vec::new();
    loop {
        match fs::symlink_metadata(&cursor) {
            Ok(metadata) => {
                if metadata.file_type().is_symlink() {
                    return Err(MigrationDestinationError::DestinationParentIsSymlink);
                }
                if !metadata.is_dir() {
                    return Err(MigrationDestinationError::DestinationParentNotDirectory);
                }
                let mut resolved =
                    fs::canonicalize(&cursor).map_err(|_| MigrationDestinationError::IoError)?;
                for name in absent.into_iter().rev() {
                    resolved.push(name);
                }
                return Ok(resolved);
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                let name = cursor
                    .file_name()
                    .ok_or(MigrationDestinationError::DestinationParentUnavailable)?
                    .to_os_string();
                absent.push(name);
                cursor = cursor
                    .parent()
                    .ok_or(MigrationDestinationError::DestinationParentUnavailable)?
                    .to_path_buf();
            }
            Err(_) => return Err(MigrationDestinationError::IoError),
        }
    }
}

/// Called ONLY by the already-authorized SQLCipher writer after validating
/// source and independent backup. A preview never creates the directories.
pub(crate) fn create_missing_destination_parent(destination: &Path) -> Result<(), String> {
    let parent = destination.parent().ok_or("Missing destination parent")?;
    let mut absent = Vec::new();
    let mut cursor = parent.to_path_buf();
    loop {
        match fs::symlink_metadata(&cursor) {
            Ok(meta) if meta.is_dir() && !meta.file_type().is_symlink() => break,
            Ok(_) => return Err("Unsafe destination directory component".into()),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                absent.push(cursor.clone());
                cursor = cursor
                    .parent()
                    .ok_or("Cannot find real ancestor of destination")?
                    .to_path_buf();
            }
            Err(_) => return Err("Cannot inspect destination directory".into()),
        }
    }
    for dir in absent.iter().rev() {
        // Atomic create-directory never replaces an existing symlink or file.
        fs::create_dir(dir).map_err(|_| "Cannot create selected destination directory")?;
    }
    Ok(())
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
    match fs::symlink_metadata(destination) {
        Ok(_) => return Err(MigrationDestinationError::DestinationExists),
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {}
        Err(_) => return Err(MigrationDestinationError::IoError),
    }
    let parent = destination
        .parent()
        .ok_or(MigrationDestinationError::DestinationParentUnavailable)?;
    // A brand-new installation may choose a not-yet-created data directory.
    // Preview inspects the existing ancestor without creating any directory.
    let parent = inspected_future_parent(parent)?;
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
    let success =
        unsafe { get_file_information_by_handle(file.as_raw_handle(), info.as_mut_ptr()) };
    if success == 0 {
        return Err("Cannot read destination directory file ID".to_owned());
    }
    let info = unsafe { info.assume_init() };
    Ok((
        info.volume_serial,
        (u64::from(info.index_high) << 32) | u64::from(info.index_low),
    ))
}

/// Compare native file identities, not just two path strings. A
/// hard-linked copy is not a separate backup.
#[cfg(unix)]
pub(crate) fn same_underlying_file(a: &Path, b: &Path) -> Result<bool, String> {
    use std::os::unix::fs::MetadataExt;
    let left = fs::metadata(a).map_err(|_| "Cannot identify source file")?;
    let right = fs::metadata(b).map_err(|_| "Cannot identify backup file")?;
    Ok(left.dev() == right.dev() && left.ino() == right.ino())
}

#[cfg(windows)]
pub(crate) fn same_underlying_file(a: &Path, b: &Path) -> Result<bool, String> {
    use std::os::windows::io::AsRawHandle;
    fn identity(path: &Path) -> Result<DirectoryIdentity, String> {
        let f = fs::File::open(path).map_err(|_| "Cannot open backup identity handle")?;
        if !f
            .metadata()
            .map_err(|_| "Cannot inspect backup identity")?
            .is_file()
        {
            return Err("Backup identity is not a regular file".to_owned());
        }
        let mut info = std::mem::MaybeUninit::<WindowsFileInformation>::uninit();
        let success =
            unsafe { get_file_information_by_handle(f.as_raw_handle(), info.as_mut_ptr()) };
        if success == 0 {
            return Err("Cannot identify backup file".to_owned());
        }
        let info = unsafe { info.assume_init() };
        Ok((
            info.volume_serial,
            (u64::from(info.index_high) << 32) | u64::from(info.index_low),
        ))
    }
    Ok(identity(a)? == identity(b)?)
}

impl PinnedDestinationParent {
    pub(crate) fn open(preview: &MigrationDestinationPreview) -> Result<Self, String> {
        let parent = preview
            .destination
            .parent()
            .ok_or("Destination directory unavailable")?;
        let meta =
            fs::symlink_metadata(parent).map_err(|_| "Cannot inspect destination directory")?;
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

    /// Check the pinned parent even after the target has legitimately been
    /// created. The full preview check below intentionally rejects occupied
    /// final targets and is therefore only valid *before* publication.
    pub(crate) fn revalidate_identity(&self) -> Result<(), String> {
        let parent = self
            .preview
            .destination
            .parent()
            .ok_or("Destination directory unavailable")?;
        let meta = fs::symlink_metadata(parent).map_err(|_| "Destination directory disappeared")?;
        if meta.file_type().is_symlink() || !meta.is_dir() {
            return Err("Destination directory changed or is a symlink".to_owned());
        }
        let path_handle = open_directory(parent)?;
        if directory_identity(&path_handle)? != self.identity {
            return Err("Destination directory identity changed".to_owned());
        }
        Ok(())
    }

    pub(crate) fn revalidate(&self) -> Result<(), String> {
        self.revalidate_identity()?;
        let parent = self
            .preview
            .destination
            .parent()
            .ok_or("Destination directory unavailable")?;
        let meta = fs::symlink_metadata(parent).map_err(|_| "Destination directory disappeared")?;
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

// Test-only Unix proof of create-if-absent using two pinned directory FDs.
// No selected final migration filename is passed to linkat or unlinkat.
// This must not be confused with authorized, durable final publication.
#[cfg(all(test, unix))]
unsafe extern "C" {
    fn linkat(
        olddirfd: std::os::raw::c_int,
        oldpath: *const std::os::raw::c_char,
        newdirfd: std::os::raw::c_int,
        newpath: *const std::os::raw::c_char,
        flags: std::os::raw::c_int,
    ) -> std::os::raw::c_int;
    fn unlinkat(
        dirfd: std::os::raw::c_int,
        path: *const std::os::raw::c_char,
        flags: std::os::raw::c_int,
    ) -> std::os::raw::c_int;
}

#[cfg(all(test, unix))]
impl PinnedDestinationParent {
    fn rehearse_exclusive_relative_link(
        &self,
        staged_parent: &fs::File,
        staged_name: &std::ffi::OsStr,
        rehearsal_name: &std::ffi::OsStr,
    ) -> Result<(), String> {
        use std::os::unix::ffi::OsStrExt;
        use std::os::unix::io::AsRawFd;

        fn normal_name(name: &std::ffi::OsStr) -> Result<std::ffi::CString, String> {
            let path = Path::new(name);
            let mut parts = path.components();
            if !matches!(parts.next(), Some(std::path::Component::Normal(_)))
                || parts.next().is_some()
            {
                return Err("Rehearsal filename must be a single normal component".into());
            }
            std::ffi::CString::new(name.as_bytes())
                .map_err(|_| "Rehearsal filename contains a NUL byte".to_owned())
        }

        let source = normal_name(staged_name)?;
        let destination = normal_name(rehearsal_name)?;
        if !rehearsal_name
            .as_bytes()
            .starts_with(b"minglefield-rehearsal-")
            || self.preview.destination.file_name() == Some(rehearsal_name)
        {
            return Err("Only private rehearsal link names are permitted".into());
        }
        if !staged_parent
            .metadata()
            .map_err(|_| "Cannot validate staged directory handle")?
            .is_dir()
        {
            return Err("Staged source handle is not a directory".into());
        }
        self.revalidate()?;
        let created = unsafe {
            linkat(
                staged_parent.as_raw_fd(),
                source.as_ptr(),
                self._directory.as_raw_fd(),
                destination.as_ptr(),
                0,
            )
        };
        if created != 0 {
            return Err("Exclusive directory-relative rehearsal link rejected".into());
        }
        // A second create of the SAME name must fail with AlreadyExists.
        let duplicate = unsafe {
            linkat(
                staged_parent.as_raw_fd(),
                source.as_ptr(),
                self._directory.as_raw_fd(),
                destination.as_ptr(),
                0,
            )
        };
        let collision_rejected = duplicate != 0
            && std::io::Error::last_os_error().kind() == std::io::ErrorKind::AlreadyExists;
        // Cleanup is also relative to the original pinned directory FD;
        // never delete a pathname resolved through a substituted parent.
        let removed = unsafe { unlinkat(self._directory.as_raw_fd(), destination.as_ptr(), 0) };
        if removed != 0 {
            return Err("Cannot clean pinned-directory rehearsal link".into());
        }
        self.revalidate()?;
        if !collision_rejected {
            return Err("Native relative link failed to reject duplicate target".into());
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
    fn uncreated_data_parent_is_allowed_without_preview_side_effects() {
        let root = temp_root();
        fs::create_dir_all(&root).unwrap();
        let source = root.join("old.sqlite3");
        fs::write(&source, b"original").unwrap();
        let destination = root.join("data").join("nested").join("new.sqlite3");
        let preview = preview_migration_destination(&source, &destination).unwrap();
        // macOS transparently resolves /var to /private/var. Compare with
        // the canonical existing ancestor rather than its textual alias.
        assert_eq!(
            preview.destination,
            fs::canonicalize(&root)
                .unwrap()
                .join("data/nested/new.sqlite3")
        );
        assert!(!destination.parent().unwrap().exists());
        create_missing_destination_parent(&destination).unwrap();
        assert!(destination.parent().unwrap().is_dir());
        assert!(!destination.exists());
        assert_eq!(fs::read(&source).unwrap(), b"original");
        assert!(preview_migration_destination(&source, &destination).is_ok());
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

    #[cfg(unix)]
    #[test]
    fn relative_link_rehearsal_is_exclusive_and_cleans_only_its_own_name() {
        let root = temp_root();
        let source_dir = root.join("original");
        let destination_dir = root.join("target");
        let staging_dir = destination_dir.join("private-stage");
        fs::create_dir_all(&source_dir).unwrap();
        fs::create_dir_all(&staging_dir).unwrap();
        let source = source_dir.join("alpha.sqlite3");
        fs::write(&source, b"original").unwrap();
        let expected = destination_dir.join("encrypted.sqlite3");
        let stage_file = staging_dir.join("stage.sqlite3");
        fs::write(&stage_file, b"verified encrypted fixture").unwrap();
        let preview = preview_migration_destination(&source, &expected).unwrap();
        let guard = PinnedDestinationParent::open(&preview).unwrap();
        let stage_handle = fs::File::open(&staging_dir).unwrap();
        let proof_name = std::ffi::OsStr::new("minglefield-rehearsal-verified.sqlite3");
        guard
            .rehearse_exclusive_relative_link(
                &stage_handle,
                std::ffi::OsStr::new("stage.sqlite3"),
                proof_name,
            )
            .unwrap();
        assert!(!destination_dir.join(proof_name).exists());
        assert!(!expected.exists());
        assert_eq!(
            fs::read(&stage_file).unwrap(),
            b"verified encrypted fixture"
        );
        assert_eq!(fs::read(&source).unwrap(), b"original");

        // A preexisting unrelated target cannot be overwritten or removed.
        let occupied = destination_dir.join(proof_name);
        fs::write(&occupied, b"existing user bytes").unwrap();
        assert!(guard
            .rehearse_exclusive_relative_link(
                &stage_handle,
                std::ffi::OsStr::new("stage.sqlite3"),
                proof_name,
            )
            .is_err());
        assert_eq!(fs::read(&occupied).unwrap(), b"existing user bytes");
        assert!(guard
            .rehearse_exclusive_relative_link(
                &stage_handle,
                std::ffi::OsStr::new("stage.sqlite3"),
                std::ffi::OsStr::new("encrypted.sqlite3"),
            )
            .is_err());
        drop(stage_handle);
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
        // Reusing the familiar database filename in a DIFFERENT new
        // directory is safe. Only the original pathname/physical file is
        // protected against replacement.
        let same_name_elsewhere = preview_migration_destination(
            &source, &target_dir.join("alpha.sqlite3")
        ).unwrap();
        assert_eq!(
            same_name_elsewhere.destination,
            fs::canonicalize(&target_dir)
                .unwrap()
                .join("alpha.sqlite3")
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
