import { invoke } from "@tauri-apps/api/core";
import { previewArguments } from "./preview-arguments.js";
import { validateDestinationPassword } from "./database-password-policy.js";
import { effectiveReviewPaths, replaceVersionedPath } from "./review-settings.js";
import { assessLegacyAlphaSchema } from "./legacy-schema.js";
import { optionalSelection, optionalPlanArguments } from "./optional-components.js";
import { createAlphaUserReview, updateAlphaUserReview, alphaUserCorrections } from "./alpha-user-review.js";
import { createLegacyReview, stageLegacyText, legacyCorrections } from "./legacy-record-review.js";
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
    const databases = items.filter(item => item.kind === "sqlite_database");
    const selection = document.querySelector("#database-selection");
    selection.replaceChildren();
    selectedDatabase = null;
    lastDatabaseInspection = null;
    resetAlphaUserReview();
    for (const item of databases) {
      const label = document.createElement("label");
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "selected-database";
      radio.value = item.sourceDirectory + "/" + item.relativePath;
      radio.style.width = "auto";
      radio.addEventListener("change", () => {
        selectedDatabase = radio.value;
        lastDatabaseInspection = null;
        resetAlphaUserReview();
      });
      label.append(radio, document.createTextNode(" " + radio.value + " — " + item.status));
      selection.append(label);
    }
    output.textContent = items.length
      ? "Found " + databases.length + " database(s) and " + (items.length - databases.length) + " other data candidate(s). Select a database to inspect."
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
let inspectedAlphaJobs = null;
let originalLegacyRecords = null;
let editedLegacyRecords = null;
let reviewLoadIssues = [];
let reviewRequestSequence = 0;
function resetAlphaUserReview() {
  reviewRequestSequence += 1;
  originalAlphaUsers = null;
  editedAlphaUsers = null;
  inspectedAlphaJobs = null;
  originalLegacyRecords = null;
  editedLegacyRecords = null;
  reviewLoadIssues = [];
  for (const category of ["login", "hosts", "effects", "jobs", "games"]) {
    document.querySelector("#data-fields-" + category).textContent = "No verified records loaded for this category.";
  }
  document.querySelector("#data-editor-status").textContent =
    "No verified records loaded. Migration remains disabled.";
  updateReviewSummary();
}
function renderAlphaUsers() {
  const root = document.querySelector("#data-fields-login");
  root.replaceChildren();
  if (!editedAlphaUsers) {
    root.textContent = "Alpha user records unavailable for this database. See review warnings.";
    return;
  }
  for (const record of editedAlphaUsers) {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.style.width = "auto";
    checkbox.checked = record.disabled;
    checkbox.addEventListener("change", () => {
      editedAlphaUsers = updateAlphaUserReview(editedAlphaUsers, record.userId, checkbox.checked);
      updateReviewSummary();
    });
    label.append(checkbox, document.createTextNode(" Disabled — " + record.userId));
    root.append(label);
  }
  if (!editedAlphaUsers.length) root.textContent = "No Alpha user records in the selected database.";
}



function renderJobRecords() {
  const root = document.querySelector("#data-fields-jobs");
  root.replaceChildren();
  if (inspectedAlphaJobs) {
    const title = document.createElement("h4");
    title.textContent = "Alpha jobs (" + inspectedAlphaJobs.length + ")";
    root.append(title);
    for (const job of inspectedAlphaJobs) {
      const line = document.createElement("p");
      line.textContent = "Job " + job.jobId + " — User " + job.userId + " — Agent " + job.agentId;
      root.append(line);
    }
  }
  if (editedLegacyRecords) {
    const title = document.createElement("h4");
    title.textContent = "Host jobs (" + editedLegacyRecords.hostJobs.length + ")";
    root.append(title);
    for (const job of editedLegacyRecords.hostJobs) {
      const line = document.createElement("p");
      line.textContent = "Job " + job.jobId + " — Host " + job.hostId + " — Effect " +
        job.effectId + " — Requester " + job.requestedBy + " — State " + job.state;
      root.append(line);
    }
    if (editedLegacyRecords.unavailable.some(item => item.startsWith("sec01_host_jobs:"))) {
      const note = document.createElement("p");
      note.textContent = "Host jobs table is absent in this database.";
      root.append(note);
    }
  }
  if (!root.childNodes.length) root.textContent = "No verified job records loaded.";
}

function renderLegacyRecords() {
  if (!editedLegacyRecords) return;
  const data = editedLegacyRecords;
  const hosts = document.querySelector("#data-fields-hosts");
  const effects = document.querySelector("#data-fields-effects");
  const games = document.querySelector("#data-fields-games");
  for (const root of [hosts, effects, games]) root.replaceChildren();
  for (const host of data.hosts) {
    const line = document.createElement("p");
    line.textContent = "Host " + host.hostId + " — Owner " + host.ownerId + " (read-only)";
    hosts.append(line);
  }
  for (const effect of data.effects) {
    const label = document.createElement("label");
    label.textContent = "Host " + effect.hostId + " / Effect " + effect.effectId +
      " — Enabled " + String(effect.enabled) + " (read-only). Description:";
    const field = document.createElement("input");
    field.type = "text";
    field.maxLength = 256;
    field.value = effect.description;
    field.addEventListener("change", () => {
      try {
        editedLegacyRecords = stageLegacyText(editedLegacyRecords, "effects",
          JSON.stringify([effect.hostId, effect.effectId]), "description", field.value);
        updateReviewSummary();
      } catch (error) {
        field.value = editedLegacyRecords.effects.find(item =>
          item.hostId === effect.hostId && item.effectId === effect.effectId).description;
        document.querySelector("#data-editor-status").textContent = String(error);
      }
    });
    label.append(field);
    effects.append(label);
  }
  for (const game of data.games) {
    const label = document.createElement("label");
    label.textContent = "Project " + game.projectId + " — Host " + game.hostId +
      " — Owner " + game.ownerId + " (read-only). Name:";
    const field = document.createElement("input");
    field.type = "text";
    field.maxLength = 120;
    field.value = game.name;
    field.addEventListener("change", () => {
      try {
        editedLegacyRecords = stageLegacyText(editedLegacyRecords, "games", game.projectId,
          "name", field.value);
        field.value = editedLegacyRecords.games.find(item => item.projectId === game.projectId).name;
        updateReviewSummary();
      } catch (error) {
        field.value = editedLegacyRecords.games.find(item => item.projectId === game.projectId).name;
        document.querySelector("#data-editor-status").textContent = String(error);
      }
    });
    const path = document.createElement("small");
    path.textContent = "Repository: " + game.repositoryRoot + " (read-only)";
    label.append(field, path);
    games.append(label);
  }
  for (const [root, table, description] of [
    [hosts, "sec01_host_owners", "hosts"],
    [effects, "sec01_host_effect_definitions", "effects"],
    [games, "alpha_game_projects", "game projects"]
  ]) {
    if (data.unavailable.some(item => item.startsWith(table + ":"))) {
      root.textContent = "The " + table + " table is absent in this database.";
    } else if (!root.childNodes.length) {
      root.textContent = "No " + description + " records in this database.";
    }
  }
  renderJobRecords();
}

// Final review reports both original values and staged values; never writes the source.
function updateReviewSummary() {
  const summary = document.querySelector("#review-data-corrections");
  const status = document.querySelector("#data-editor-status");
  if (!originalAlphaUsers && !originalLegacyRecords) {
    summary.textContent = "No verified application records loaded for review. No changes staged.";
    return;
  }
  try {
    const alphaChanges = originalAlphaUsers && editedAlphaUsers
      ? alphaUserCorrections(originalAlphaUsers, editedAlphaUsers) : [];
    const legacyChanges = originalLegacyRecords && editedLegacyRecords
      ? legacyCorrections(originalLegacyRecords, editedLegacyRecords) : [];
    const changes = [
      ...alphaChanges.map(change => ({
        label: "User " + change.userId + " / Disabled",
        previous: originalAlphaUsers.find(item => item.userId === change.userId).disabled,
        next: change.disabled
      })),
      ...legacyChanges.map(change => ({
        label: (change.category === "effects" ? "Effect " : "Game ") +
          change.key + " / " + change.field,
        previous: change.previous,
        next: change.next
      }))
    ];
    summary.replaceChildren();
    const heading = document.createElement("p");
    heading.textContent = changes.length + " correction(s) staged in memory. No source data changed.";
    summary.append(heading);
    if (editedLegacyRecords) {
      const counts = document.createElement("p");
      counts.textContent = "Verified records: " + editedLegacyRecords.hosts.length + " hosts, " +
        editedLegacyRecords.effects.length + " effects, " +
        editedLegacyRecords.hostJobs.length + " host jobs, " +
        editedLegacyRecords.games.length + " games; " +
        (inspectedAlphaJobs?.length ?? 0) + " Alpha jobs; " +
        (editedAlphaUsers?.length ?? 0) + " Alpha users.";
      summary.append(counts);
    }
    for (const change of changes) {
      const line = document.createElement("p");
      line.textContent = change.label + ": " + String(change.previous) + " → " + String(change.next);
      summary.append(line);
    }
    for (const issue of [...(originalLegacyRecords?.unavailable ?? []), ...reviewLoadIssues]) {
      const line = document.createElement("p");
      line.textContent = "Not included: " + issue;
      summary.append(line);
    }
    const limitation = document.createElement("p");
    limitation.textContent = "Unchanged/read-only: host owners, agent/job identities, job states, effect activation, game paths, secrets and authentication sessions. No migration or installation is authorized.";
    summary.append(limitation);
    status.textContent = changes.length + " supported correction(s) staged in memory. " +
      reviewLoadIssues.length + " record reader warning(s). Migration remains disabled.";
  } catch (error) {
    summary.textContent = "Review validation failed: " + String(error);
    status.textContent = "Review validation failed: " + String(error);
  }
}

async function inspectSelectedSqlite() {
  const output = document.querySelector("#data-result");
  if (!selectedDatabase) {
    output.textContent = "Select a database first.";
    return;
  }
  const path = selectedDatabase;
  resetAlphaUserReview();
  const requestSequence = reviewRequestSequence;
  lastDatabaseInspection = null;
  output.textContent = "Inspecting a read-only SQLite snapshot…";
  try {
    const unlockPassword = existingDbPassword.value;
    const request = invoke("inspect_sqlite_database", { path, password: unlockPassword });
    existingDbPassword.value = "";
    const preview = await request;
    if (requestSequence !== reviewRequestSequence || selectedDatabase !== path) return;
    lastDatabaseInspection = preview;
    if (!preview.integrityOk || !preview.foreignKeysOk) {
      document.querySelector("#data-editor-status").textContent =
        "Database integrity verification failed. Editing is unavailable.";
      output.textContent = "Database integrity or foreign-key verification failed. Migration cannot proceed.";
      return;
    }
    const results = await Promise.allSettled([
      invoke("inspect_alpha_users", { path, password: unlockPassword }),
      invoke("inspect_alpha_jobs", { path, password: unlockPassword }),
      invoke("inspect_legacy_records", { path, password: unlockPassword })
    ]);
    if (requestSequence !== reviewRequestSequence || selectedDatabase !== path) return;
    try {
      if (results[0].status === "fulfilled") {
        originalAlphaUsers = createAlphaUserReview(results[0].value);
        editedAlphaUsers = createAlphaUserReview(results[0].value);
      } else {
        reviewLoadIssues.push("Alpha users: " + String(results[0].reason));
      }
    } catch (error) {
      reviewLoadIssues.push("Alpha users: " + String(error));
    }
    try {
      if (results[1].status === "fulfilled") {
        inspectedAlphaJobs = results[1].value;
      } else {
        reviewLoadIssues.push("Alpha jobs: " + String(results[1].reason));
      }
    } catch (error) {
      reviewLoadIssues.push("Alpha jobs: " + String(error));
    }
    try {
      if (results[2].status === "fulfilled") {
        originalLegacyRecords = createLegacyReview(results[2].value);
        editedLegacyRecords = createLegacyReview(results[2].value);
      } else {
        reviewLoadIssues.push("Hosts / Effects / Jobs / Games: " + String(results[2].reason));
      }
    } catch (error) {
      reviewLoadIssues.push("Hosts / Effects / Jobs / Games: " + String(error));
    }
    renderAlphaUsers();
    renderLegacyRecords();
    renderJobRecords();
    updateReviewSummary();
    output.textContent = "Database integrity verified. Read-only record review completed with " +
      reviewLoadIssues.length + " warning(s). Migration and installation remain disabled.";
  } catch (error) {
    if (requestSequence !== reviewRequestSequence || selectedDatabase !== path) return;
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
  updateReviewSummary();
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
