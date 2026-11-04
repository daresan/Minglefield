//! Shared, side-effect-free installation planning for GUI and CLI.
//! This crate does not install files, claim Hosts, or establish publisher trust.

pub mod config;
pub mod config_v2;
pub mod consent;
pub mod data_inventory;
pub mod discovery;
pub mod git_tools_v2;
pub mod integrity;
pub mod manifest;
pub mod migration_destination;
pub mod publisher;
pub mod release_source;
pub mod schema_compatibility;
pub mod schema_versions;
pub mod sqlite_inspection;

use std::path::{Component, Path};

/// OS-specific paths mirror server/platform_user_paths.py.
/// The returned install and data paths are distinct and are not created here.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UserPaths {
    pub install: String,
    pub data: String,
}

pub fn user_paths(
    platform: &str,
    local_app_data: Option<&str>,
    home: &str,
    xdg_data_home: Option<&str>,
) -> Result<UserPaths, &'static str> {
    let home = home.trim_end_matches(['/', '\\']);
    match platform {
        "win32" => {
            let local = local_app_data
                .filter(|value| !value.is_empty())
                .ok_or("LOCALAPPDATA must be an absolute directory on Windows")?;
            // Windows absolute paths require a drive prefix or UNC share.
            let bytes = local.as_bytes();
            let drive_absolute = bytes.len() >= 3
                && bytes[0].is_ascii_alphabetic()
                && bytes[1] == b':'
                && (bytes[2] == b'\\' || bytes[2] == b'/');
            let unc_absolute = local.starts_with("\\\\") || local.starts_with("//");
            if !drive_absolute && !unc_absolute {
                return Err("LOCALAPPDATA must be an absolute directory on Windows");
            }
            let local = local.trim_end_matches(['/', '\\']);
            Ok(UserPaths {
                install: format!("{local}\\Programs\\Minglefield"),
                data: format!("{local}\\Minglefield"),
            })
        }
        "darwin" => {
            if !home.starts_with('/') {
                return Err("HOME must be absolute");
            }
            Ok(UserPaths {
                install: format!("{home}/Applications/Minglefield.app"),
                data: format!("{home}/Library/Application Support/Minglefield"),
            })
        }
        value if value.starts_with("linux") => {
            if !home.starts_with('/') {
                return Err("HOME must be absolute");
            }
            let data_root = match xdg_data_home.filter(|value| !value.is_empty()) {
                Some(value) if value.starts_with('/') => value.trim_end_matches('/').to_owned(),
                Some(_) => return Err("XDG_DATA_HOME must be absolute"),
                None => format!("{home}/.local/share"),
            };
            Ok(UserPaths {
                install: format!("{home}/.local/opt/minglefield"),
                data: format!("{data_root}/minglefield"),
            })
        }
        _ => Err("unsupported operating system"),
    }
}

pub fn default_user_paths() -> Result<UserPaths, &'static str> {
    let platform = if cfg!(windows) {
        "win32"
    } else if cfg!(target_os = "macos") {
        "darwin"
    } else if cfg!(target_os = "linux") {
        "linux"
    } else {
        return Err("unsupported operating system");
    };
    let home =
        std::env::var(if cfg!(windows) { "USERPROFILE" } else { "HOME" }).unwrap_or_default();
    let local = std::env::var("LOCALAPPDATA").ok();
    let xdg = std::env::var("XDG_DATA_HOME").ok();
    user_paths(platform, local.as_deref(), &home, xdg.as_deref())
}

/// Read-only discovery roots for existing installations. The first path is
/// the current platform default; additional roots cover older gateway layouts.
/// This does not change the destination for new installations.
pub fn existing_data_search_paths(
    platform: &str,
    local_app_data: Option<&str>,
    home: &str,
    xdg_data_home: Option<&str>,
) -> Result<Vec<String>, &'static str> {
    let primary = user_paths(platform, local_app_data, home, xdg_data_home)?.data;
    let mut paths = vec![primary];
    if platform.starts_with("linux") || platform == "darwin" {
        let home = home.trim_end_matches('/');
        let legacy = format!("{home}/.local/share/Minglefield");
        if !paths.contains(&legacy) {
            paths.push(legacy);
        }
    }
    Ok(paths)
}

#[cfg(test)]
mod existing_data_search_tests {
    use super::existing_data_search_paths;

    #[test]
    fn linux_searches_xdg_and_gateway_legacy_directory() {
        let paths =
            existing_data_search_paths("linux", None, "/home/tester", Some("/tmp/xdg-data"))
                .unwrap();
        assert_eq!(
            paths,
            vec![
                "/tmp/xdg-data/minglefield",
                "/home/tester/.local/share/Minglefield",
            ]
        );
    }

    #[test]
    fn macos_searches_application_support_and_gateway_legacy_directory() {
        let paths = existing_data_search_paths("darwin", None, "/Users/tester", None).unwrap();
        assert_eq!(
            paths,
            vec![
                "/Users/tester/Library/Application Support/Minglefield",
                "/Users/tester/.local/share/Minglefield",
            ]
        );
    }

    #[test]
    fn windows_keeps_single_default_data_directory() {
        let paths = existing_data_search_paths(
            "win32",
            Some("C:\\Users\\Tester\\AppData\\Local"),
            "C:\\Users\\Tester",
            None,
        )
        .unwrap();
        assert_eq!(
            paths,
            vec!["C:\\Users\\Tester\\AppData\\Local\\Minglefield"]
        );
    }
}

pub fn default_existing_data_search_paths() -> Result<Vec<String>, &'static str> {
    let platform = if cfg!(windows) {
        "win32"
    } else if cfg!(target_os = "macos") {
        "darwin"
    } else if cfg!(target_os = "linux") {
        "linux"
    } else {
        return Err("unsupported operating system");
    };
    let home =
        std::env::var(if cfg!(windows) { "USERPROFILE" } else { "HOME" }).unwrap_or_default();
    let local = std::env::var("LOCALAPPDATA").ok();
    let xdg = std::env::var("XDG_DATA_HOME").ok();
    existing_data_search_paths(platform, local.as_deref(), &home, xdg.as_deref())
}

pub fn default_destination() -> Result<String, &'static str> {
    default_user_paths().map(|paths| paths.install)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Gui,
    Silent,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InstallRequest {
    pub mode: Mode,
    pub install_dir: String,
    pub install_optional_conda: bool,
    pub install_optional_comfyui: bool,
    pub explicit_optional_consent: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InstallPlan {
    pub install_dir: String,
    pub provision_host: bool,
    pub install_optional_conda: bool,
    pub install_optional_comfyui: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PlanError {
    EmptyDestination,
    RelativeDestination,
    InvalidDestination,
    OptionalConsentRequired,
}

pub fn plan(request: &InstallRequest) -> Result<InstallPlan, PlanError> {
    if request.install_dir.trim().is_empty() {
        return Err(PlanError::EmptyDestination);
    }
    let path = Path::new(&request.install_dir);
    if !path.is_absolute() {
        return Err(PlanError::RelativeDestination);
    }
    if path
        .components()
        .any(|component| matches!(component, Component::ParentDir))
    {
        return Err(PlanError::InvalidDestination);
    }
    if (request.install_optional_conda || request.install_optional_comfyui)
        && !request.explicit_optional_consent
    {
        return Err(PlanError::OptionalConsentRequired);
    }
    Ok(InstallPlan {
        install_dir: request.install_dir.clone(),
        // Authentication and one-time provisioning are not implemented yet.
        provision_host: false,
        install_optional_conda: request.install_optional_conda,
        install_optional_comfyui: request.install_optional_comfyui,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request() -> InstallRequest {
        InstallRequest {
            mode: Mode::Silent,
            install_dir: std::env::temp_dir().to_string_lossy().into_owned(),
            install_optional_conda: false,
            install_optional_comfyui: false,
            explicit_optional_consent: false,
        }
    }

    #[test]
    fn platform_paths_match_python_reference_contract() {
        let win = user_paths(
            "win32",
            Some("C:\\Users\\Shadow\\AppData\\Local"),
            "C:\\Users\\Other",
            None,
        )
        .unwrap();
        assert_eq!(
            win.install,
            "C:\\Users\\Shadow\\AppData\\Local\\Programs\\Minglefield"
        );
        assert_eq!(win.data, "C:\\Users\\Shadow\\AppData\\Local\\Minglefield");
        assert!(user_paths("win32", None, "C:\\Users\\Shadow", None).is_err());
        assert!(user_paths("win32", Some("relative"), "C:\\Users\\Shadow", None).is_err());

        let mac = user_paths("darwin", None, "/Users/test", None).unwrap();
        assert_eq!(mac.install, "/Users/test/Applications/Minglefield.app");
        assert_eq!(
            mac.data,
            "/Users/test/Library/Application Support/Minglefield"
        );

        let linux = user_paths("linux", None, "/home/test", Some("/var/tmp/xdg")).unwrap();
        assert_eq!(linux.install, "/home/test/.local/opt/minglefield");
        assert_eq!(linux.data, "/var/tmp/xdg/minglefield");
        assert!(user_paths("linux", None, "/home/test", Some("relative")).is_err());
        assert!(user_paths("plan9", None, "/home/test", None).is_err());
    }

    #[test]
    fn safe_plan_has_no_implicit_host_claim_or_optional_installs() {
        let plan = plan(&request()).unwrap();
        assert!(!plan.provision_host);
        assert!(!plan.install_optional_conda);
        assert!(!plan.install_optional_comfyui);
    }

    #[test]
    fn optional_install_requires_explicit_consent() {
        let mut req = request();
        req.install_optional_comfyui = true;
        assert_eq!(plan(&req), Err(PlanError::OptionalConsentRequired));
        req.explicit_optional_consent = true;
        assert!(plan(&req).is_ok());
    }

    #[test]
    fn rejects_relative_and_parent_paths() {
        let mut req = request();
        req.install_dir = "relative/path".into();
        assert_eq!(plan(&req), Err(PlanError::RelativeDestination));
        req.install_dir = format!(
            "{}{}..{}other",
            std::env::temp_dir().display(),
            std::path::MAIN_SEPARATOR,
            std::path::MAIN_SEPARATOR
        );
        assert_eq!(plan(&req), Err(PlanError::InvalidDestination));
    }

    #[test]
    fn rejects_empty_destination() {
        let mut req = request();
        req.install_dir = " ".into();
        assert_eq!(plan(&req), Err(PlanError::EmptyDestination));
    }
}
