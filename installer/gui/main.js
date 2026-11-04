import { invoke } from "@tauri-apps/api/core";
import { previewArguments } from "./preview-arguments.js";
const destination = document.querySelector("#destination");
const dataDirectory = document.querySelector("#data-directory");
const configText = document.querySelector("#config");
const result = document.querySelector("#result");
const pathsSection = document.querySelector("#paths");
const configSection = document.querySelector("#config-section");
let defaultConfig = null;

async function loadFrameworkLicense() {
  const licenseText = document.querySelector("#license-text");
  try {
    const license = await invoke("framework_license");
    if (license.identifier !== "GPL-3.0-or-later" || !license.text.startsWith("GNU GENERAL PUBLIC LICENSE")) {
      throw new Error("Unexpected framework license response");
    }
    licenseText.textContent = license.text;
  } catch (error) {
    licenseText.textContent = "Unable to load the bundled framework license: " + String(error);
  }
}


async function loadApplicationReadme() {
  const output = document.querySelector("#readme-text");
  try {
    const readme = await invoke("application_readme");
    if (typeof readme.text !== "string" || !readme.text.startsWith("# Minglefield")) {
      throw new Error("Unexpected bundled README");
    }
    output.textContent = readme.text;
  } catch (error) {
    output.textContent = "Unable to load bundled README: " + String(error);
  }
}

for (const radio of document.querySelectorAll('input[name="mode"], input[name="setup-mode"]')) {
  radio.addEventListener("change", () => {
    const advanced = document.querySelector('input[name="setup-mode"]:checked').value === "advanced";
    const useConfig = document.querySelector('input[name="mode"]:checked').value === "config";
    document.querySelector("#advanced-options").hidden = !advanced;
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
    const args = previewArguments({
      setupMode: document.querySelector('input[name="setup-mode"]:checked').value,
      advancedSource: document.querySelector('input[name="mode"]:checked').value,
      defaults: defaultConfig,
      installDir: destination.value,
      dataDir: dataDirectory.value,
      configText: configText.value
    });
    const plan = await invoke("preview_install_plan", args);
    result.textContent = JSON.stringify(plan, null, 2);
  } catch (error) {
    result.textContent = "Plan rejected: " + String(error);
  }
});
document.querySelector("#inspect-source").addEventListener("click", async () => {
  const output = document.querySelector("#source-result");
  const path = document.querySelector("#source-path").value.trim();
  if (!path) {
    output.textContent = "Select a source directory first.";
    return;
  }
  output.textContent = "Inspecting selected directory…";
  try {
    const inspection = await invoke("inspect_source_path", { path });
    output.textContent = JSON.stringify(inspection, null, 2);
  } catch (error) {
    output.textContent = "Inspection failed: " + String(error);
  }
});
document.querySelector("#inspect-data").addEventListener("click", async () => {
  const output = document.querySelector("#data-result");
  const path = document.querySelector("#source-path").value.trim();
  if (!path) { output.textContent = "Select a directory first."; return; }
  output.textContent = "Inspecting known user-data locations…";
  try {
    const items = await invoke("inspect_existing_data", { path });
    output.textContent = items.length
      ? JSON.stringify(items, null, 2)
      : "No known data candidates found at the checked locations. This does not prove the directory contains no Minglefield data.";
  } catch (error) { output.textContent = "Data inspection failed: " + String(error); }
});
const existingDbPassword = document.querySelector("#existing-db-password");
const newDbPassword = document.querySelector("#new-db-password");
const confirmDbPassword = document.querySelector("#confirm-db-password");
const passwordStatus = document.querySelector("#new-db-password-status");

function updateNewDatabasePasswordStatus() {
  const password = newDbPassword.value;
  const missing = [];
  if ([...password].length < 8) missing.push("at least 8 characters");
  if (!/\p{Lu}/u.test(password)) missing.push("an uppercase letter");
  if (!/[0-9]/.test(password)) missing.push("a digit");
  if (![...password].some((c) => !/[\p{L}\p{N}\s]/u.test(c))) missing.push("a special character");
  if (missing.length) {
    passwordStatus.textContent = "New password requires " + missing.join(", ") + ". Migration remains disabled.";
  } else if (password !== confirmDbPassword.value) {
    passwordStatus.textContent = "New password meets the policy; confirmation does not match. Migration remains disabled.";
  } else {
    passwordStatus.textContent = "New password meets the policy and confirmation matches. Migration remains disabled until encryption is implemented.";
  }
}
newDbPassword.addEventListener("input", updateNewDatabasePasswordStatus);
confirmDbPassword.addEventListener("input", updateNewDatabasePasswordStatus);
window.addEventListener("pagehide", () => {
  existingDbPassword.value = "";
  newDbPassword.value = "";
  confirmDbPassword.value = "";
});
let selectedDatabase = null;

async function inspectSelectedSqlite() {
  const output = document.querySelector("#data-result");
  if (!selectedDatabase) {
    output.textContent = "Select a database first.";
    return;
  }
  output.textContent = "Inspecting a read-only SQLite snapshot…";
  try {
    const request = invoke("inspect_sqlite_database", { path: selectedDatabase, password: existingDbPassword.value });
    existingDbPassword.value = "";
    const preview = await request;
    output.textContent = JSON.stringify(preview, null, 2);
  } catch (error) {
    output.textContent = "SQLite inspection failed: " + String(error);
  }
}

async function inspectDefaultUserData() {
  const output = document.querySelector("#data-result");
  const selection = document.querySelector("#database-selection");
  output.textContent = "Inspecting per-user Minglefield application data…";
  selection.replaceChildren();
  selectedDatabase = null;
  try {
    const items = await invoke("inspect_default_user_data");
    const databases = items.filter((item) => item.kind === "sqlite_database");
    output.textContent = items.length
      ? JSON.stringify(items, null, 2)
      : "No database or known configuration found in the default application data directory.";
    if (databases.length) {
      const heading = document.createElement("p");
      heading.textContent = "Database for future migration (selection only; nothing is imported):";
      selection.append(heading);
      for (const item of databases) {
        const label = document.createElement("label");
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "selected-database";
        radio.value = item.sourceDirectory + "/" + item.relativePath;
        radio.style.width = "auto";
        radio.addEventListener("change", () => { selectedDatabase = radio.value; });
        label.append(radio, document.createTextNode(" " + item.sourceDirectory + "/" + item.relativePath + " — " + item.status));
        selection.append(label);
      }
      const inspectButton = document.createElement("button");
      inspectButton.type = "button";
      inspectButton.textContent = "Inspect selected SQLite database (read-only)";
      inspectButton.addEventListener("click", inspectSelectedSqlite);
      selection.append(inspectButton);
    }
  } catch (error) {
    output.textContent = "Application data inspection failed: " + String(error);
  }
}
document.querySelector("#inspect-default-data").addEventListener("click", inspectDefaultUserData);
inspectDefaultUserData();
loadDefault();
loadFrameworkLicense();
loadApplicationReadme();

// Wizard navigation preserves the existing form controls and their values.
// No page transition authorizes a download, filesystem write, or installation.
const wizardPages = [...document.querySelectorAll("[data-wizard-page]")];
const wizardNames = ["Welcome", "Configuration", "Source inspection", "Review"];
let wizardIndex = 0;
function showWizardPage(index) {
  if (!Number.isInteger(index) || index < 0 || index >= wizardPages.length) return;
  wizardIndex = index;
  wizardPages.forEach((page, position) => { page.hidden = position !== index; });
  document.querySelector("#wizard-back").disabled = index === 0;
  document.querySelector("#wizard-next").disabled = index === wizardPages.length - 1;
  document.querySelector("#wizard-progress").textContent =
    `Step ${index + 1} of ${wizardPages.length} — ${wizardNames[index]}`;
  document.querySelector("#wizard-step-label").textContent = wizardNames[index];
}
document.querySelector("#wizard-back").addEventListener("click", () => showWizardPage(wizardIndex - 1));
document.querySelector("#wizard-next").addEventListener("click", () => showWizardPage(wizardIndex + 1));
showWizardPage(0);
