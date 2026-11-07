//! Native Tauri adapter for the shared verified managed Alpha file installer.
//! The GUI, headless CLI and tests must use the same installer-core engine.
#[cfg(test)]
use minglefield_installer_core::integrity::sha256_hex;
use minglefield_installer_core::managed_alpha_install::{
    install_from_verified_root, verified_inventory, ApplicationFilesInstalled,
};
#[cfg(test)]
use std::fs;
use std::path::{Path, PathBuf};
use tauri::Manager;

/// The compiled hash must come from the trusted application bundle build,
/// never from JavaScript, a selected source directory or a command argument.
const INSTALL_ALPHA_CONSENT: &str = "INSTALL MINGLEFIELD ALPHA FILES";

fn check_native_install_consent(confirmation: &str) -> Result<(), String> {
    if confirmation != INSTALL_ALPHA_CONSENT {
        return Err(
            "Explicit native approval for Alpha application file installation is required"
                .to_owned(),
        );
    }
    Ok(())
}

fn find_packaged_alpha_source(
    resource_dir: &Path,
    executable_dir: &Path,
    expected_digest: &str,
) -> Result<PathBuf, String> {
    for candidate in [
        resource_dir.join("managed-alpha"),
        executable_dir.join("managed-alpha"),
    ] {
        if candidate.is_dir() && verified_inventory(&candidate, expected_digest).is_ok() {
            return Ok(candidate);
        }
    }
    Err("Alpha application package is missing or incomplete: extract the full portable archive with managed-alpha next to the executable".to_owned())
}

#[tauri::command]
pub async fn install_alpha_application(
    app: tauri::AppHandle,
    install_dir: String,
    confirmation: String,
) -> Result<ApplicationFilesInstalled, String> {
    check_native_install_consent(&confirmation)?;
    let expected = option_env!("MINGLEFIELD_ALPHA_INVENTORY_SHA256")
        .ok_or("Managed Alpha application has not been bundled into this Setup Manager")?;
    let resources = app
        .path()
        .resource_dir()
        .map_err(|_| "Cannot locate application resources")?;
    let executable = std::env::current_exe().map_err(|_| "Cannot locate portable Setup Manager")?;
    let executable_dir = executable
        .parent()
        .ok_or("Cannot locate portable Setup Manager directory")?
        .to_path_buf();
    let installed = tauri::async_runtime::spawn_blocking(move || {
        let source = find_packaged_alpha_source(&resources, &executable_dir, expected)?;
        install_from_verified_root(&source, Path::new(&install_dir), expected)
    })
    .await
    .map_err(|_| "Managed Alpha installation worker failed".to_owned())??;
    app.state::<crate::alpha_first_run::FirstRunState>()
        .record_installed_application(Path::new(&installed.install_dir))?;
    Ok(installed)
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
    fn backend_requires_separate_exact_file_install_consent() {
        assert!(check_native_install_consent("").is_err());
        assert!(check_native_install_consent("INSTALL MINGLEFIELD ALPHA").is_err());
        assert!(check_native_install_consent("install minglefield alpha files").is_err());
        assert!(check_native_install_consent(INSTALL_ALPHA_CONSENT).is_ok());
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
        assert_eq!(
            fs::read(src.join("application/server/installed_alpha_launch.py")).unwrap(),
            first
        );
        assert_eq!(
            fs::read(dst.join("application/server/installed_alpha_launch.py")).unwrap(),
            first
        );
        assert!(install_from_verified_root(&src, &dst, &digest).is_err());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn permits_fresh_nested_parent_and_existing_database_directory() {
        let root = fixture_root();
        let (src, digest) = fixture(&root);
        let nested = root.join("never-created").join("application-install");
        assert!(!nested.parent().unwrap().exists());
        assert!(install_from_verified_root(&src, &nested, &digest).is_ok());
        assert!(nested
            .join("application/server/installed_alpha_launch.py")
            .is_file());
        let with_db = root.join("existing-data");
        fs::create_dir(&with_db).unwrap();
        let database = with_db.join("user-alpha.sqlite3");
        fs::write(&database, b"private data to preserve").unwrap();
        assert!(install_from_verified_root(&src, &with_db, &digest).is_ok());
        assert_eq!(fs::read(&database).unwrap(), b"private data to preserve");
        assert!(install_from_verified_root(&src, &with_db, &digest).is_err());
        assert_eq!(fs::read(&database).unwrap(), b"private data to preserve");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn portable_sibling_package_is_found_when_resource_folder_is_only_a_placeholder() {
        let root = fixture_root();
        let (source, digest) = fixture(&root);
        let placeholder = root.join("resources/managed-alpha");
        fs::create_dir_all(&placeholder).unwrap();
        let exe = root.join("portable");
        fs::create_dir(&exe).unwrap();
        fs::rename(&source, exe.join("managed-alpha")).unwrap();
        assert_eq!(
            find_packaged_alpha_source(&root.join("resources"), &exe, &digest).unwrap(),
            exe.join("managed-alpha")
        );
        assert!(
            find_packaged_alpha_source(&root.join("resources"), &exe, &"0".repeat(64)).is_err()
        );
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
