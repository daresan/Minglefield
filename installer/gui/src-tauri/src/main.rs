use minglefield_installer_core::{plan, InstallRequest, Mode};
use serde::Serialize;
use std::env;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct PlanPreview {
    install_dir: String,
    provision_host: bool,
    install_optional_conda: bool,
    install_optional_comfyui: bool,
    execution_enabled: bool,
}

#[tauri::command]
fn default_destination() -> Result<String, String> {
    let destination = if cfg!(windows) {
        env::var("LOCALAPPDATA")
            .map(|v| format!("{v}\\Programs\\Minglefield"))
            .map_err(|_| "LOCALAPPDATA is not set")?
    } else if cfg!(target_os = "macos") {
        env::var("HOME")
            .map(|v| format!("{v}/Applications/Minglefield"))
            .map_err(|_| "HOME is not set")?
    } else {
        env::var("HOME")
            .map(|v| format!("{v}/.local/opt/Minglefield"))
            .map_err(|_| "HOME is not set")?
    };
    Ok(destination)
}

#[tauri::command]
fn preview_install_plan(install_dir: String) -> Result<PlanPreview, String> {
    let request = InstallRequest {
        mode: Mode::Gui,
        install_dir,
        install_optional_conda: false,
        install_optional_comfyui: false,
        explicit_optional_consent: false,
    };
    let p = plan(&request).map_err(|err| format!("{err:?}"))?;
    Ok(PlanPreview {
        install_dir: p.install_dir,
        provision_host: p.provision_host,
        install_optional_conda: p.install_optional_conda,
        install_optional_comfyui: p.install_optional_comfyui,
        execution_enabled: false,
    })
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            default_destination,
            preview_install_plan
        ])
        .run(tauri::generate_context!())
        .expect("failed to start Minglefield installer GUI");
}
