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
        let plan = config.preview(minglefield_installer_core::Mode::Silent).unwrap();
        let text = success(&config, &plan);
        assert!(text.starts_with("{\"schema_version\":1"));
        assert!(text.contains("\"status\":\"plan_only\""));
        assert!(text.contains("\"execution_enabled\":false"));
        assert!(text.contains("\"provision_host\":false"));
        assert!(text.contains("\"exit_code\":0"));
    }

    #[test]
    fn error_is_machine_readable_without_secrets_or_side_effects() {
        let text = failure(3, "invalid \"path\"");
        assert!(text.contains("\"exit_code\":3"));
        assert!(text.contains("\"execution_enabled\":false"));
        assert!(text.contains("invalid \\\"path\\\""));
    }
}
