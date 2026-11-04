use minglefield_installer_core::config::InstallerConfig;
use minglefield_installer_core::config_v2::InstallerConfigV2;
use minglefield_installer_core::Mode;
use serde::Serialize;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct PlanPreview {
    version: u32,
    install_dir: String,
    data_dir: String,
    provision_host: bool,
    install_optional_conda: bool,
    install_optional_comfyui: bool,
    execution_enabled: bool,
    install_optional_git: bool,
    install_optional_gh: bool,
    offer_gh_login: bool,
    consent_git: bool,
    consent_gh: bool,
    consent_login: bool,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct DefaultConfig {
    version: u32,
    install_dir: String,
    data_dir: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct LicenseInfo {
    identifier: &'static str,
    text: &'static str,
}

#[tauri::command]
fn framework_license() -> LicenseInfo {
    LicenseInfo {
        identifier: "GPL-3.0-or-later",
        text: include_str!("../../../../LICENSE"),
    }
}

#[cfg(test)]
mod license_tests {
    #[test]
    fn embedded_framework_license_is_complete() {
        let license = super::framework_license();
        assert_eq!(license.identifier, "GPL-3.0-or-later");
        assert!(license.text.starts_with("GNU GENERAL PUBLIC LICENSE"));
        assert!(license.text.contains("END OF TERMS AND CONDITIONS"));
        assert!(license.text.len() > 30_000);
    }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct SourceInspection {
    kind: &'static str,
    location: String,
    provenance_verified: bool,
    launch_ready: bool,
}

#[tauri::command]
fn inspect_source_path(path: String) -> SourceInspection {
    use minglefield_installer_core::discovery::{inspect_source_directory, CandidateKind};
    let candidate = inspect_source_directory(std::path::Path::new(&path));
    SourceInspection {
        kind: match candidate.kind {
            CandidateKind::SourceCheckout => "source_checkout",
            CandidateKind::Unrecognized => "unrecognized",
        },
        location: candidate.location,
        provenance_verified: candidate.provenance_verified,
        launch_ready: candidate.launch_ready,
    }
}

#[tauri::command]
fn default_configuration() -> Result<DefaultConfig, String> {
    let c = InstallerConfig::defaults().map_err(|err| format!("{err:?}"))?;
    Ok(DefaultConfig {
        version: c.version,
        install_dir: c.install_dir,
        data_dir: c.data_dir,
    })
}

#[tauri::command]
fn preview_install_plan(
    install_dir: String,
    data_dir: String,
    config_text: Option<String>,
) -> Result<PlanPreview, String> {
    let (c, tools, config_version) = if let Some(text) = config_text {
        let version_lines: Vec<&str> = text
            .lines()
            .map(str::trim)
            .filter(|line| {
                line.split_once('=')
                    .is_some_and(|(key, _)| key.trim() == "version")
            })
            .collect();
        if version_lines.len() != 1 {
            return Err("missing or duplicate configuration version".to_owned());
        }
        let version = version_lines[0]
            .split_once('=')
            .map(|(_, value)| value.trim())
            .unwrap_or("");
        if version == "2" {
            let config = InstallerConfigV2::parse(&text).map_err(str::to_string)?;
            config.git_tools.validate().map_err(str::to_string)?;
            (config.base, config.git_tools, 2)
        } else {
            let config = InstallerConfig::parse(&text).map_err(str::to_string)?;
            (
                config,
                minglefield_installer_core::git_tools_v2::GitToolOptions::disabled(),
                1,
            )
        }
    } else {
        let mut c = InstallerConfig::defaults().map_err(|err| format!("{err:?}"))?;
        c.install_dir = install_dir;
        c.data_dir = data_dir;
        (
            c,
            minglefield_installer_core::git_tools_v2::GitToolOptions::disabled(),
            1,
        )
    };
    let p = c.preview(Mode::Gui).map_err(|err| format!("{err:?}"))?;
    Ok(PlanPreview {
        version: config_version,
        install_dir: p.install_dir,
        data_dir: c.data_dir,
        provision_host: p.provision_host,
        install_optional_conda: p.install_optional_conda,
        install_optional_comfyui: p.install_optional_comfyui,
        execution_enabled: false,
        install_optional_git: tools.install_optional_git,
        install_optional_gh: tools.install_optional_gh,
        offer_gh_login: tools.offer_gh_login,
        consent_git: tools.consent_git,
        consent_gh: tools.consent_gh,
        consent_login: tools.consent_login,
    })
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            default_configuration,
            framework_license,
            inspect_source_path,
            preview_install_plan
        ])
        .run(tauri::generate_context!())
        .expect("failed to start Minglefield installer GUI");
}
