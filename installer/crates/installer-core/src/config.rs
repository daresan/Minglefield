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

fn parse_bool(value: &str) -> Result<bool, &'static str> {
    match value {
        "true" => Ok(true),
        "false" => Ok(false),
        _ => Err("boolean must be true or false"),
    }
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

    /// Parse a versioned configuration without allowing unknown keys or implicit consent.
    /// Text file syntax is strict key=value, with UTF-8, no escaping or interpolation.
    pub fn parse(text: &str) -> Result<Self, &'static str> {
        let mut config = Self {
            version: 0,
            install_dir: String::new(),
            data_dir: String::new(),
            install_optional_conda: false,
            install_optional_comfyui: false,
            explicit_optional_consent: false,
        };
        let mut seen = std::collections::HashSet::new();
        for line in text.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let (key, value) = line.split_once('=').ok_or("invalid configuration line")?;
            let key = key.trim();
            let value = value.trim();
            if !seen.insert(key) {
                return Err("duplicate configuration key");
            }
            match key {
                "version" => config.version = value.parse().map_err(|_| "invalid version")?,
                "install_dir" => config.install_dir = value.to_owned(),
                "data_dir" => config.data_dir = value.to_owned(),
                "install_optional_conda" => {
                    config.install_optional_conda = parse_bool(value)?;
                }
                "install_optional_comfyui" => {
                    config.install_optional_comfyui = parse_bool(value)?;
                }
                "explicit_optional_consent" => {
                    config.explicit_optional_consent = parse_bool(value)?;
                }
                _ => return Err("unknown configuration key"),
            }
        }
        for key in [
            "version",
            "install_optional_conda",
            "install_optional_comfyui",
            "explicit_optional_consent",
        ] {
            if !seen.contains(key) {
                return Err("missing configuration key");
            }
        }
        if config.version != CONFIG_VERSION {
            return Err("unsupported configuration version");
        }
        if !seen.contains("install_dir") || !seen.contains("data_dir") {
            let defaults = Self::defaults().map_err(|_| "cannot resolve platform defaults")?;
            if !seen.contains("install_dir") {
                config.install_dir = defaults.install_dir;
            }
            if !seen.contains("data_dir") {
                config.data_dir = defaults.data_dir;
            }
        }
        Ok(config)
    }

    pub fn preview(&self, mode: Mode) -> Result<InstallPlan, ConfigError> {
        if self.version != CONFIG_VERSION {
            return Err(ConfigError::UnsupportedVersion);
        }
        let data = std::path::Path::new(&self.data_dir);
        if !data.is_absolute()
            || data
                .components()
                .any(|c| matches!(c, std::path::Component::ParentDir))
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
    fn parser_rejects_unknown_duplicate_and_incomplete_config() {
        let valid = "version=1\ninstall_dir=/tmp/minglefield\ndata_dir=/tmp/minglefield-data\ninstall_optional_conda=false\ninstall_optional_comfyui=false\nexplicit_optional_consent=false\n";
        assert!(InstallerConfig::parse(valid).is_ok());
        assert!(InstallerConfig::parse(&format!("{valid}unknown=true\n")).is_err());
        assert!(InstallerConfig::parse(&format!("{valid}version=1\n")).is_err());
        assert!(InstallerConfig::parse("version=1").is_err());
        let portable = "version=1\ninstall_optional_conda=false\ninstall_optional_comfyui=false\nexplicit_optional_consent=false\n";
        let parsed = InstallerConfig::parse(portable).unwrap();
        assert!(!parsed.install_dir.is_empty());
        assert!(!parsed.data_dir.is_empty());
        assert!(InstallerConfig::parse(&valid.replace("version=1", "version=2")).is_err());
        assert!(InstallerConfig::parse(&valid.replace("conda=false", "conda=TRUE")).is_err());
    }

    #[test]
    fn version_mismatch_fails_closed() {
        let mut config = base();
        config.version += 1;
        assert_eq!(
            config.preview(Mode::Silent),
            Err(ConfigError::UnsupportedVersion)
        );
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
        assert_eq!(
            config.preview(Mode::Silent),
            Err(ConfigError::InvalidDataDirectory)
        );
        config = base();
        config.install_optional_comfyui = true;
        assert_eq!(
            config.preview(Mode::Silent),
            Err(ConfigError::Plan(PlanError::OptionalConsentRequired))
        );
    }
}
