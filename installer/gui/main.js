import { invoke } from "@tauri-apps/api/core";
import { previewArguments } from "./preview-arguments.js";
import { validateDestinationPassword } from "./database-password-policy.js";
import { effectiveReviewPaths, replaceVersionedPath } from "./review-settings.js";
import { databaseReviewEvidence } from "./database-review-evidence.js";
import { optionalSelection, optionalPlanArguments } from "./optional-components.js";
import { assessFieldCoverage } from "./schema-coverage.js";
import { createFullReview, stageFullCell, fullRowCorrections, fullReviewSummary } from "./full-database-review.js";
import { renderDomainDatabaseReview } from "./domain-database-review.js";
import { groupReviewedTables } from "./database-review-categories.js";
import { assessTemporaryDiskCopy, selectTemporaryCopyCredentials } from "./temporary-encrypted-review.js";
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
        ...databaseReviewEvidence(lastDatabaseInspection),
        destinationEncryptionRequired: true,
        // The five domain tabs now share the same full-row editor. Legacy
        // correction arrays remain in the plan shape for older consumers.
        stagedAlphaUserCorrections: [],
        stagedEffectAndGameCorrections: [],
        stagedFullDatabaseChanges: originalFullDb && editedFullDb
          ? fullReviewSummary(stagedFullDatabaseCorrections()) : [],
        verifiedMigrationRehearsal: lastMigrationRehearsal ? {
          status: lastMigrationRehearsal.status,
          verifiedChanges: lastMigrationRehearsal.verifiedChanges,
          preservedTableCount: lastMigrationRehearsal.preservedTables.length,
          inventoriedColumnCount: lastMigrationRehearsal.fieldCoverage.reduce(
            (sum, entry) => sum + entry.columns.length, 0
          ),
          protectedColumnCount: lastMigrationRehearsal.fieldCoverage.reduce(
            (sum, entry) => sum + entry.protectedColumns.length, 0
          ),
          schemaObjectCount: lastMigrationRehearsal.schemaObjectCount,
          fullDataCopyVerified: lastMigrationRehearsal.fullDataCopyVerified,
          verifiedRowCount: lastMigrationRehearsal.verifiedRowCount,
          verifiedTableCount: lastMigrationRehearsal.verifiedTableCount,
          verifiedSchemaEntryCount: lastMigrationRehearsal.verifiedSchemaEntryCount,
          encryptedDestinationVerified: false,
          proposedDestination: lastMigrationRehearsal.destinationPath,
          sourcePreserved: lastMigrationRehearsal.sourcePreserved,
          destinationCreated: false,
          executionEnabled: false
        } : null,
        verifiedTemporaryEncryptedCopy: lastTemporaryEncryptedProof ? {
          status: lastTemporaryEncryptedProof.status,
          temporaryEncryptedCopyVerified: lastTemporaryEncryptedProof.temporaryEncryptedCopyVerified,
          verifiedStagedChanges: lastTemporaryEncryptedProof.verifiedStagedChanges,
          stagedValuesMatchCiphertext: lastTemporaryEncryptedProof.stagedValuesMatchCiphertext,
          ciphertextHeaderVerified: lastTemporaryEncryptedProof.ciphertextHeaderVerified,
          wrongKeyRejected: lastTemporaryEncryptedProof.wrongKeyRejected,
          checkedRows: lastTemporaryEncryptedProof.checkedRows,
          checkedTables: lastTemporaryEncryptedProof.checkedTables,
          temporaryFilesRemoved: lastTemporaryEncryptedProof.temporaryFilesRemoved,
          encryptedDestinationVerified: false,
          destinationCreated: false,
          executionEnabled: false
        } : null,
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
    resetDatabaseReview();
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
        resetDatabaseReview();
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
existingDbPassword.addEventListener("input", () => resetDatabaseReview());
window.addEventListener("pagehide", () => {
  retainedSourceUnlockPassword = "";
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
      resetDatabaseReview();
      document.querySelector("#data-result").textContent =
        "Selected database: " + path + ". Use inspection to validate it; migration remains disabled.";
    }
  } catch (error) {
    document.querySelector("#data-result").textContent = "Database picker failed: " + String(error);
  }
});
let selectedDatabase = null;
let lastDatabaseInspection = null;
let retainedSourceUnlockPassword = "";
let originalFullDb = null;
let editedFullDb = null;
let reviewRequestSequence = 0;
let lastMigrationRehearsal = null;
let rehearsalRequestSequence = 0;
let lastTemporaryEncryptedProof = null;
let temporaryEncryptedRequestSequence = 0;
function invalidateMigrationRehearsal() {
  rehearsalRequestSequence += 1;
  temporaryEncryptedRequestSequence += 1;
  lastTemporaryEncryptedProof = null;
  document.querySelector("#temporary-sqlcipher-result").textContent =
    "Encrypted disk-copy verification must be repeated after review or destination changes.";
  lastMigrationRehearsal = null;
  document.querySelector("#migration-field-coverage").replaceChildren();
  document.querySelector("#migration-rehearsal-result").textContent =
    "Migration rehearsal requires a new verification after data or destination changes.";
  document.querySelector("#review-migration-rehearsal-status").textContent =
    "No current verified migration rehearsal. Execution remains disabled.";
}
function resetDatabaseReview() {
  reviewRequestSequence += 1;
  retainedSourceUnlockPassword = "";
  invalidateMigrationRehearsal();
  originalFullDb = null;
  editedFullDb = null;
  renderDomainDatabaseReview(document, () => editedFullDb, editDatabaseCell, reviewError);
  document.querySelector("#data-editor-status").textContent =
    "No verified database records loaded. Migration remains disabled.";
  updateReviewSummary();
}

function reviewError(error) {
  document.querySelector("#data-editor-status").textContent = String(error);
}

function editDatabaseCell(table, rowIndex, field, kind, value) {
  editedFullDb = stageFullCell(editedFullDb, table, rowIndex, field, kind, value);
  invalidateMigrationRehearsal();
  updateReviewSummary();
}

function stagedFullDatabaseCorrections() {
  if (!originalFullDb || !editedFullDb) {
    throw new Error("Full database values were not loaded for migration review.");
  }
  return fullRowCorrections(originalFullDb, editedFullDb);
}

function allStagedMigrationChanges() {
  return stagedFullDatabaseCorrections();
}

function renderGroupedDatabase() {
  renderDomainDatabaseReview(document, () => editedFullDb, editDatabaseCell, reviewError);
}

// The summary intentionally contains only table names, rowids and changed
// column names, never password hashes, tokens or raw workflow JSON.
function updateReviewSummary() {
  const summary = document.querySelector("#review-data-corrections");
  const status = document.querySelector("#data-editor-status");
  if (!originalFullDb || !editedFullDb) {
    summary.textContent = "No verified application records loaded for review. No changes staged.";
    return;
  }
  try {
    const changed = fullReviewSummary(stagedFullDatabaseCorrections());
    const grouped = groupReviewedTables(editedFullDb);
    summary.replaceChildren();
    const heading = document.createElement("p");
    heading.textContent = changed.length +
      " row correction(s) staged across " + editedFullDb.tables.length +
      " verified source table(s). No source data changed.";
    summary.append(heading);
    const count = document.createElement("p");
    count.textContent = [
      "Anmeldung", "Hosts", "Effekte", "Jobs", "Games", "Sonstige"
    ].map((name, i) =>
      name + ": " + grouped[["login","hosts","effects","jobs","games","all"][i]].length
      + " Tabelle(n)").join(" · ");
    summary.append(count);
    for (const entry of changed) {
      const line = document.createElement("p");
      line.textContent = entry.table + " / rowid " + (entry.rowId ?? "(none)") +
        ": " + entry.changedColumns.join(", ");
      summary.append(line);
    }
    const note = document.createElement("p");
    note.textContent = "Every stored value may be staged. SQLite constraints, " +
      "foreign keys and full-copy verification still apply; no database " +
      "migration or installation execution is enabled.";
    summary.append(note);
    status.textContent = changed.length + " staged row change(s); " +
      editedFullDb.tables.length + " verified source table(s).";
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
  resetDatabaseReview();
  const requestSequence = reviewRequestSequence;
  lastDatabaseInspection = null;
  output.textContent = "Inspecting a read-only SQLite snapshot and all stored tables…";
  try {
    const unlockPassword = existingDbPassword.value;
    const request = invoke("inspect_sqlite_database", {path, password: unlockPassword});
    existingDbPassword.value = "";
    const preview = await request;
    if (requestSequence !== reviewRequestSequence || selectedDatabase !== path) return;
    if (!preview.integrityOk || !preview.foreignKeysOk) {
      throw new Error("Database integrity or foreign-key verification failed.");
    }
    const records = createFullReview(await invoke("inspect_full_database", {
      path, password: unlockPassword
    }));
    if (requestSequence !== reviewRequestSequence || selectedDatabase !== path) return;
    const schemaTables = new Map(preview.tables.map(t => [t.name, t.columns]));
    if (schemaTables.size !== preview.tables.length ||
        records.tables.length !== schemaTables.size ||
        records.tables.some(t => JSON.stringify(t.columns) !==
          JSON.stringify(schemaTables.get(t.name)))) {
      throw new Error("The typed table inventory differs from the verified source schema.");
    }
    originalFullDb = records;
    editedFullDb = createFullReview(records);
    lastDatabaseInspection = preview;
    retainedSourceUnlockPassword = unlockPassword;
    renderGroupedDatabase();
    updateReviewSummary();
    const objectAudit = databaseReviewEvidence(preview).schemaObjectAssessment;
    const objectCounts = Number.isSafeInteger(objectAudit.matchedSchemaEntryCount) &&
      Number.isSafeInteger(objectAudit.expectedSchemaEntryCount)
      ? " (" + objectAudit.matchedSchemaEntryCount + "/" +
        objectAudit.expectedSchemaEntryCount + " entries)"
      : "";
    output.textContent = "Database integrity verified. " +
      records.tables.length + " complete SQLite table(s) loaded in the five review areas." +
      " SQLite schema-object audit: " + objectAudit.reason + objectCounts + "." +
      " Unrecognized extensions are listed separately. Migration remains disabled.";
  } catch (error) {
    if (requestSequence !== reviewRequestSequence || selectedDatabase !== path) return;
    retainedSourceUnlockPassword = "";
    lastDatabaseInspection = null;
    originalFullDb = null;
    editedFullDb = null;
    renderGroupedDatabase();
    updateReviewSummary();
    output.textContent = "Database inspection rejected: " + String(error);
  }
}

function renderFieldCoverage(summary) {
  const root = document.querySelector("#migration-field-coverage");
  root.replaceChildren();
  const heading = document.createElement("p");
  heading.textContent = "Verified schema inventory: " + summary.tables +
    " tables, " + summary.columns + " columns; " + summary.editableColumns +
    " staged-editable and " + summary.protectedColumns +
    " protected. No record values are included.";
  root.append(heading);
  for (const entry of summary.entries) {
    const details = document.createElement("details");
    const label = document.createElement("summary");
    label.textContent = entry.table + " — " + entry.rows + " rows — " +
      entry.editable.length + " editable / " + entry.protected.length +
      " protected columns";
    details.append(label);
    const editable = document.createElement("p");
    editable.textContent = "Staged-editable: " +
      (entry.editable.length ? entry.editable.join(", ") : "(none)");
    const protectedFields = document.createElement("p");
    protectedFields.textContent = "Protected (not editable): " +
      (entry.protected.length ? entry.protected.join(", ") : "(none)");
    details.append(editable, protectedFields);
    root.append(details);
  }
}

const migrationDestinationInput = document.querySelector("#migration-destination-path");
const migrationResult = document.querySelector("#migration-rehearsal-result");

migrationDestinationInput.addEventListener("input", invalidateMigrationRehearsal);
document.querySelector("#browse-migration-destination").addEventListener("click", async () => {
  try {
    const folder = await invoke("browse_directory");
    if (!folder) return;
    const separator = folder.includes("\\") ? "\\" : "/";
    migrationDestinationInput.value = folder.replace(/[\\/]+$/, "") +
      separator + "minglefield-migrated.sqlite3";
    invalidateMigrationRehearsal();
  } catch (error) {
    migrationResult.textContent = "Destination folder selection failed: " + String(error);
  }
});

document.querySelector("#preview-migration-rehearsal").addEventListener("click", async () => {
  const source = selectedDatabase;
  const destinationPath = migrationDestinationInput.value.trim();
  const requestSequence = ++rehearsalRequestSequence;
  temporaryEncryptedRequestSequence += 1;
  lastTemporaryEncryptedProof = null;
  document.querySelector("#temporary-sqlcipher-result").textContent =
    "Encrypted disk test must be repeated after the memory rehearsal.";
  lastMigrationRehearsal = null;
  migrationResult.textContent = "Verifying the complete database and staged changes on a disposable snapshot…";
  try {
    if (!source || !lastDatabaseInspection?.integrityOk || !lastDatabaseInspection.foreignKeysOk) {
      throw new Error("Select and inspect a valid existing database first.");
    }
    if (!destinationPath) throw new Error("Select a separate new database destination.");
    const corrections = allStagedMigrationChanges();
    const password = retainedSourceUnlockPassword;
    const request = invoke("preview_migration_rehearsal", {
      sourcePath: source, destinationPath, password, corrections
    });
    const preview = await request;
    if (requestSequence !== rehearsalRequestSequence || selectedDatabase !== source) return;
    if (preview.executionEnabled || preview.destinationCreated ||
        !preview.sourcePreserved || !preview.sourceIntegrityVerified ||
        preview.fullDataCopyVerified !== true || preview.encryptedDestinationVerified !== false ||
        !Number.isSafeInteger(preview.verifiedRowCount) ||
        preview.verifiedTableCount < preview.preservedTables.length) {
      throw new Error("Unexpected unsafe migration rehearsal result");
    }
    const coverage = assessFieldCoverage(preview.fieldCoverage, preview.preservedTables);
    renderFieldCoverage(coverage);
    lastMigrationRehearsal = { ...preview, sourcePath: source, destinationPath };
    migrationResult.textContent = JSON.stringify(preview, null, 2);
    document.querySelector("#review-migration-rehearsal-status").textContent =
      "Verified rehearsal: " + preview.verifiedChanges + " staged correction(s), " +
      preview.preservedTables.length + " existing tables accounted for, " +
      preview.fieldCoverage.reduce((sum, entry) => sum + entry.columns.length, 0) +
      " columns inventoried (" +
      preview.fieldCoverage.reduce((sum, entry) => sum + entry.protectedColumns.length, 0) +
      " protected). Full in-memory copy verified for " + preview.verifiedRowCount +
      " rows across " + preview.verifiedTableCount + " tables. No encrypted destination created. " +
      "Migration execution disabled.";
  } catch (error) {
    if (requestSequence !== rehearsalRequestSequence) return;
    document.querySelector("#migration-field-coverage").replaceChildren();
    migrationResult.textContent = "Migration rehearsal rejected: " + String(error);
    document.querySelector("#review-migration-rehearsal-status").textContent =
      "Migration rehearsal rejected. Migration execution remains disabled.";
  }
});

const tempDiskResult = document.querySelector("#temporary-sqlcipher-result");
// The two page-3 fields are the single source of the NEW destination password.
// Changing either invalidates a previously verified temporary disk proof.
for (const entry of [newDbPassword, confirmDbPassword, existingDbPassword]) {
  entry.addEventListener("input", () => {
    temporaryEncryptedRequestSequence += 1;
    lastTemporaryEncryptedProof = null;
    tempDiskResult.textContent = "Database credentials changed; reverify the encrypted temporary copy.";
  });
}
document.querySelector("#verify-temporary-sqlcipher").addEventListener("click", async () => {
  const source = selectedDatabase;
  const destinationPath = migrationDestinationInput.value.trim();
  const requestSequence = ++temporaryEncryptedRequestSequence;
  lastTemporaryEncryptedProof = null;
  tempDiskResult.textContent = "Rechecking staged corrections in the temporary encrypted SQLCipher copy…";
  try {
    if (!lastMigrationRehearsal || lastMigrationRehearsal.sourcePath !== source ||
        lastMigrationRehearsal.destinationPath !== destinationPath ||
        !lastMigrationRehearsal.fullDataCopyVerified) {
      throw new Error("First complete a successful in-memory migration rehearsal of all current edits.");
    }
    const corrections = allStagedMigrationChanges();
    if (corrections.length !== lastMigrationRehearsal.verifiedChanges) {
      throw new Error("Staged corrections changed since the last memory rehearsal.");
    }
    const credentials = selectTemporaryCopyCredentials({
      newPassword: newDbPassword.value,
      confirmation: confirmDbPassword.value,
      existingSourcePassword: retainedSourceUnlockPassword
    });
    const request = invoke("verify_temporary_encrypted_copy", {
      sourcePath: source, destinationPath,
      ...credentials, corrections
    });
    const raw = await request;
    if (requestSequence !== temporaryEncryptedRequestSequence || selectedDatabase !== source) return;
    lastTemporaryEncryptedProof = assessTemporaryDiskCopy(raw, lastMigrationRehearsal);
    tempDiskResult.textContent = JSON.stringify(lastTemporaryEncryptedProof, null, 2);
  } catch (error) {
    if (requestSequence !== temporaryEncryptedRequestSequence) return;
    tempDiskResult.textContent = "Temporary encrypted disk-copy test rejected: " + String(error);
  }
});

document.querySelector("#inspect-selected-database").addEventListener("click", inspectSelectedSqlite);

async function inspectDefaultUserData() {
  const output = document.querySelector("#data-result");
  const selection = document.querySelector("#database-selection");
  output.textContent = "Inspecting per-user Minglefield application data…";
  selection.replaceChildren();
  selectedDatabase = null;
  lastDatabaseInspection = null;
  resetDatabaseReview();
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
        radio.addEventListener("change", () => { selectedDatabase = radio.value; lastDatabaseInspection = null; resetDatabaseReview(); });
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
        ...databaseReviewEvidence(lastDatabaseInspection)
      }, null, 2)
    : "No database inspected. Fresh installation still requires encrypted SQLCipher.";
  updateReviewSummary();
  if (lastMigrationRehearsal) {
    document.querySelector("#review-migration-rehearsal-status").textContent =
      "Dry-run verified for " + lastMigrationRehearsal.verifiedChanges +
      " staged correction(s), " + lastMigrationRehearsal.preservedTables.length +
      " tables and " + lastMigrationRehearsal.schemaObjectCount +
      " schema objects." +
      (lastTemporaryEncryptedProof
        ? " Temporary SQLCipher verified for " + lastTemporaryEncryptedProof.verifiedStagedChanges +
          " staged correction(s), all temporary files removed."
        : " Encrypted temporary copy has not been verified.") +
      " No final destination file created. Migration execution remains disabled.";
  }
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
for (const tab of ["login", "hosts", "effects", "jobs", "games", "all"]) {
  document.querySelector("#data-tab-" + tab).addEventListener("click", () => {
    for (const category of ["login", "hosts", "effects", "jobs", "games", "all"]) {
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
    document.querySelector("#data-editor-status").textContent = editedFullDb
      ? "Loaded " + editedFullDb.tables.length +
        " complete SQLite table(s) for domain-based editing. Migration execution remains disabled."
      : selectedDatabase
        ? "Inspect the selected database to load all application values. Migration remains blocked."
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
