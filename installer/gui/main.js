import { invoke } from "@tauri-apps/api/core";
import { previewArguments } from "./preview-arguments.js";
import { validateDestinationPassword } from "./database-password-policy.js";
import { effectiveReviewPaths, replaceVersionedPath } from "./review-settings.js";
import { assessLegacyAlphaSchema } from "./legacy-schema.js";
import { optionalSelection, optionalPlanArguments } from "./optional-components.js";
import { createAlphaUserReview, updateAlphaUserReview, alphaUserCorrections } from "./alpha-user-review.js";
const destination = document.querySelector("#destination");
const dataDirectory = document.querySelector("#data-directory");
const configText = document.querySelector("#config");
const result = document.querySelector("#result");
const pathsSection = document.querySelector("#paths");
const configSection = document.querySelector("#config-section");
let defaultConfig = null;
// Only explicit corrections on the Standard review page override safe defaults.
// Advanced Custom Paths and Versioned Configuration keep their own state.
const standardOverrides = { installDir: null, dataDir: null };

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
const optionalIds = {
  install_optional_git: "optional-git", consent_git: "consent-git",
  install_optional_gh: "optional-gh", consent_gh: "consent-gh",
  offer_gh_login: "optional-gh-login", consent_login: "consent-gh-login",
  install_optional_conda: "optional-conda", install_optional_comfyui: "optional-comfyui",
  explicit_optional_consent: "consent-runtime"
};
function currentOptionalSelection() {
  return Object.fromEntries(Object.entries(optionalIds).map(([key, id]) =>
    [key, document.querySelector("#" + id).checked]));
}
function optionalValidation() {
  try {
    const options = optionalSelection(currentOptionalSelection());
    const setupMode = document.querySelector('input[name="setup-mode"]:checked').value;
    const advancedSource = document.querySelector('input[name="mode"]:checked').value;
    if (Object.values(options).some(Boolean) && setupMode === "advanced" && advancedSource === "config") {
      throw new Error("Edit optional choices in the versioned configuration or deselect them here.");
    }
    return { valid: true, message: Object.values(options).some(Boolean)
      ? "Optional selections validated for the installation plan."
      : "No optional components selected." };
  } catch (error) { return { valid: false, message: String(error) }; }
}
for (const id of Object.values(optionalIds)) {
  document.querySelector("#" + id).addEventListener("change", () => {
    document.querySelector("#optional-status").textContent = optionalValidation().message;
    updateWizardNavigation();
  });
}
for (const radio of document.querySelectorAll('input[name="setup-mode"], input[name="mode"]')) {
  radio.addEventListener("change", () => {
    document.querySelector("#optional-status").textContent = optionalValidation().message;
    updateWizardNavigation();
  });
}
document.querySelector("#preview").addEventListener("click", async () => {
  const passwordCheck = validateDestinationPassword(newDbPassword.value, confirmDbPassword.value);
  if (!passwordCheck.valid) {
    result.textContent = "Plan validation blocked: " + passwordCheck.message;
    return;
  }
  result.textContent = "Validating…";
  try {
    const args = previewArguments({
      setupMode: document.querySelector('input[name="setup-mode"]:checked').value,
      advancedSource: document.querySelector('input[name="mode"]:checked').value,
      defaults: defaultConfig,
      installDir: destination.value,
      dataDir: dataDirectory.value,
      configText: configText.value,
      standardOverrides
    });
    const finalArgs = optionalPlanArguments(args, currentOptionalSelection(),
      document.querySelector('input[name="setup-mode"]:checked').value,
      document.querySelector('input[name="mode"]:checked').value);
    const plan = await invoke("preview_install_plan", {
      ...finalArgs,
      newDbPassword: newDbPassword.value,
      confirmDbPassword: confirmDbPassword.value
    });
    result.textContent = JSON.stringify({
      ...plan,
      database: {
        operation: selectedDatabase ? "legacy_sqlite_to_sqlcipher" : "create_sqlcipher",
        source: selectedDatabase,
        sourceInspected: Boolean(lastDatabaseInspection),
        schemaAssessment: lastDatabaseInspection ? assessLegacyAlphaSchema(lastDatabaseInspection) : null,
        destinationEncryptionRequired: true,
        stagedAlphaUserCorrections: originalAlphaUsers && editedAlphaUsers
          ? alphaUserCorrections(originalAlphaUsers, editedAlphaUsers) : [],
        migrationEnabled: false,
        executionEnabled: false
      }
    }, null, 2);
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
      ? "Found " + items.length + " known data candidate(s). Select and inspect the database to continue."
      : "No known data candidates found at the checked locations. This does not prove the directory contains no Minglefield data.";
  } catch (error) { output.textContent = "Data inspection failed: " + String(error); }
});
const existingDbPassword = document.querySelector("#existing-db-password");
const newDbPassword = document.querySelector("#new-db-password");
const confirmDbPassword = document.querySelector("#confirm-db-password");
const passwordStatus = document.querySelector("#new-db-password-status");

function updateNewDatabasePasswordStatus() {
  const check = validateDestinationPassword(newDbPassword.value, confirmDbPassword.value);
  passwordStatus.textContent = check.message + " Database migration and installation execution are not yet enabled.";
  if (typeof wizardIndex !== "undefined" && wizardIndex === 3) updateWizardNavigation();
}

newDbPassword.addEventListener("input", updateNewDatabasePasswordStatus);
confirmDbPassword.addEventListener("input", updateNewDatabasePasswordStatus);
window.addEventListener("pagehide", () => {
  existingDbPassword.value = "";
  newDbPassword.value = "";
  confirmDbPassword.value = "";
});
for (const [buttonId, fieldId] of [
  ["browse-destination", "destination"],
  ["browse-data-directory", "data-directory"],
  ["browse-source-path", "source-path"]
]) {
  document.querySelector("#" + buttonId).addEventListener("click", async () => {
    try {
      const path = await invoke("browse_directory");
      if (path) document.querySelector("#" + fieldId).value = path;
    } catch (error) {
      document.querySelector("#data-result").textContent = "Directory picker failed: " + String(error);
    }
  });
}
document.querySelector("#browse-database").addEventListener("click", async () => {
  try {
    const path = await invoke("browse_sqlite_file");
    if (path) {
      selectedDatabase = path;
      lastDatabaseInspection = null;
      resetAlphaUserReview();
      document.querySelector("#data-result").textContent =
        "Selected database: " + path + ". Use inspection to validate it; migration remains disabled.";
    }
  } catch (error) {
    document.querySelector("#data-result").textContent = "Database picker failed: " + String(error);
  }
});
let selectedDatabase = null;
let lastDatabaseInspection = null;
let originalAlphaUsers = null;
let editedAlphaUsers = null;
function resetAlphaUserReview() {
  originalAlphaUsers = null;
  editedAlphaUsers = null;
  document.querySelector("#data-fields-login").replaceChildren();
}
function renderAlphaUsers() {
  const root = document.querySelector("#data-fields-login");
  root.replaceChildren();
  if (!editedAlphaUsers) return;
  for (const record of editedAlphaUsers) {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.style.width = "auto";
    checkbox.checked = record.disabled;
    checkbox.addEventListener("change", () => {
      editedAlphaUsers = updateAlphaUserReview(editedAlphaUsers, record.userId, checkbox.checked);
      document.querySelector("#data-editor-status").textContent =
        alphaUserCorrections(originalAlphaUsers, editedAlphaUsers).length +
        " Alpha user setting(s) changed. Changes are staged in memory only; migration execution is not yet available.";
    });
    label.append(checkbox, document.createTextNode(" Disabled — " + record.userId));
    root.append(label);
  }
  if (!editedAlphaUsers.length) root.textContent = "No Alpha user records in the selected database.";
}


async function inspectSelectedSqlite() {
  const output = document.querySelector("#data-result");
  if (!selectedDatabase) {
    output.textContent = "Select a database first.";
    return;
  }
  output.textContent = "Inspecting a read-only SQLite snapshot…";
  try {
    const unlockPassword = existingDbPassword.value;
    const request = invoke("inspect_sqlite_database", { path: selectedDatabase, password: unlockPassword });
    existingDbPassword.value = "";
    const preview = await request;
    lastDatabaseInspection = preview;
    resetAlphaUserReview();
    try {
      const users = await invoke("inspect_alpha_users", { path: selectedDatabase, password: unlockPassword });
      originalAlphaUsers = createAlphaUserReview(users);
      editedAlphaUsers = createAlphaUserReview(users);
      renderAlphaUsers();
    } catch (reviewError) {
      document.querySelector("#data-editor-status").textContent =
        "Application data could not be loaded for editing: " + String(reviewError);
    }
    output.textContent = preview.integrityOk && preview.foreignKeysOk
      ? "Database integrity verified. Continue after confirming the new encrypted database password. Application data mapping and migration execution are still pending."
      : "Database integrity or foreign-key verification failed. Migration cannot proceed.";
  } catch (error) {
    output.textContent = "Database inspection could not be completed. Check the selected file and existing database unlock password. " + String(error);
  }
}

document.querySelector("#inspect-selected-database").addEventListener("click", inspectSelectedSqlite);

async function inspectDefaultUserData() {
  const output = document.querySelector("#data-result");
  const selection = document.querySelector("#database-selection");
  output.textContent = "Inspecting per-user Minglefield application data…";
  selection.replaceChildren();
  selectedDatabase = null;
  lastDatabaseInspection = null;
  resetAlphaUserReview();
  try {
    const items = await invoke("inspect_default_user_data");
    const databases = items.filter((item) => item.kind === "sqlite_database");
    output.textContent = items.length
      ? "Found " + databases.length + " database candidate(s) and " + (items.length - databases.length) + " other data candidate(s). Select a database to inspect."
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
        radio.addEventListener("change", () => { selectedDatabase = radio.value; lastDatabaseInspection = null; resetAlphaUserReview(); });
        label.append(radio, document.createTextNode(" " + item.sourceDirectory + "/" + item.relativePath + " — " + item.status));
        selection.append(label);
      }

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
const wizardNames = ["Welcome", "Configuration", "Optional installations", "Source inspection", "Data review", "Review"];
function activeConfiguration() {
  return {
    setupMode: document.querySelector('input[name="setup-mode"]:checked').value,
    advancedSource: document.querySelector('input[name="mode"]:checked').value,
    defaults: defaultConfig,
    installDir: destination.value,
    dataDir: dataDirectory.value,
    configText: configText.value,
    standardOverrides
  };
}
function refreshReview() {
  const issue = document.querySelector("#review-paths-status");
  try {
    const paths = effectiveReviewPaths(activeConfiguration());
    document.querySelector("#review-install-dir").value = paths.installDir;
    document.querySelector("#review-data-dir").value = paths.dataDir;
    issue.textContent = "These are the effective paths for the selected setup mode. Corrections are applied to the actual installation plan.";
  } catch (error) {
    issue.textContent = "Configuration cannot be reviewed: " + String(error);
  }
  document.querySelector("#review-source-dir").value = document.querySelector("#source-path").value;
  document.querySelector("#review-database-path").value = selectedDatabase || "";
  document.querySelector("#review-database-summary").textContent = lastDatabaseInspection
    ? JSON.stringify({
        status: lastDatabaseInspection.status,
        integrityOk: lastDatabaseInspection.integrityOk,
        foreignKeysOk: lastDatabaseInspection.foreignKeysOk,
        applicationId: lastDatabaseInspection.applicationId,
        userVersion: lastDatabaseInspection.userVersion,
        tableCount: lastDatabaseInspection.tables.length,
        schemaAssessment: assessLegacyAlphaSchema(lastDatabaseInspection)
      }, null, 2)
    : "No database inspected. Fresh installation still requires encrypted SQLCipher.";
  document.querySelector("#review-security-summary").textContent =
    "SQLCipher is mandatory for fresh installs and legacy imports. Destination password: " +
    validateDestinationPassword(newDbPassword.value, confirmDbPassword.value).message +
    " Execution is not enabled yet. No passwords are displayed.";
}
for (const [reviewId, sourceId, configKey, overrideKey] of [
  ["review-install-dir", "destination", "install_dir", "installDir"],
  ["review-data-dir", "data-directory", "data_dir", "dataDir"]
]) {
  document.querySelector("#" + reviewId).addEventListener("change", () => {
    const value = document.querySelector("#" + reviewId).value;
    const mode = activeConfiguration();
    try {
      if (!value.trim()) throw new Error("A directory cannot be empty.");
      if (mode.setupMode === "standard") {
        standardOverrides[overrideKey] = value;
      } else if (mode.advancedSource === "defaults") {
        document.querySelector("#" + sourceId).value = value;
      } else {
        configText.value = replaceVersionedPath(configText.value, configKey, value);
      }
      refreshReview();
    } catch (error) {
      document.querySelector("#review-paths-status").textContent = "Correction rejected: " + String(error);
    }
  });
}
document.querySelector("#review-source-dir").addEventListener("input", () => {
  document.querySelector("#source-path").value = document.querySelector("#review-source-dir").value;
});

for (const tab of ["paths", "database", "security"]) {
  document.querySelector("#review-tab-" + tab).addEventListener("click", () => {
    for (const name of ["paths", "database", "security"]) {
      document.querySelector("#review-" + name).hidden = name !== tab;
    }
    refreshReview();
  });
}
// Application records must be loaded from the verified backend before editing.
// Never fabricate fields or write credentials into an unverified destination.
for (const tab of ["login", "hosts", "effects", "jobs", "games"]) {
  document.querySelector("#data-tab-" + tab).addEventListener("click", () => {
    for (const category of ["login", "hosts", "effects", "jobs", "games"]) {
      document.querySelector("#data-editor-" + category).hidden = category !== tab;
    }
  });
}
function refreshFinalConfiguration() {
  refreshReview();
}
let wizardIndex = 0;
function updateWizardNavigation() {
  const passwordCheck = validateDestinationPassword(newDbPassword.value, confirmDbPassword.value);
  const next = document.querySelector("#wizard-next");
  next.disabled = wizardIndex === wizardPages.length - 1 ||
    (wizardIndex === 2 && !optionalValidation().valid) ||
    (wizardIndex === 3 && !passwordCheck.valid);
  next.title = wizardIndex === 2 && !optionalValidation().valid ? optionalValidation().message :
    wizardIndex === 3 && !passwordCheck.valid ? passwordCheck.message : "";
}
function showWizardPage(index) {
  if (!Number.isInteger(index) || index < 0 || index >= wizardPages.length) return;
  wizardIndex = index;
  if (wizardPages[index].dataset.wizardPage === "data-review") {
    document.querySelector("#data-editor-status").textContent = editedAlphaUsers
      ? "Loaded " + editedAlphaUsers.length + " Alpha user record(s). " +
        alphaUserCorrections(originalAlphaUsers, editedAlphaUsers).length +
        " change(s) staged; encrypted migration execution is not yet available."
      : selectedDatabase
        ? "Inspect the selected database on page 4 to load editable application values. Migration remains blocked."
        : "Fresh installation: application defaults and encrypted database creation are not yet implemented.";
  }
  if (wizardPages[index].dataset.wizardPage === "review") refreshFinalConfiguration();
  wizardPages.forEach((page, position) => { page.hidden = position !== index; });
  document.querySelector("#wizard-back").disabled = index === 0;
  updateWizardNavigation();
  document.querySelector("#wizard-progress").textContent =
    `Step ${index + 1} of ${wizardPages.length} — ${wizardNames[index]}`;
  document.querySelector("#wizard-step-label").textContent = wizardNames[index];
}
document.querySelector("#wizard-back").addEventListener("click", () => showWizardPage(wizardIndex - 1));
document.querySelector("#wizard-next").addEventListener("click", () => {
  if (wizardIndex === 2 && !optionalValidation().valid) return;
  if (wizardIndex === 3) {
    const check = validateDestinationPassword(newDbPassword.value, confirmDbPassword.value);
    if (!check.valid) { passwordStatus.textContent = check.message; return; }
  }
  showWizardPage(wizardIndex + 1);
});
showWizardPage(0);
