import { invoke } from "@tauri-apps/api/core";
import {
  WIZARD_PAGES, validateInstallSelections, reviewRows,
  isExistingTargetWarning, installationRequest, verifyInstalledRunning
} from "./installation-review.js";
import { createInstallationDataEditor } from "./installation-data-edit.js";

const byId = id => document.getElementById(id);
const pages = [...document.querySelectorAll(".wizard-page")];
let wizardIndex = 0;
let installing = false;
let complete = false;
let databasePathCustomized = false;
let defaultDirs = null;
let defaultDbCandidates = [];
let discoveredDbReady = false;

async function discoverDefaultDatabases() {
  const status = byId("database-discovery-status");
  const select = byId("detected-database");
  status.textContent = "Suche im Minglefield-Datenordner …";
  try {
    const entries = await invoke("inspect_default_user_data");
    const found = entries
      .filter(item => item.kind === "sqlite_database" && typeof item.sourceDirectory === "string" &&
        typeof item.relativePath === "string" && item.relativePath !== "");
    defaultDbCandidates = found.map(item => ({
      path: item.sourceDirectory.replace(/[\\/]+$/, "") +
        (item.sourceDirectory.includes("\\") ? "\\" : "/") + item.relativePath,
      status: item.status
    }));
    select.replaceChildren();
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = found.length ? "Datenbank auswählen" : "Keine Datenbank gefunden";
    select.append(empty);
    defaultDbCandidates.forEach((item, i) => {
      const option = document.createElement("option");
      option.value = String(i);
      option.textContent = item.path +
        (item.status === "sqlite_header_valid_unverified" ? " (SQLite)" : " (verschlüsselt / noch ungeprüft)");
      select.append(option);
    });
    status.textContent = found.length
      ? found.length + " DB-Vorschläge gefunden. Verwende die passende DB als Quelle oder bereits verschlüsseltes Ziel."
      : "Keine bekannten DB-Dateien gefunden. Eine Datei kann weiterhin manuell gewählt werden.";
  } catch {
    status.textContent = "Automatische Suche nicht verfügbar; Datenbank kann manuell ausgewählt werden.";
  }
  discoveredDbReady = true;
}

function useDiscoveredDatabase(target) {
  const index = Number(byId("detected-database").value);
  if (byId("detected-database").value === "" || !Number.isInteger(index)) return;
  const candidate = defaultDbCandidates[index];
  if (!candidate) return;
  if (target) {
    // The DB must be unlocked with its existing SQLCipher password.
    byId("source-database").value = "";
    byId("database-path").value = candidate.path;
    databasePathCustomized = true;
  } else {
    byId("source-database").value = candidate.path;
    // Keep the proposed destination DISTINCT from the selected source.
    if (byId("database-path").value.trim() === candidate.path) {
      byId("database-path").value = candidate.path + ".migrated.sqlite3";
      databasePathCustomized = true;
    }
  }
  databaseEditor.clear();
  if (wizardIndex === 5) refreshReview();
}
const databaseEditor = createInstallationDataEditor(document, invoke);

function collectForm() {
  return {
    mode: document.querySelector('input[name="setup-mode"]:checked').value,
    installDir: byId("install-dir").value.trim(),
    dataDir: byId("data-dir").value.trim(),
    databasePath: byId("database-path").value.trim(),
    sourceDatabase: byId("source-database").value.trim(),
    sourcePassword: byId("source-password").value,
    databasePassword: byId("database-password").value,
    databasePasswordConfirmation: byId("database-password-confirm").value,
    loginPassword: byId("admin-password").value,
    loginPasswordConfirmation: byId("admin-password-confirm").value
  };
}

function applyMode() {
  const standard =
    document.querySelector('input[name="setup-mode"]:checked').value === "standard";
  byId("mode-description").textContent = standard
    ? "Standard verwendet die empfohlenen Speicherorte im Benutzerprofil."
    : "Erweitert erlaubt die freie Auswahl von Programm- und Datenverzeichnis.";
  for (const id of ["install-dir", "data-dir", "browse-install-dir", "browse-data-dir"]) {
    byId(id).disabled = standard || installing || complete;
  }
  if (standard && defaultDirs) {
    byId("install-dir").value = defaultDirs.installDir;
    byId("data-dir").value = defaultDirs.dataDir;
    if (!databasePathCustomized) updateDefaultDatabasePath();
  }
}

function updateDefaultDatabasePath() {
  if (databasePathCustomized) return;
  const parent = byId("data-dir").value.trim().replace(/[\\/]+$/, "");
  if (parent) {
    byId("database-path").value =
      parent + (parent.includes("\\") ? "\\" : "/") + "minglefield.sqlite3";
  }
}

function refreshReview() {
  const form = collectForm();
  let staged = { correctionCount: 0, missingCount: 0, schemaChoice: "no" };
  let sourceIssue = "";
  try {
    staged = databaseEditor.selection(form);
  } catch (error) {
    sourceIssue = String(error);
  }
  const summary = byId("install-summary");
  summary.replaceChildren();
  for (const [name, value] of reviewRows(form, staged)) {
    const dt = document.createElement("dt");
    dt.textContent = name;
    const dd = document.createElement("dd");
    dd.textContent = value;
    summary.append(dt, dd);
  }
  const issue = validateInstallSelections(form) || sourceIssue ||
    (!form.loginPassword && !staged.adminExists
      ? "Bitte auf Seite 5 ein Loginpasswort für den neuen mingleadmin festlegen."
      : "");
  byId("ready-status").textContent = issue || "Bereit zur Installation.";
  byId("ready-status").style.color = issue ? "#f5c898" : "#b1e3cd";
  byId("install-now").disabled =
    installing || complete || !!issue || !byId("installation-approved").checked;
}

function showPage(index) {
  if (index < 0 || index >= pages.length || installing) return;
  wizardIndex = index;
  document.body.classList.toggle("review-data", index === 4);
  pages.forEach((page, i) => { page.hidden = i !== index; });
  byId("wizard-progress").textContent =
    "Schritt " + (index + 1) + " von " + pages.length + " – " + WIZARD_PAGES[index];
  byId("wizard-step-label").textContent = WIZARD_PAGES[index];
  byId("wizard-back").disabled = index === 0 || complete;
  byId("wizard-next").disabled = index === pages.length - 1 || complete;
  if (index === 4) {
    databaseEditor.inspect(collectForm()).then(() => {
      if (wizardIndex === pages.length - 1) refreshReview();
    });
  }
  if (index === pages.length - 1) refreshReview();
}

async function choosePath(id, command) {
  if (installing || complete) return;
  try {
    const chosen = await invoke(command);
    if (chosen) {
      byId(id).value = chosen;
      if (id === "data-dir") updateDefaultDatabasePath();
      if (id === "database-path") databasePathCustomized = true;
      if (id === "source-database" || (id === "database-path" && !byId("source-database").value.trim())) databaseEditor.clear();
      if (wizardIndex === 5) refreshReview();
    }
  } catch {
    // An unavailable file-picker is not an authorization or installation
    // failure; the operator can type or paste the path normally.
  }
}

async function install(continueExisting) {
  if (installing || complete) return;
  const form = collectForm();
  let staged;
  let issue = validateInstallSelections(form);
  try { staged = databaseEditor.selection(form); }
  catch (error) { issue = issue || String(error); }
  if (!issue && !form.loginPassword && !staged.adminExists) {
    issue = "Bitte auf Seite 5 ein Loginpasswort für den neuen mingleadmin festlegen.";
  }
  if (issue || !byId("installation-approved").checked) {
    refreshReview();
    return;
  }
  installing = true;
  byId("existing-warning").hidden = true;
  byId("install-now").disabled = true;
  byId("wizard-back").disabled = true;
  byId("installation-status").textContent =
    "Installation läuft: Datenbank übernehmen oder erstellen, Programmdateien installieren, " +
    "mingleadmin einrichten und Minglefield starten…";
  try {
    const result = verifyInstalledRunning(await invoke("install_minglefield", {
      request: installationRequest(form, continueExisting, staged)
    }));
    complete = true;
    byId("installation-status").textContent =
      "MINGLEFIELD INSTALLIERT UND GESTARTET.\n" +
      "Anwendung: " + result.installedApplication + "\n" +
      "Datenbank: " + result.encryptedDatabase + "\n" +
      "Lokaler Host: " + result.localHostId + "\n" +
      "Minglefield läuft auf: " + result.localUrl + "\n" +
      "Prozess-ID: " + result.nativeProcessId + "\n" +
      "Der Setup Manager kann geschlossen werden. Anmeldung in Minglefield wie gewohnt.";
    const link = byId("installed-url");
    link.href = result.localUrl;
    link.hidden = false;
  } catch (error) {
    if (isExistingTargetWarning(error) && !continueExisting) {
      byId("installation-status").textContent =
        "Vorhandenes Ziel erkannt. Bitte Weiter oder Abbruch wählen.";
      byId("existing-warning").hidden = false;
    } else {
      byId("installation-status").textContent =
        "Installation nicht abgeschlossen: " + String(error) +
        "\nVorhandene Daten und gesicherte Programmdateien werden nicht automatisch gelöscht.";
    }
  } finally {
    installing = false;
    byId("wizard-back").disabled = complete;
    refreshReview();
  }
}

for (const radio of document.querySelectorAll('input[name="setup-mode"]')) {
  radio.addEventListener("change", applyMode);
}
for (const id of [
  "install-dir", "data-dir", "source-database", "source-password",
  "database-path", "database-password", "database-password-confirm",
  "admin-password", "admin-password-confirm"
]) {
  byId(id).addEventListener("input", () => {
    if (id === "database-path") databasePathCustomized = true;
    if (id === "source-database" || id === "source-password" || (id === "database-path" && !byId("source-database").value.trim()) || (id === "database-password" && !byId("source-database").value.trim())) databaseEditor.clear();
    if (id === "data-dir") updateDefaultDatabasePath();
    if (wizardIndex === 5) refreshReview();
  });
}
byId("installation-approved").addEventListener("change", refreshReview);
byId("rescan-default-databases").addEventListener("click", discoverDefaultDatabases);
byId("use-detected-as-source").addEventListener("click", () => useDiscoveredDatabase(false));
byId("use-detected-as-target").addEventListener("click", () => useDiscoveredDatabase(true));
byId("inspect-selected-database").addEventListener("click", () => databaseEditor.inspect(collectForm()));
byId("browse-install-dir").addEventListener("click",
  () => choosePath("install-dir", "browse_directory"));
byId("browse-data-dir").addEventListener("click",
  () => choosePath("data-dir", "browse_directory"));
byId("browse-source-db").addEventListener("click",
  () => choosePath("source-database", "browse_sqlite_file"));
byId("wizard-back").addEventListener("click", () => showPage(wizardIndex - 1));
byId("wizard-next").addEventListener("click", () => showPage(wizardIndex + 1));
byId("install-now").addEventListener("click", () => install(false));
byId("existing-continue").addEventListener("click", () => install(true));
byId("existing-abort").addEventListener("click", () => {
  byId("existing-warning").hidden = true;
  byId("installation-status").textContent =
    "Abgebrochen. Es wurden keine weiteren Änderungen gestartet.";
});
window.addEventListener("pagehide", () => {
  for (const id of [
    "source-password", "database-password", "database-password-confirm",
    "admin-password", "admin-password-confirm"
  ]) byId(id).value = "";
});

async function initialize() {
  try {
    const defaults = await invoke("default_configuration");
    if (typeof defaults.installDir !== "string" ||
        typeof defaults.dataDir !== "string") {
      throw new Error("Ungültige Standardpfade");
    }
    defaultDirs = { installDir: defaults.installDir, dataDir: defaults.dataDir };
    applyMode();
    updateDefaultDatabasePath();
  } catch (error) {
    byId("mode-description").textContent =
      "Standardpfade nicht verfügbar: " + String(error) +
      ". Unter Erweitert bitte Pfade auswählen.";
    document.querySelector('input[name="setup-mode"][value="advanced"]').checked = true;
    applyMode();
  }
  try {
    const license = await invoke("framework_license");
    byId("license-text").textContent = license.text || "Lizenztext nicht verfügbar.";
  } catch {
    byId("license-text").textContent = "Lizenztext ist in dieser Vorschau nicht verfügbar.";
  }
  try {
    const readme = await invoke("application_readme");
    byId("readme-text").textContent = readme.text || "Projektinformationen sind nicht verfügbar.";
  } catch {
    byId("readme-text").textContent = "Projektinformationen sind nicht verfügbar.";
  }
  showPage(0);
  await discoverDefaultDatabases();
}
initialize();
