import { invoke } from "@tauri-apps/api/core";
const destination = document.querySelector("#destination");
const result = document.querySelector("#result");
async function loadDefault() {
  try {
    destination.value = await invoke("default_destination");
    result.textContent = "Ready to preview the installation plan.";
  } catch (error) {
    result.textContent = "Could not determine default destination: " + String(error);
  }
}
document.querySelector("#preview").addEventListener("click", async () => {
  result.textContent = "Validating…";
  try {
    const plan = await invoke("preview_install_plan", { installDir: destination.value });
    result.textContent = JSON.stringify(plan, null, 2);
  } catch (error) {
    result.textContent = "Plan rejected: " + String(error);
  }
});
loadDefault();
