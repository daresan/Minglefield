import { invoke } from "@tauri-apps/api/core";
import {
  WIZARD_PAGES, validateInstallSelections, reviewRows,
  isExistingTargetWarning, installationRequest, verifyInstalledRunning
} from "./installation-review.js";

const byId = id => document.getElementById(id);
const pages = [...document.querySelectorAll(".wizard-page")];
let wizardIndex = 0;
let installing = false;
let complete = false;
let databasePathCustomized = false;
let defaultDirs = null;

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
  const summary = byId("install-summary");
  summary.replaceChildren();
  for (const [name, value] of reviewRows(form)) {
    const dt = document.createElement("dt");
    dt.textContent = name;
    const dd = document.createElement("dd");
    dd.textContent = value;
    summary.append(dt, dd);
  }
  const issue = validateInstallSelections(form);
  byId("ready-status").textContent = issue || "Bereit zur Installation.";
  byId("ready-status").style.color = issue ? "#f5c898" : "#b1e3cd";
  byId("install-now").disabled =
    installing || complete || !!issue || !byId("installation-approved").checked;
}

function showPage(index) {
  if (index < 0 || index >= pages.length || installing) return;
  wizardIndex = index;
  pages.forEach((page, i) => { page.hidden = i !== index; });
  byId("wizard-progress").textContent =
    "Schritt " + (index + 1) + " von " + pages.length + " – " + WIZARD_PAGES[index];
  byId("wizard-step-label").textContent = WIZARD_PAGES[index];
  byId("wizard-back").disabled = index === 0 || complete;
  byId("wizard-next").disabled = index === pages.length - 1 || complete;
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
  const issue = validateInstallSelections(form);
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
      request: installationRequest(form, continueExisting)
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
    if (id === "data-dir") updateDefaultDatabasePath();
    if (wizardIndex === 5) refreshReview();
  });
}
byId("installation-approved").addEventListener("change", refreshReview);
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
  showPage(0);
}
initialize();
