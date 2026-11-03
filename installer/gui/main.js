import { invoke } from "@tauri-apps/api/core";
const destination = document.querySelector("#destination");
const dataDirectory = document.querySelector("#data-directory");
const configText = document.querySelector("#config");
const result = document.querySelector("#result");
const pathsSection = document.querySelector("#paths");
const configSection = document.querySelector("#config-section");
let defaultConfig = null;

for (const radio of document.querySelectorAll('input[name="mode"]')) {
  radio.addEventListener("change", () => {
    const useConfig = document.querySelector('input[name="mode"]:checked').value === "config";
    pathsSection.hidden = useConfig;
    configSection.hidden = !useConfig;
  });
}

async function loadDefault() {
  try {
    defaultConfig = await invoke("default_configuration");
    destination.value = defaultConfig.installDir;
    dataDirectory.value = defaultConfig.dataDir;
    configText.value = [
      "version=" + defaultConfig.version,
      "install_dir=" + defaultConfig.installDir,
      "data_dir=" + defaultConfig.dataDir,
      "install_optional_conda=false",
      "install_optional_comfyui=false",
      "explicit_optional_consent=false"
    ].join("\n");
    result.textContent = "Ready to preview the installation plan.";
  } catch (error) {
    result.textContent = "Could not determine default configuration: " + String(error);
  }
}
document.querySelector("#preview").addEventListener("click", async () => {
  result.textContent = "Validating…";
  try {
    const useConfig = document.querySelector('input[name="mode"]:checked').value === "config";
    const plan = await invoke("preview_install_plan", {
      installDir: destination.value,
      dataDir: dataDirectory.value,
      configText: useConfig ? configText.value : null
    });
    result.textContent = JSON.stringify(plan, null, 2);
  } catch (error) {
    result.textContent = "Plan rejected: " + String(error);
  }
});
loadDefault();
