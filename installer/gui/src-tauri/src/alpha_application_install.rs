//! Local application-file installation using a build-pinned runtime inventory.
//! This intentionally does NOT provision a Host, unlock a database or launch
//! the application. The user must authorize those separate first-run actions.
use minglefield_installer_core::integrity::{sha256_hex, sha256_reader_hex};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs::{self, File};
use std::path::{Component, Path, PathBuf};
use tauri::Manager;

const INVENTORY_NAME: &str = "managed-file-inventory.json";
const MAX_INVENTORY_BYTES: u64 = 16 * 1024 * 1024;
const MAX_FILES: usize = 40_000;
const MAX_FILE_BYTES: u64 = 90 * 1024 * 1024;
const MAX_BUNDLE_BYTES: u64 = 2 * 1024 * 1024 * 1024;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Inventory {
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
    status: &'static str,
    install_dir: String,
    installed_entries: usize,
    host_provisioning_enabled: bool,
    application_launch_enabled: bool,
}

fn relative_install_path(name: &str) -> Result<PathBuf, String> {
    if name.is_empty() || name.contains('\\') || name.contains(':') || name.contains('\0') {
        return Err("Invalid application inventory file name".to_owned());
    }
    let path = Path::new(name);
    if path.components().any(|part| !matches!(part, Component::Normal(_))) {
        return Err("Application inventory contains an unsafe path".to_owned());
    }
    Ok(path.to_path_buf())
}

fn check_regular_file(path: &Path, expected_size: u64, digest: &str) -> Result<(), String> {
    let metadata = fs::symlink_metadata(path)
        .map_err(|_| "Missing managed Alpha source file".to_owned())?;
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

fn verified_inventory(source: &Path, expected_digest: &str) -> Result<Inventory, String> {
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
    if inventory.schema_version != 1 || inventory.files.is_empty() || inventory.files.len() > MAX_FILES
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
                    return Err("Managed Alpha runtime link leaves the installation source".to_owned());
                }
            }
        }
    }
    if !has_python {
        return Err("Managed Alpha Python executable is missing".to_owned());
    }
    Ok(inventory)
}

/// Copy only manifest-declared files into a never-before-existing directory.
/// Failure leaves an incomplete NEW directory for manual inspection; the
/// original application data, database and independent backup are not touched.
fn install_from_verified_root(
    source: &Path,
    destination: &Path,
    expected_digest: &str,
) -> Result<ApplicationFilesInstalled, String> {
    let source_meta =
        fs::symlink_metadata(source).map_err(|_| "Managed Alpha source unavailable")?;
    if source_meta.file_type().is_symlink() || !source_meta.is_dir() {
        return Err("Managed Alpha source must be a real directory".to_owned());
    }
    let source =
        fs::canonicalize(source).map_err(|_| "Cannot identify managed Alpha source")?;
    if !destination.is_absolute()
        || destination
            .components()
            .any(|part| matches!(part, Component::CurDir | Component::ParentDir))
        || destination.file_name().is_none()
    {
        return Err("Installation destination must be a new absolute directory".to_owned());
    }
    let parent = destination
        .parent()
        .ok_or("Installation destination has no parent")?;
    let parent_meta = fs::symlink_metadata(parent)
        .map_err(|_| "Installation parent directory must already exist")?;
    if parent_meta.file_type().is_symlink() || !parent_meta.is_dir() {
        return Err("Installation parent must be a real directory".to_owned());
    }
    let final_parent =
        fs::canonicalize(parent).map_err(|_| "Cannot identify installation parent")?;
    if final_parent.starts_with(&source) || source.starts_with(destination) {
        return Err("Installation must not overlap its source".to_owned());
    }
    let target = final_parent.join(
        destination
            .file_name()
            .ok_or("Installation target filename missing")?,
    );
    // A new file, symlink or directory occupies the name: never overwrite it.
    match fs::symlink_metadata(&target) {
        Ok(_) => return Err("Installation destination is already occupied".to_owned()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
        Err(_) => return Err("Cannot check installation destination".to_owned()),
    }
    let inventory = verified_inventory(&source, expected_digest)?;
    // This is deliberately an exclusive creation rather than a rename that
    // might replace an existing empty directory on Unix.
    fs::create_dir(&target).map_err(|_| "Cannot exclusively create application directory")?;
    let mut links = Vec::new();
    for (name, entry) in &inventory.files {
        let relative = relative_install_path(name)?;
        let dest = target.join(&relative);
        dest.parent()
            .ok_or("Managed application entry has no parent")?
            .to_path_buf();
        fs::create_dir_all(
            dest.parent()
                .ok_or("Managed application entry has no parent")?,
        )
        .map_err(|_| "Cannot create managed application subdirectory")?;
        match entry {
            InventoryEntry::File { size, sha256 } => {
                let src = source.join(&relative);
                check_regular_file(&src, *size, sha256)?;
                fs::copy(&src, &dest)
                    .map_err(|_| "Cannot copy managed Alpha application file")?;
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
            let target_metadata = fs::metadata(&src)
                .map_err(|_| "Cannot identify managed Alpha link target")?;
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
        if metadata.file_type().is_symlink() || !metadata.is_file() || metadata.len() > MAX_INVENTORY_BYTES
        {
            return Err("Managed Alpha installation metadata is invalid".to_owned());
        }
        fs::copy(&src, target.join(name))
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

/// The compiled hash must come from the trusted application bundle build,
/// never from JavaScript, a selected source directory or a command argument.
#[tauri::command]
pub async fn install_alpha_application(
    app: tauri::AppHandle,
    install_dir: String,
) -> Result<ApplicationFilesInstalled, String> {
    let expected = option_env!("MINGLEFIELD_ALPHA_INVENTORY_SHA256")
        .ok_or("Managed Alpha application has not been bundled into this Setup Manager")?;
    let resources = app
        .path()
        .resource_dir()
        .map_err(|_| "Cannot locate application resources")?;
    let bundled = resources.join("managed-alpha");
    let source = if bundled.is_dir() {
        bundled
    } else {
        let executable =
            std::env::current_exe().map_err(|_| "Cannot locate portable Setup Manager")?;
        executable
            .parent()
            .ok_or("Cannot locate portable Setup Manager directory")?
            .join("managed-alpha")
    };
    tauri::async_runtime::spawn_blocking(move || {
        install_from_verified_root(&source, Path::new(&install_dir), expected)
    })
    .await
    .map_err(|_| "Managed Alpha installation worker failed".to_owned())?
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture_root() -> PathBuf {
        let root = std::env::temp_dir().join(format!(
            "mf-managed-installer-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir(&root).unwrap();
        root
    }

    fn fixture(root: &Path) -> (PathBuf, String) {
        let source = root.join("prepared");
        fs::create_dir(&source).unwrap();
        let entry = source.join("application/server/installed_alpha_launch.py");
        fs::create_dir_all(entry.parent().unwrap()).unwrap();
        fs::write(entry, b"abc").unwrap();
        let python = source.join("runtime/python/bin/python3.11");
        fs::create_dir_all(python.parent().unwrap()).unwrap();
        fs::write(python, b"def").unwrap();
        let json = concat!(
            "{\"schemaVersion\":1,\"files\":{",
            "\"application/server/installed_alpha_launch.py\":",
            "{\"type\":\"file\",\"size\":3,\"sha256\":",
            "\"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\"},",
            "\"runtime/python/bin/python3.11\":",
            "{\"type\":\"file\",\"size\":3,\"sha256\":",
            "\"cb8379ac2098aa165029e3938a51da0bcecfc008fd6795f401178647f96c5b34\"}}}"
        );
        fs::write(source.join(INVENTORY_NAME), json).unwrap();
        fs::write(source.join("runtime-manifest.json"), "{}").unwrap();
        (source, sha256_hex(json.as_bytes()))
    }

    #[test]
    fn installs_verified_files_without_touching_source() {
        let root = fixture_root();
        let (src, digest) = fixture(&root);
        let first = fs::read(src.join("application/server/installed_alpha_launch.py")).unwrap();
        let dst = root.join("installed");
        let result = install_from_verified_root(&src, &dst, &digest).unwrap();
        assert_eq!(result.status, "alpha_application_files_installed");
        assert_eq!(result.installed_entries, 2);
        assert!(!result.host_provisioning_enabled);
        assert!(!result.application_launch_enabled);
        assert_eq!(fs::read(src.join("application/server/installed_alpha_launch.py")).unwrap(), first);
        assert_eq!(fs::read(dst.join("application/server/installed_alpha_launch.py")).unwrap(), first);
        assert!(install_from_verified_root(&src, &dst, &digest).is_err());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_unpinned_or_tampered_files_before_creating_destination() {
        let root = fixture_root();
        let (source, digest) = fixture(&root);
        let dst = root.join("should-not-exist");
        assert!(install_from_verified_root(&source, &dst, &"0".repeat(64)).is_err());
        assert!(!dst.exists());
        fs::write(source.join("runtime/python/bin/python3.11"), b"evil").unwrap();
        assert!(install_from_verified_root(&source, &dst, &digest).is_err());
        assert!(!dst.exists());
        fs::remove_dir_all(root).unwrap();
    }
}
