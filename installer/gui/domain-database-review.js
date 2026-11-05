// One editable typed SQLite surface per domain; no secondary editor for
// the same row. All callbacks use the latest staged review, never an old copy.
import { REVIEW_CATEGORIES, groupReviewedTables } from "./database-review-categories.js";
import { renderFullDatabaseTable } from "./full-database-table.js";

const LABELS = Object.freeze({
  login: "Anmeldung", hosts: "Hosts", effects: "Effekte",
  jobs: "Jobs", games: "Games", all: "Sonstige DB-Tabellen"
});

export function renderDomainDatabaseReview(doc, getReview, onEdit, onError) {
  const review = getReview();
  const groups = review ? groupReviewedTables(review) : null;
  let accounted = 0;
  for (const category of REVIEW_CATEGORIES) {
    const root = doc.querySelector("#data-fields-" + category);
    root.replaceChildren();
    const tables = groups?.[category] ?? [];
    accounted += tables.length;
    if (category === "all") {
      const fallback = doc.querySelector("#data-tab-all");
      fallback.hidden = !tables.length;
      if (!tables.length && !doc.querySelector("#data-editor-all").hidden) {
        doc.querySelector("#data-editor-all").hidden = true;
        doc.querySelector("#data-editor-login").hidden = false;
      }
    }
    if (!tables.length) {
      root.textContent = review
        ? "Keine Tabellen diesem Bereich zugeordnet."
        : "Noch keine geprüften Datenbanktabellen geladen.";
      continue;
    }
    const note = doc.createElement("p");
    note.className = "help";
    note.textContent = tables.length + " Tabelle(n) in " + LABELS[category] +
      ". Alle gespeicherten Werte sind typisiert bearbeitbar; Änderungen " +
      "werden ausschließlich für die isolierte Migration vorgemerkt.";
    const selectorLabel = doc.createElement("label");
    selectorLabel.textContent = "Tabelle";
    const selector = doc.createElement("select");
    selector.setAttribute("aria-label", LABELS[category] + ": Datenbanktabelle");
    selectorLabel.append(selector);
    for (const table of tables) {
      const option = doc.createElement("option");
      option.value = table.name;
      option.textContent = table.name + " (" + table.rows.length + " Zeilen)";
      selector.append(option);
    }
    const content = doc.createElement("div");
    content.setAttribute("data-table-review", category);
    selector.addEventListener("change", () => {
      const table = getReview()?.tables.find(item => item.name === selector.value);
      if (!table || !tables.some(item => item.name === selector.value)) {
        content.textContent = "Tabelle nicht mehr in der geprüften Auswahl.";
        return;
      }
      renderFullDatabaseTable(content, table,
        (rowIndex, column, kind, value) => onEdit(table.name, rowIndex, column, kind, value),
        onError);
    });
    root.append(note, selectorLabel, content);
    selector.value = tables[0].name;
    // A real change listener is also used by mouse and keyboard navigation.
    const first = getReview()?.tables.find(item => item.name === selector.value);
    renderFullDatabaseTable(content, first,
      (rowIndex, column, kind, value) => onEdit(first.name, rowIndex, column, kind, value),
      onError);
  }
  if (groups && accounted !== review.tables.length) {
    throw new Error("Not all SQLite tables were assigned a review category");
  }
}
