//! Shared, side-effect-free installation planning for GUI and CLI.
//! This crate does not install files, claim Hosts, or establish publisher trust.

use std::path::{Component, Path};

/// Resolve the current user's default installation destination for both GUI and CLI.
/// A missing home directory is an error, never a fallback to a relative path.
pub fn default_destination() -> Result<String, &'static str> {
    if cfg!(windows) {
        std::env::var("LOCALAPPDATA")
            .map(|v| format!("{v}\\\\Programs\\\\Minglefield"))
            .map_err(|_| "LOCALAPPDATA is not set")
    } else if cfg!(target_os = "macos") {
        std::env::var("HOME")
            .map(|v| format!("{v}/Applications/Minglefield"))
            .map_err(|_| "HOME is not set")
    } else {
        std::env::var("HOME")
            .map(|v| format!("{v}/.local/opt/Minglefield"))
            .map_err(|_| "HOME is not set")
    }
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
