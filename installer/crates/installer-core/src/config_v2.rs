//! Complete, strict v2 installer configuration, without changing v1 behavior.
//! Read-only planning: this module never installs tools or authenticates.

use crate::config::InstallerConfig;
use crate::git_tools_v2::GitToolOptions;
use crate::{InstallPlan, Mode};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InstallerConfigV2 {
    pub base: InstallerConfig,
    pub git_tools: GitToolOptions,
}

impl InstallerConfigV2 {
    pub fn parse(text: &str) -> Result<Self, &'static str> {
        let mut base_lines = Vec::new();
        let mut tool_lines = Vec::new();
        let mut version_seen = false;
        for line in text.lines() {
            let trimmed = line.trim();
            if trimmed.is_empty() || trimmed.starts_with('#') {
                continue;
            }
            let (key, value) = trimmed
                .split_once('=')
                .ok_or("invalid configuration line")?;
            match key.trim() {
                "version" => {
                    if version_seen {
                        return Err("duplicate configuration key");
                    }
                    version_seen = true;
                    if value.trim() != "2" {
                        return Err("unsupported configuration version");
                    }
                    base_lines.push("version=1".to_owned());
                }
                "install_optional_git"
                | "install_optional_gh"
                | "offer_gh_login"
                | "consent_git"
                | "consent_gh"
                | "consent_login" => {
                    tool_lines.push(trimmed.to_owned());
                }
                _ => base_lines.push(trimmed.to_owned()),
            }
        }
        if !version_seen {
            return Err("missing configuration key");
        }
        let base = InstallerConfig::parse(&base_lines.join("\n"))?;
        let git_tools = GitToolOptions::parse(&tool_lines.join("\n"))?;
        Ok(Self { base, git_tools })
    }

    pub fn preview(&self, mode: Mode) -> Result<InstallPlan, &'static str> {
        self.git_tools.validate()?;
        self.base
            .preview(mode)
            .map_err(|_| "invalid base installation plan")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const BASE: &str = "version=2\ninstall_optional_conda=false\ninstall_optional_comfyui=false\nexplicit_optional_consent=false\ninstall_optional_git=false\ninstall_optional_gh=false\noffer_gh_login=false\nconsent_git=false\nconsent_gh=false\nconsent_login=false\n";

    #[test]
    fn v2_default_options_and_preview() {
        let config = InstallerConfigV2::parse(BASE).unwrap();
        assert_eq!(config.git_tools, GitToolOptions::disabled());
        assert!(config.preview(Mode::Silent).is_ok());
    }

    #[test]
    fn v2_independent_gh_selection_and_consent() {
        let text = BASE
            .replace("install_optional_gh=false", "install_optional_gh=true")
            .replace("consent_gh=false", "consent_gh=true");
        let config = InstallerConfigV2::parse(&text).unwrap();
        assert!(config.git_tools.install_optional_gh);
        assert!(!config.git_tools.install_optional_git);
        assert!(config.preview(Mode::Gui).is_ok());
    }

    #[test]
    fn v2_rejects_missing_consent_unknown_and_duplicate_keys() {
        let missing_consent =
            BASE.replace("install_optional_git=false", "install_optional_git=true");
        assert!(InstallerConfigV2::parse(&missing_consent).is_err());
        assert!(InstallerConfigV2::parse(&format!("{BASE}unknown=true\n")).is_err());
        assert!(InstallerConfigV2::parse(&format!("{BASE}consent_git=false\n")).is_err());
        assert!(InstallerConfigV2::parse(&BASE.replace("consent_git=false\n", "")).is_err());
        assert!(InstallerConfigV2::parse(&BASE.replace("version=2", "version=1")).is_err());
    }

    #[test]
    fn v1_parser_still_rejects_v2_fields() {
        assert!(InstallerConfig::parse(BASE).is_err());
    }
}
