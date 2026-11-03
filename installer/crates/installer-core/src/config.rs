use crate::{default_user_paths, plan, InstallPlan, InstallRequest, Mode, PlanError};

pub const CONFIG_VERSION: u32 = 1;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InstallerConfig {
    pub version: u32,
    pub install_dir: String,
    pub data_dir: String,
    pub install_optional_conda: bool,
    pub install_optional_comfyui: bool,
    pub explicit_optional_consent: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConfigError {
    UnsupportedVersion,
    InvalidDataDirectory,
    Plan(PlanError),
    MissingPlatformDirectory(&'static str),
}

impl InstallerConfig {
    pub fn defaults() -> Result<Self, ConfigError> {
        let paths = default_user_paths().map_err(ConfigError::MissingPlatformDirectory)?;
        Ok(Self {
            version: CONFIG_VERSION,
            install_dir: paths.install,
            data_dir: paths.data,
            install_optional_conda: false,
            install_optional_comfyui: false,
            explicit_optional_consent: false,
        })
    }

    pub fn preview(&self, mode: Mode) -> Result<InstallPlan, ConfigError> {
        if self.version != CONFIG_VERSION {
            return Err(ConfigError::UnsupportedVersion);
        }
        let data = std::path::Path::new(&self.data_dir);
        if !data.is_absolute()
            || data.components().any(|c| matches!(c, std::path::Component::ParentDir))
        {
            return Err(ConfigError::InvalidDataDirectory);
        }
        plan(&InstallRequest {
            mode,
            install_dir: self.install_dir.clone(),
            install_optional_conda: self.install_optional_conda,
            install_optional_comfyui: self.install_optional_comfyui,
            explicit_optional_consent: self.explicit_optional_consent,
        })
        .map_err(ConfigError::Plan)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base() -> InstallerConfig {
        let path = std::env::temp_dir().to_string_lossy().into_owned();
        InstallerConfig {
            version: CONFIG_VERSION,
            install_dir: path.clone(),
            data_dir: path,
            install_optional_conda: false,
            install_optional_comfyui: false,
            explicit_optional_consent: false,
        }
    }

    #[test]
    fn version_mismatch_fails_closed() {
        let mut config = base();
        config.version += 1;
        assert_eq!(config.preview(Mode::Silent), Err(ConfigError::UnsupportedVersion));
    }

    #[test]
    fn gui_and_cli_use_identical_validation() {
        let config = base();
        assert_eq!(config.preview(Mode::Gui), config.preview(Mode::Silent));
    }

    #[test]
    fn unsafe_data_path_and_optional_installs_fail_closed() {
        let mut config = base();
        config.data_dir = "relative".to_string();
        assert_eq!(config.preview(Mode::Silent), Err(ConfigError::InvalidDataDirectory));
        config = base();
        config.install_optional_comfyui = true;
        assert_eq!(
            config.preview(Mode::Silent),
            Err(ConfigError::Plan(PlanError::OptionalConsentRequired))
        );
    }
}
