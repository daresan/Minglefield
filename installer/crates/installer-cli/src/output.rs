//! Stable JSON output for the read-only installer preview.
use minglefield_installer_core::config::InstallerConfig;
use minglefield_installer_core::InstallPlan;

fn quoted(value: &str) -> String {
    let mut result = String::from("\"");
    for character in value.chars() {
        match character {
            '"' => result.push_str("\\\""),
            '\\' => result.push_str("\\\\"),
            '\n' => result.push_str("\\n"),
            '\r' => result.push_str("\\r"),
            '\t' => result.push_str("\\t"),
            c if c <= '\u{001f}' => {
                result.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => result.push(c),
        }
    }
    result.push('"');
    result
}

pub fn success(config: &InstallerConfig, plan: &InstallPlan) -> String {
    format!(
        "{{\"schema_version\":1,\"status\":\"plan_only\",\"exit_code\":0,\"execution_enabled\":false,\"install_dir\":{},\"data_dir\":{},\"provision_host\":{},\"install_optional_conda\":{},\"install_optional_comfyui\":{}}}",
        quoted(&plan.install_dir),
        quoted(&config.data_dir),
        plan.provision_host,
        plan.install_optional_conda,
        plan.install_optional_comfyui
    )
}

/// Version 2 extends the v1 preview with explicit, independent Git/gh selections.
/// The preview never runs installers or authentication.
pub fn success_v2(
    config: &minglefield_installer_core::config_v2::InstallerConfigV2,
    plan: &InstallPlan,
) -> String {
    let legacy = success(&config.base, plan);
    let prefix = legacy.strip_suffix('}').expect("v1 JSON object");
    let tools = &config.git_tools;
    format!(
        "{prefix},\"config_version\":2,\"install_optional_git\":{},\"install_optional_gh\":{},\"offer_gh_login\":{},\"consent_git\":{},\"consent_gh\":{},\"consent_login\":{}}}",
        tools.install_optional_git,
        tools.install_optional_gh,
        tools.offer_gh_login,
        tools.consent_git,
        tools.consent_gh,
        tools.consent_login
    )
}

/// Reports only the bounded verified file copy. This is NOT a complete
/// application install, database migration, or local Host activation.
pub fn installed_alpha_files(install_dir: &str, entries: usize) -> String {
    format!(
        "{{\"schema_version\":1,\"status\":\"alpha_application_files_installed\",\"exit_code\":0,\"execution_enabled\":true,\"application_launch_enabled\":false,\"host_provisioning_enabled\":false,\"install_dir\":{},\"installed_entries\":{entries}}}",
        quoted(install_dir)
    )
}

/// Versioned V3 extends V2 with DB input fields but never serializes secrets.
pub fn success_v3(
    config: &minglefield_installer_core::config_v3::InstallerConfigV3,
    plan: &InstallPlan,
) -> String {
    success_v2(&config.base, plan).replace("\"config_version\":2", "\"config_version\":3")
}

pub fn failure(code: u8, message: &str) -> String {
    format!(
        "{{\"schema_version\":1,\"status\":\"error\",\"exit_code\":{code},\"execution_enabled\":false,\"error\":{}}}",
        quoted(message)
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn json_escapes_windows_paths_and_control_characters() {
        assert_eq!(
            quoted("C:\\Test\\\"file\n"),
            "\"C:\\\\Test\\\\\\\"file\\n\""
        );
        assert_eq!(quoted("\u{0001}"), "\"\\u0001\"");
    }

    #[test]
    fn preview_json_is_non_executing_and_does_not_claim_host() {
        let config = InstallerConfig::defaults().unwrap();
        let plan = config
            .preview(minglefield_installer_core::Mode::Silent)
            .unwrap();
        let text = success(&config, &plan);
        assert!(text.starts_with("{\"schema_version\":1"));
        assert!(text.contains("\"status\":\"plan_only\""));
        assert!(text.contains("\"execution_enabled\":false"));
        assert!(text.contains("\"provision_host\":false"));
        assert!(text.contains("\"exit_code\":0"));
    }

    #[test]
    fn v2_json_preserves_plan_only_and_independent_gh_option() {
        let source = "version=2\ninstall_optional_conda=false\ninstall_optional_comfyui=false\nexplicit_optional_consent=false\ninstall_optional_git=false\ninstall_optional_gh=true\noffer_gh_login=false\nconsent_git=false\nconsent_gh=true\nconsent_login=false\n";
        let config =
            minglefield_installer_core::config_v2::InstallerConfigV2::parse(source).unwrap();
        let plan = config
            .preview(minglefield_installer_core::Mode::Silent)
            .unwrap();
        let text = success_v2(&config, &plan);
        assert!(text.contains("\"config_version\":2"));
        assert!(text.contains("\"install_optional_git\":false"));
        assert!(text.contains("\"install_optional_gh\":true"));
        assert!(text.contains("\"execution_enabled\":false"));
    }

    #[test]
    fn v3_plan_preview_never_serializes_administrator_authored_secret() {
        let config = minglefield_installer_core::config_v3::InstallerConfigV3::parse(concat!(
            "version=3\ninstall_optional_conda=false\n",
            "install_optional_comfyui=false\nexplicit_optional_consent=false\n",
            "install_optional_git=false\ninstall_optional_gh=false\n",
            "offer_gh_login=false\nconsent_git=false\nconsent_gh=false\n",
            "consent_login=false\ndb_password=SecretNotForPlan9!\n"
        ))
        .unwrap();
        let plan = config
            .preview(minglefield_installer_core::Mode::Silent)
            .unwrap();
        let result = success_v3(&config, &plan);
        assert!(result.contains("\"config_version\":3"));
        assert!(result.contains("\"status\":\"plan_only\""));
        assert!(!result.contains("SecretNotForPlan9!"));
    }

    #[test]
    fn error_is_machine_readable_without_secrets_or_side_effects() {
        let text = failure(3, "invalid \"path\"");
        assert!(text.contains("\"exit_code\":3"));
        assert!(text.contains("\"execution_enabled\":false"));
        assert!(text.contains("invalid \\\"path\\\""));
    }
}
