use minglefield_installer_core::config::InstallerConfig;
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
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct DefaultConfig {
    version: u32,
    install_dir: String,
    data_dir: String,
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
    let c = if let Some(text) = config_text {
        // An explicitly supplied config is validated without silent overrides.
        InstallerConfig::parse(&text).map_err(str::to_string)?
    } else {
        let mut c = InstallerConfig::defaults().map_err(|err| format!("{err:?}"))?;
        c.install_dir = install_dir;
        c.data_dir = data_dir;
        c
    };
    let p = c.preview(Mode::Gui).map_err(|err| format!("{err:?}"))?;
    Ok(PlanPreview {
        version: c.version,
        install_dir: p.install_dir,
        data_dir: c.data_dir,
        provision_host: p.provision_host,
        install_optional_conda: p.install_optional_conda,
        install_optional_comfyui: p.install_optional_comfyui,
        execution_enabled: false,
    })
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            default_configuration,
            preview_install_plan
        ])
        .run(tauri::generate_context!())
        .expect("failed to start Minglefield installer GUI");
}
