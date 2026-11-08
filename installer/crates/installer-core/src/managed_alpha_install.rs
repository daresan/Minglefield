//! Shared bounded Alpha file installation for GUI and CLI using a pinned inventory.
//! This intentionally does NOT provision a Host, unlock a database or launch
//! the application. The user must authorize those separate first-run actions.
use crate::integrity::{sha256_hex, sha256_reader_hex};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs::{self, File, OpenOptions};
use std::io;
use std::path::{Component, Path, PathBuf};

const INVENTORY_NAME: &str = "managed-file-inventory.json";
const MAX_INVENTORY_BYTES: u64 = 16 * 1024 * 1024;
const MAX_FILES: usize = 40_000;
const MAX_FILE_BYTES: u64 = 90 * 1024 * 1024;
const MAX_BUNDLE_BYTES: u64 = 2 * 1024 * 1024 * 1024;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Inventory {
    #[serde(rename = "schemaVersion")]
    schema_version: u32,
    files: BTreeMap<String, InventoryEntry>,
}

#[derive(Deserialize)]
#[serde(tag = "type", rename_all = "snake_case", deny_unknown_fields)]
enum InventoryEntry {
    File { size: u64, sha256: String },
    Symlink { target: String },
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ApplicationFilesInstalled {
    pub status: &'static str,
    pub install_dir: String,
    pub installed_entries: usize,
    pub host_provisioning_enabled: bool,
    pub application_launch_enabled: bool,
}

fn relative_install_path(name: &str) -> Result<PathBuf, String> {
    if name.is_empty() || name.contains('\\') || name.contains(':') || name.contains('\0') {
        return Err("Invalid application inventory file name".to_owned());
    }
    let path = Path::new(name);
    if path
        .components()
        .any(|part| !matches!(part, Component::Normal(_)))
    {
        return Err("Application inventory contains an unsafe path".to_owned());
    }
    Ok(path.to_path_buf())
}

fn check_regular_file(path: &Path, expected_size: u64, digest: &str) -> Result<(), String> {
    let metadata =
        fs::symlink_metadata(path).map_err(|_| "Missing managed Alpha source file".to_owned())?;
    if metadata.file_type().is_symlink()
        || !metadata.is_file()
        || metadata.len() != expected_size
        || expected_size > MAX_FILE_BYTES
    {
        return Err("Invalid managed Alpha file type or length".to_owned());
    }
    let (actual, length) = sha256_reader_hex(
        File::open(path).map_err(|_| "Cannot open managed Alpha source file".to_owned())?,
    )
    .map_err(|_| "Cannot hash managed Alpha source file".to_owned())?;
    if length != expected_size || actual != digest {
        return Err("Managed Alpha source digest mismatch".to_owned());
    }
    Ok(())
}

pub fn verified_inventory(source: &Path, expected_digest: &str) -> Result<Inventory, String> {
    if expected_digest.len() != 64
        || !expected_digest
            .bytes()
            .all(|character| character.is_ascii_hexdigit() && !character.is_ascii_uppercase())
    {
        return Err("No pinned application inventory digest available".to_owned());
    }
    let manifest = source.join(INVENTORY_NAME);
    let meta = fs::symlink_metadata(&manifest)
        .map_err(|_| "Managed Alpha inventory unavailable".to_owned())?;
    if meta.file_type().is_symlink() || !meta.is_file() || meta.len() > MAX_INVENTORY_BYTES {
        return Err("Managed Alpha inventory is not a bounded regular file".to_owned());
    }
    let contents = fs::read(&manifest).map_err(|_| "Cannot read managed Alpha inventory")?;
    if contents.len() as u64 != meta.len() || sha256_hex(&contents) != expected_digest {
        return Err("Managed Alpha inventory does not match the compiled package".to_owned());
    }
    let inventory: Inventory =
        serde_json::from_slice(&contents).map_err(|_| "Invalid managed Alpha inventory")?;
    if inventory.schema_version != 1
        || inventory.files.is_empty()
        || inventory.files.len() > MAX_FILES
    {
        return Err("Unsupported or oversized managed Alpha inventory".to_owned());
    }
    if !inventory
        .files
        .contains_key("application/server/installed_alpha_launch.py")
    {
        return Err("Managed Alpha application entrypoint is missing".to_owned());
    }
    let mut total = 0_u64;
    let mut has_python = false;
    for (name, entry) in &inventory.files {
        let relative = relative_install_path(name)?;
        let source_file = source.join(&relative);
        match entry {
            InventoryEntry::File { size, sha256 } => {
                total = total
                    .checked_add(*size)
                    .ok_or("Managed Alpha size overflow")?;
                if total > MAX_BUNDLE_BYTES {
                    return Err("Managed Alpha installation exceeds size limit".to_owned());
                }
                check_regular_file(&source_file, *size, sha256)?;
                if name.ends_with("python.exe") || name.ends_with("bin/python3.11") {
                    has_python = true;
                }
            }
            InventoryEntry::Symlink { target } => {
                let metadata = fs::symlink_metadata(&source_file)
                    .map_err(|_| "Missing Alpha runtime symlink")?;
                if !metadata.file_type().is_symlink()
                    || fs::read_link(&source_file)
                        .map_err(|_| "Cannot read Alpha runtime symlink")?
                        != Path::new(target)
                {
                    return Err("Managed Alpha symlink differs from inventory".to_owned());
                }
                let actual = fs::canonicalize(&source_file)
                    .map_err(|_| "Cannot resolve Alpha runtime symlink")?;
                if !actual.starts_with(source) {
                    return Err(
                        "Managed Alpha runtime link leaves the installation source".to_owned()
                    );
                }
            }
        }
    }
    if !has_python {
        return Err("Managed Alpha Python executable is missing".to_owned());
    }
    Ok(inventory)
}

pub fn verify_installed_application(source: &Path, expected_digest: &str) -> Result<(), String> {
    verified_inventory(source, expected_digest).map(|_| ())
}

fn ensure_real_directories(directory: &Path) -> Result<(), String> {
    let mut absent = Vec::new();
    let mut path = directory.to_path_buf();
    loop {
        match fs::symlink_metadata(&path) {
            Ok(meta) if meta.is_dir() && !meta.file_type().is_symlink() => break,
            Ok(_) => return Err("Install path includes a file or symlink".to_owned()),
            Err(e) if e.kind() == io::ErrorKind::NotFound => {
                absent.push(path.clone());
                path = path
                    .parent()
                    .ok_or("Cannot find existing installation ancestor")?
                    .to_path_buf();
            }
            Err(_) => return Err("Cannot inspect installation parent directory".to_owned()),
        }
    }
    for dir in absent.iter().rev() {
        fs::create_dir(dir).map_err(|_| "Cannot create new installation directory")?;
    }
    Ok(())
}

/// Copy only manifest-declared files into a never-before-existing directory.
/// Failure leaves an incomplete NEW directory for manual inspection; the
/// original application data, database and independent backup are not touched.
pub fn install_from_verified_root(
    source: &Path,
    destination: &Path,
    expected_digest: &str,
) -> Result<ApplicationFilesInstalled, String> {
    let source_meta =
        fs::symlink_metadata(source).map_err(|_| "Managed Alpha source unavailable")?;
    if source_meta.file_type().is_symlink() || !source_meta.is_dir() {
        return Err("Managed Alpha source must be a real directory".to_owned());
    }
    let source = fs::canonicalize(source).map_err(|_| "Cannot identify managed Alpha source")?;
    if !destination.is_absolute()
        || destination
            .components()
            .any(|part| matches!(part, Component::CurDir | Component::ParentDir))
        || destination.file_name().is_none()
    {
        return Err("Installation destination must be a new absolute directory".to_owned());
    }
    let inventory = verified_inventory(&source, expected_digest)?;
    let parent = destination
        .parent()
        .ok_or("Installation destination has no parent")?;

    // Do not create anything during preview or while inventory verification
    // is still pending. A new parent is a perfectly normal first-install path.
    let mut cursor = parent;
    while let Err(error) = fs::symlink_metadata(cursor) {
        if error.kind() != io::ErrorKind::NotFound {
            return Err("Cannot inspect installation ancestor".into());
        }
        cursor = cursor.parent().ok_or("Installation ancestor is missing")?;
    }
    let ancestor =
        fs::symlink_metadata(cursor).map_err(|_| "Cannot validate installation ancestor")?;
    if ancestor.file_type().is_symlink() || !ancestor.is_dir() {
        return Err("Installation ancestor must be a real directory".into());
    }
    if source.starts_with(destination) || destination.starts_with(&source) {
        return Err("Installation must not overlap its source".into());
    }
    // Existing data folders are acceptable. The encrypted DB may already be
    // present at the user's chosen root. Never replace existing managed
    // application paths, symlinks, runtime files, or foreign user contents.
    let mut existing = false;
    match fs::symlink_metadata(destination) {
        Ok(meta) if meta.is_dir() && !meta.file_type().is_symlink() => existing = true,
        Ok(_) => return Err("Installation path is occupied by a file or symlink".into()),
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Err(_) => return Err("Cannot inspect installation destination".into()),
    }
    if existing {
        for name in inventory.files.keys() {
            let top = Path::new(name)
                .components()
                .next()
                .ok_or("Managed application inventory has no root component")?;
            let item = destination.join(top.as_os_str());
            match fs::symlink_metadata(item) {
                Ok(_) => {
                    return Err(
                        "Existing application files would conflict with installation".into(),
                    )
                }
                Err(err) if err.kind() == io::ErrorKind::NotFound => {}
                Err(_) => return Err("Cannot inspect existing application entries".into()),
            }
        }
        for name in [INVENTORY_NAME, "runtime-manifest.json"] {
            if fs::symlink_metadata(destination.join(name)).is_ok() {
                return Err("Existing managed application metadata must not be overwritten".into());
            }
        }
    }
    ensure_real_directories(parent)?;
    if !existing {
        fs::create_dir(destination)
            .map_err(|_| "Cannot exclusively create application directory")?;
    }
    let target = fs::canonicalize(destination)
        .map_err(|_| "Cannot resolve created installation destination")?;
    let mut links = Vec::new();
    for (name, entry) in &inventory.files {
        let relative = relative_install_path(name)?;
        let dest = target.join(&relative);
        fs::create_dir_all(
            dest.parent()
                .ok_or("Managed application entry has no parent")?,
        )
        .map_err(|_| "Cannot create managed application subdirectory")?;
        match entry {
            InventoryEntry::File { size, sha256 } => {
                let src = source.join(&relative);
                check_regular_file(&src, *size, sha256)?;
                let mut input =
                    File::open(&src).map_err(|_| "Cannot reopen verified managed Alpha file")?;
                let mut output = OpenOptions::new()
                    .write(true)
                    .create_new(true)
                    .open(&dest)
                    .map_err(|_| "Cannot exclusively create managed application file")?;
                io::copy(&mut input, &mut output)
                    .map_err(|_| "Cannot copy managed Alpha application bytes")?;
                output
                    .sync_all()
                    .map_err(|_| "Cannot flush managed Alpha application file")?;
                fs::set_permissions(
                    &dest,
                    fs::metadata(&src)
                        .map_err(|_| "Cannot inspect managed Alpha permissions")?
                        .permissions(),
                )
                .map_err(|_| "Cannot preserve managed Alpha file permissions")?;
                check_regular_file(&dest, *size, sha256)?;
            }
            InventoryEntry::Symlink { target: link } => links.push((dest, link.clone(), relative)),
        }
    }
    for (dest, link, relative) in links {
        let src = source.join(&relative);
        if !fs::canonicalize(&src)
            .map_err(|_| "Managed Alpha link changed during installation")?
            .starts_with(&source)
        {
            return Err("Managed Alpha link escapes its source".to_owned());
        }
        #[cfg(unix)]
        std::os::unix::fs::symlink(&link, &dest)
            .map_err(|_| "Cannot recreate managed Alpha runtime symlink")?;
        #[cfg(windows)]
        {
            let target_metadata =
                fs::metadata(&src).map_err(|_| "Cannot identify managed Alpha link target")?;
            if target_metadata.is_dir() {
                std::os::windows::fs::symlink_dir(&link, &dest)
                    .map_err(|_| "Cannot recreate managed Alpha runtime directory symlink")?;
            } else {
                std::os::windows::fs::symlink_file(&link, &dest)
                    .map_err(|_| "Cannot recreate managed Alpha runtime file symlink")?;
            }
        }
    }
    for name in ["runtime-manifest.json", INVENTORY_NAME] {
        let src = source.join(name);
        let metadata = fs::symlink_metadata(&src)
            .map_err(|_| "Managed Alpha installation metadata is absent")?;
        if metadata.file_type().is_symlink()
            || !metadata.is_file()
            || metadata.len() > MAX_INVENTORY_BYTES
        {
            return Err("Managed Alpha installation metadata is invalid".to_owned());
        }
        let mut input =
            File::open(&src).map_err(|_| "Cannot open managed Alpha installation metadata")?;
        let mut output = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(target.join(name))
            .map_err(|_| "Managed Alpha installation metadata is already occupied")?;
        io::copy(&mut input, &mut output)
            .map_err(|_| "Cannot copy managed Alpha installation metadata")?;
    }
    Ok(ApplicationFilesInstalled {
        status: "alpha_application_files_installed",
        install_dir: target.to_string_lossy().into_owned(),
        installed_entries: inventory.files.len(),
        host_provisioning_enabled: false,
        application_launch_enabled: false,
    })
}

/// An explicitly approved installation may reuse a valid existing application
/// or archive *only conflicting managed top-level names* before installing a
/// newly verified package. Foreign files are neither deleted nor replaced.
/// This operation is not invoked by developer diagnostic or preview buttons.
pub fn install_or_reuse_application(
    source: &Path,
    destination: &Path,
    pinned_inventory: &str,
    approve_existing: bool,
) -> Result<(ApplicationFilesInstalled, bool), String> {
    let inventory = verified_inventory(source, pinned_inventory)?;
    if verify_installed_application(destination, pinned_inventory).is_ok() {
        return Ok((
            ApplicationFilesInstalled {
                status: "alpha_application_files_installed",
                install_dir: fs::canonicalize(destination)
                    .map_err(|_| "Cannot identify existing Minglefield installation")?
                    .to_string_lossy()
                    .into_owned(),
                installed_entries: inventory.files.len(),
                host_provisioning_enabled: false,
                application_launch_enabled: false,
            },
            true,
        ));
    }
    let existing = match fs::symlink_metadata(destination) {
        Ok(metadata) if metadata.is_dir() && !metadata.file_type().is_symlink() => true,
        Ok(_) => return Err("Application destination is not a real directory".into()),
        Err(error) if error.kind() == io::ErrorKind::NotFound => false,
        Err(_) => return Err("Cannot inspect application destination".into()),
    };
    if !existing {
        return install_from_verified_root(source, destination, pinned_inventory)
            .map(|result| (result, false));
    }
    let mut roots = std::collections::BTreeSet::new();
    for entry in inventory.files.keys() {
        let relative = relative_install_path(entry)?;
        let first = relative
            .components()
            .next()
            .ok_or("Managed application entry has no top-level directory")?;
        roots.insert(first.as_os_str().to_os_string());
    }
    roots.insert(std::ffi::OsString::from(INVENTORY_NAME));
    roots.insert(std::ffi::OsString::from("runtime-manifest.json"));
    let has_conflicts = roots
        .iter()
        .any(|name| fs::symlink_metadata(destination.join(name)).is_ok());
    if !has_conflicts {
        // An existing empty (or non-conflicting) folder does NOT constitute
        // replacement of application files and needs no separate warning.
        return install_from_verified_root(source, destination, pinned_inventory)
            .map(|result| (result, false));
    }
    if !approve_existing {
        return Err("Existing managed application files require confirmation".into());
    }
    // A staged package is complete and hash-verified before anything in the
    // existing target can be renamed. Distinct names preserve old files for
    // manual recovery if an OS file handle prevents replacement.
    let parent = destination
        .parent()
        .ok_or("Application destination has no parent")?;
    let id: String = rusqlite::Connection::open_in_memory()
        .and_then(|db| db.query_row("SELECT lower(hex(randomblob(16)))", [], |row| row.get(0)))
        .map_err(|_| "Cannot reserve unique application staging identity")?;
    let stage = parent.join(format!(".minglefield-install-stage-{id}"));
    let backup = parent.join(format!(".minglefield-previous-application-{id}"));
    let staged = install_from_verified_root(source, &stage, pinned_inventory)?;
    fs::create_dir(&backup).map_err(|_| "Cannot preserve previous application entries")?;
    let mut backed_up = Vec::new();
    let mut installed = Vec::new();
    let result = (|| -> Result<(), String> {
        for name in &roots {
            let target_entry = destination.join(name);
            match fs::symlink_metadata(&target_entry) {
                Ok(_) => {
                    fs::rename(&target_entry, backup.join(name))
                        .map_err(|_| "Cannot archive previous application entry")?;
                    backed_up.push(name.clone());
                }
                Err(error) if error.kind() == io::ErrorKind::NotFound => {}
                Err(_) => return Err("Cannot inspect existing application entry".into()),
            }
            fs::rename(stage.join(name), &target_entry)
                .map_err(|_| "Cannot install staged application entry")?;
            installed.push(name.clone());
        }
        verify_installed_application(destination, pinned_inventory)
            .map_err(|_| "Updated installed application failed inventory check".to_owned())
    })();
    if let Err(reason) = result {
        let mut restore_ok = true;
        for name in installed.iter().rev() {
            if fs::rename(destination.join(name), stage.join(name)).is_err() {
                restore_ok = false;
            }
        }
        for name in backed_up.iter().rev() {
            if fs::rename(backup.join(name), destination.join(name)).is_err() {
                restore_ok = false;
            }
        }
        return Err(if restore_ok {
            reason
        } else {
            "Application update interrupted; previous and staged files preserved for manual recovery"
                .into()
        });
    }
    // Only the now-empty internal stage directory is removed. Never delete
    // the backup holding previously installed/foreign application bytes.
    let _ = fs::remove_dir(&stage);
    Ok((
        ApplicationFilesInstalled {
            install_dir: fs::canonicalize(destination)
                .map_err(|_| "Cannot identify updated application directory")?
                .to_string_lossy()
                .into_owned(),
            ..staged
        },
        false,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> (PathBuf, PathBuf, String) {
        let root = std::env::temp_dir().join(format!(
            "mf-core-managed-install-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir(&root).unwrap();
        let source = root.join("source");
        let application = source.join("application/server/installed_alpha_launch.py");
        let python = source.join("runtime/python/bin/python3.11");
        fs::create_dir_all(application.parent().unwrap()).unwrap();
        fs::create_dir_all(python.parent().unwrap()).unwrap();
        fs::write(&application, b"abc").unwrap();
        fs::write(&python, b"def").unwrap();
        let inventory = concat!(
            "{\"schemaVersion\":1,\"files\":{",
            "\"application/server/installed_alpha_launch.py\":",
            "{\"type\":\"file\",\"size\":3,\"sha256\":",
            "\"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\"},",
            "\"runtime/python/bin/python3.11\":",
            "{\"type\":\"file\",\"size\":3,\"sha256\":",
            "\"cb8379ac2098aa165029e3938a51da0bcecfc008fd6795f401178647f96c5b34\"}}}"
        );
        fs::write(source.join(INVENTORY_NAME), inventory).unwrap();
        fs::write(source.join("runtime-manifest.json"), "{}").unwrap();
        (root, source, sha256_hex(inventory.as_bytes()))
    }

    #[test]
    fn empty_or_nonconflicting_existing_directory_needs_no_overwrite_confirmation() {
        let (root, source, digest) = fixture();
        let empty = root.join("Programs-Minglefield");
        fs::create_dir(&empty).unwrap();
        let (_, reused) = install_or_reuse_application(&source, &empty, &digest, false).unwrap();
        assert!(!reused);
        assert!(verify_installed_application(&empty, &digest).is_ok());

        let with_user_files = root.join("Minglefield-with-unrelated-files");
        fs::create_dir(&with_user_files).unwrap();
        fs::write(with_user_files.join("private.sqlite3"), b"user database").unwrap();
        let (_, reused) =
            install_or_reuse_application(&source, &with_user_files, &digest, false).unwrap();
        assert!(!reused);
        assert_eq!(
            fs::read(with_user_files.join("private.sqlite3")).unwrap(),
            b"user database"
        );
        assert!(verify_installed_application(&with_user_files, &digest).is_ok());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn existing_directory_update_archives_old_managed_entries_without_touching_user_files() {
        let (root, source, digest) = fixture();
        let dest = root.join("existing-with-user-files");
        // Use a previously populated destination rather than rejecting it.
        fs::create_dir_all(dest.join("application/server")).unwrap();
        fs::write(dest.join("application/server/legacy.py"), b"older edition").unwrap();
        fs::write(dest.join("unrelated-user-file.txt"), b"do not touch").unwrap();
        assert!(install_or_reuse_application(&source, &dest, &digest, false).is_err());
        let (installed, reused) =
            install_or_reuse_application(&source, &dest, &digest, true).unwrap();
        assert!(!reused);
        assert_eq!(installed.status, "alpha_application_files_installed");
        assert!(verify_installed_application(&dest, &digest).is_ok());
        assert_eq!(
            fs::read(dest.join("unrelated-user-file.txt")).unwrap(),
            b"do not touch"
        );
        let archives: Vec<_> = fs::read_dir(dest.parent().unwrap())
            .unwrap()
            .filter_map(Result::ok)
            .filter(|entry| {
                entry
                    .file_name()
                    .to_string_lossy()
                    .starts_with(".minglefield-previous-application-")
            })
            .collect();
        assert_eq!(archives.len(), 1);
        assert_eq!(
            fs::read(archives[0].path().join("application/server/legacy.py")).unwrap(),
            b"older edition"
        );
        let (_same, reused) = install_or_reuse_application(&source, &dest, &digest, true).unwrap();
        assert!(reused);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn native_core_installs_with_existing_data_and_rejects_reuse() {
        let (root, source, digest) = fixture();
        let target = root.join("data-and-install");
        fs::create_dir(&target).unwrap();
        fs::write(target.join("private.sqlite3"), b"existing encrypted data").unwrap();
        let installed = install_from_verified_root(&source, &target, &digest).unwrap();
        assert_eq!(installed.installed_entries, 2);
        assert_eq!(installed.status, "alpha_application_files_installed");
        assert!(!installed.application_launch_enabled);
        assert_eq!(
            fs::read(target.join("private.sqlite3")).unwrap(),
            b"existing encrypted data"
        );
        assert!(install_from_verified_root(&source, &target, &digest).is_err());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn native_core_rejects_untrusted_or_tampered_inventory_before_write() {
        let (root, source, digest) = fixture();
        let target = root.join("untouched");
        assert!(install_from_verified_root(&source, &target, &"0".repeat(64)).is_err());
        assert!(!target.exists());
        fs::write(source.join("runtime/python/bin/python3.11"), b"corrupt").unwrap();
        assert!(install_from_verified_root(&source, &target, &digest).is_err());
        assert!(!target.exists());
        fs::remove_dir_all(root).unwrap();
    }
}
