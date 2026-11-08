// Product page 5: existing, verified typed SQLite editor plus schema decision.
// This module only READS the selected database and STAGES values in memory.
// All writes occur later inside the single consented Rust install_minglefield.
import { createFullReview, stageFullCell, fullRowCorrections, fullReviewSummary } from "./full-database-review.js";
import { renderDomainDatabaseReview } from "./domain-database-review.js";
import { databaseReviewEvidence } from "./database-review-evidence.js";
import { validateSchemaAdditionSelection } from "./schema-addition-selection.js";

export const DATABASE_DOMAINS = ["login", "hosts", "effects", "jobs", "games", "all"];

export function approvedSchemaAdditions(missing, choice) {
  if (!["yes", "no"].includes(choice)) throw new Error("Ungültige Schemamigrationsauswahl");
  return validateSchemaAdditionSelection(missing, choice === "yes" ? missing : []);
}

export function selectedDataCorrections(original, edited) {
  if (!original && !edited) return [];
  if (!original || !edited) throw new Error("Unvollständige Datenbankbearbeitung");
  return fullRowCorrections(original, edited);
}

// The new-local-admin password is mandatory when no existing account was
// observed in the read-only user inventory. This prevents initiating an
// installation that would necessarily fail after copying application files.
export function existingInstallerAdmin(review) {
  const table = review?.tables?.find(item => item.name === "alpha_users");
  if (!table) return false;
  const index = table.columns.indexOf("user_id");
  return index >= 0 && table.rows.some(row =>
    row.cells[index]?.kind === "text" &&
    row.cells[index]?.value === "mingleadmin"
  );
}

export function createInstallationDataEditor(doc, invoke) {
  const el = id => doc.getElementById(id);
  let original = null;
  let edited = null;
  let loadedSource = "";
  let loadedPassword = "";
  let loadedFromOriginalSource = false;
  let error = "";
  let busy = false;
  let missingObjects = [];
  let incompatibleObjects = [];
  let hostBindings = [];
  let requestId = 0;
  let didInspect = false;

  function clear() {
    requestId++;
    original = null;
    edited = null;
    loadedSource = "";
    loadedPassword = "";
    missingObjects = [];
    incompatibleObjects = [];
    hostBindings = [];
    const select = el("selected-local-host");
    select.replaceChildren();
    const placeholder = doc.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Lokalen Host automatisch erkennen";
    select.append(placeholder);
    el("host-selection-info").textContent =
      "Vorhandene Hostzuordnungen werden aus der Datenbank gelesen.";
    error = "";
    didInspect = false;
    busy = false;
    el("schema-migrate-choice").value = "no";
    el("schema-review-section").hidden = true;
    el("data-editor").hidden = true;
    el("data-source-status").textContent = "Noch keine vorhandene Datenbank entsperrt.";
    el("data-review-corrections").textContent = "Keine Datenänderungen vorgemerkt.";
    el("inspect-selected-database").disabled = false;
  }

  function showCategory(selected) {
    for (const category of DATABASE_DOMAINS) {
      el("data-editor-" + category).hidden = selected !== category;
      el("data-tab-" + category).setAttribute("aria-pressed", String(selected === category));
    }
  }

  for (const category of DATABASE_DOMAINS) {
    el("data-tab-" + category).addEventListener("click", () => showCategory(category));
  }
  showCategory("login");

  function refreshEdits() {
    const changes = selectedDataCorrections(original, edited);
    el("data-editor-status").textContent =
      edited.tables.length + " Tabellen · " + changes.length + " geänderte Datensätze vorgemerkt.";
    const content = el("data-review-corrections");
    content.replaceChildren();
    if (!changes.length) {
      content.textContent = "Noch keine Werte geändert.";
      return;
    }
    const title = doc.createElement("p");
    title.textContent = "Für die Installation vorgemerkte Änderungen (ohne vertrauliche Werte):";
    content.append(title);
    for (const change of fullReviewSummary(changes)) {
      const line = doc.createElement("p");
      line.textContent = change.table + " / rowid " + (change.rowId || "ohne rowid") +
        " · " + change.changedColumns.join(", ");
      content.append(line);
    }
  }

  function onEdit(table, row, column, kind, value) {
    if (!loadedFromOriginalSource) {
      throw new Error("Für Änderungen eine bestehende DB als Quelle und eine neue Zieldatei auf Seite 4 auswählen.");
    }
    edited = stageFullCell(edited, table, row, column, kind, value);
    refreshEdits();
  }

  function render() {
    renderDomainDatabaseReview(doc, () => edited, onEdit,
      problem => { el("data-editor-status").textContent = String(problem); });
  }

  function renderHostBindings(hosts) {
    hostBindings = hosts;
    const select = el("selected-local-host");
    select.replaceChildren();
    const placeholder = doc.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Lokalen Host automatisch erkennen";
    select.append(placeholder);
    for (const host of hosts) {
      const option = doc.createElement("option");
      option.value = host.hostId;
      option.textContent = host.hostId + " (Operator: " + host.operatorId + ")";
      select.append(option);
    }
    if (hosts.length === 1) {
      select.value = hosts[0].hostId;
    } else {
      const knownLocal = hosts.filter(host =>
        host.hostId === "host.local" || host.hostId.startsWith("local."));
      if (knownLocal.length === 1) select.value = knownLocal[0].hostId;
    }
    el("host-selection-info").textContent = hosts.length
      ? "Die vorhandene Hostzuordnung bleibt erhalten. Bei mehreren Hosts bitte genau den Host dieses PCs wählen, keinen Remote-Host."
      : "Keine bestehende Hostzuordnung: Der Installer erstellt einen neuen lokalen Host.";
  }

  function renderSchema(inspection) {
    const audit = databaseReviewEvidence(inspection).schemaObjectAssessment;
    missingObjects = validateSchemaAdditionSelection(
      Array.isArray(audit?.missingObjects) ? audit.missingObjects : [], []);
    incompatibleObjects = Array.isArray(audit?.incompatibleObjects)
      ? audit.incompatibleObjects : [];
    const parts = [
      "Schema: " + (audit?.reason || "nicht klassifiziert"),
      Number.isInteger(audit?.matchedSchemaEntryCount) && Number.isInteger(audit?.expectedSchemaEntryCount)
        ? audit.matchedSchemaEntryCount + " von " + audit.expectedSchemaEntryCount + " registrierten Schemaobjekten vorhanden"
        : "",
      missingObjects.length + " fehlende registrierte Objekte",
      incompatibleObjects.length + " inkompatible Objekte"
    ].filter(Boolean);
    el("schema-audit-status").textContent = parts.join(" · ");
    el("schema-review-section").hidden = false;
    const list = el("missing-schema-choices");
    list.replaceChildren();
    for (const name of missingObjects) {
      const p = doc.createElement("p");
      p.textContent = name;
      list.append(p);
    }
    if (!missingObjects.length) {
      list.textContent = "Keine registrierten Schemaergänzungen erforderlich.";
    }
    const select = el("schema-migrate-choice");
    select.value = "no";
    select.disabled = !loadedFromOriginalSource || missingObjects.length === 0;
    el("missing-schema-description").textContent =
      incompatibleObjects.length
        ? "Inkompatible Objekte erkannt; eine automatische Ergänzung ersetzt oder entfernt keine bestehenden Tabellen."
        : "Das vorhandene Schema wird mit dem registrierten Minglefield-Schema verglichen. Die Ergänzung fehlender Objekte ist optional.";
  }

  async function inspect(form) {
    const path = (form.sourceDatabase || form.databasePath || "").trim();
    const key = form.sourceDatabase ? form.sourcePassword : form.databasePassword;
    if (!path) {
      clear();
      return;
    }
    if (didInspect && loadedSource === path && loadedPassword === key && !error) return;
    clear();
    const currentId = ++requestId;
    busy = true;
    el("inspect-selected-database").disabled = true;
    el("data-source-status").textContent =
      "Datenbank wird schreibgeschützt geöffnet; Datensätze und Schema werden eingelesen …";
    try {
      const inspection = await invoke("inspect_sqlite_database", { path, password: key });
      const data = createFullReview(await invoke("inspect_full_database", { path, password: key }));
      if (currentId !== requestId) return;
      if (inspection.integrityOk !== true || inspection.foreignKeysOk !== true) {
        throw new Error("Datenbankintegrität oder Fremdschlüssel nicht bestätigt.");
      }
      const tables = new Map(inspection.tables.map(table => [table.name, table.columns]));
      if (tables.size !== inspection.tables.length ||
          data.tables.length !== tables.size ||
          data.tables.some(table =>
            JSON.stringify(table.columns) !== JSON.stringify(tables.get(table.name)))) {
        throw new Error("Die gespeicherten Tabellen entsprechen nicht der geprüften Schemaübersicht.");
      }
      original = data;
      edited = createFullReview(data);
      loadedSource = path;
      loadedPassword = key;
      loadedFromOriginalSource = Boolean(form.sourceDatabase);
      error = "";
      didInspect = true;
      el("data-editor").hidden = false;
      el("data-source-status").textContent = data.tables.length +
        " Tabellen entsperrt und geladen. " +
        (loadedFromOriginalSource
          ? "Werte können für die neue verschlüsselte Zielkopie geändert werden."
          : "Das vorhandene Datenbankziel wird unverändert übernommen; zur Bearbeitung als Quelle mit neuer Zieldatei auswählen.");
      render();
      refreshEdits();
      renderSchema(inspection);
      // Host inventory is supplemental to the existing editable DB review.
      // A Host-specific failure must not discard successfully loaded tables.
      try {
        const hosts = await invoke("inspect_host_bindings", { path, password: key });
        if (currentId !== requestId) return;
        renderHostBindings(hosts);
      } catch {
        if (currentId !== requestId) return;
        el("host-selection-info").textContent =
          "Hostzuordnungen konnten nicht gelesen werden. Der Datenbankeditor bleibt verfügbar; die Hostzuordnung wird bei der Installation weiterhin geprüft.";
      }
    } catch (problem) {
      if (currentId !== requestId) return;
      error = String(problem);
      el("data-source-status").textContent = form.sourceDatabase
        ? "Quelldatenbank konnte nicht entsperrt werden: " + error
        : "Kein vorhandenes Datenbankziel geöffnet. Bei Neuinstallation ist dies normal.";
      el("schema-review-section").hidden = true;
      el("data-editor").hidden = true;
    } finally {
      if (currentId === requestId) {
        busy = false;
        el("inspect-selected-database").disabled = false;
      }
    }
  }

  function selection(form) {
    const path = (form.sourceDatabase || form.databasePath || "").trim();
    const key = form.sourceDatabase ? form.sourcePassword : form.databasePassword;
    if (form.sourceDatabase && (busy || !didInspect || path !== loadedSource ||
        key !== loadedPassword || error)) {
      throw new Error("Bitte Quelldatenbank auf Seite 5 entsperren und die Schemaüberprüfung abwarten.");
    }
    const corrections = form.sourceDatabase
      ? selectedDataCorrections(original, edited)
      : [];
    const schemaChoice = el("schema-migrate-choice").value;
    const schemaAdditions = form.sourceDatabase
      ? approvedSchemaAdditions(missingObjects, schemaChoice)
      : [];
    if (incompatibleObjects.length && schemaAdditions.length) {
      throw new Error("Inkompatible Schemaobjekte erfordern eine korrigierte Quelldatenbank.");
    }
    return {
      corrections,
      schemaAdditions,
      correctionCount: corrections.length,
      missingCount: missingObjects.length,
      schemaChoice: form.sourceDatabase ? schemaChoice : "no",
      adminExists: existingInstallerAdmin(original),
      localHostId: el("selected-local-host").value || null,
      hostBindings: hostBindings.length
    };
  }

  return { clear, inspect, selection, isBusy: () => busy };
}
