import {stageFullCell, fullRowCorrections, fullReviewSummary} from "./full-database-review.js";

export function renderFullDatabaseTable(root, table, onEdit, onError, doc = document) {
  root.replaceChildren();
  if (!table) return;
  const info = doc.createElement("p");
  info.textContent = table.name + ": " + table.rows.length + " loaded rows, " +
    table.columns.length + " columns. Only stored values can be edited; " +
    "SQLite types are fixed. Changes are staged only on a disposable copy.";
  root.append(info);
  const scroll = doc.createElement("div");
  scroll.className = "data-table-scroll";
  const grid = doc.createElement("table");
  grid.className = "data-review-table";
  const header = doc.createElement("tr");
  for (const name of ["SQLite rowid", ...table.columns]) {
    const th = doc.createElement("th");
    th.textContent = name;
    header.append(th);
  }
  const head = doc.createElement("thead"); head.append(header);grid.append(head);
  const body = doc.createElement("tbody");
  table.rows.forEach((row, rowIndex) => {
    const tr = doc.createElement("tr");
    const rowTag = doc.createElement("td");
    rowTag.textContent = row.rowId ?? "(without rowid)";
    tr.append(rowTag);
    row.cells.forEach((cell, colIndex) => {
      const name = table.columns[colIndex];
      const td = doc.createElement("td");
      // Display the original SQLite storage class as read-only metadata.
      // The review edits values, not column definitions or storage types.
      const fixedType = doc.createElement("span");
      fixedType.className = "sqlite-fixed-type";
      fixedType.textContent = cell.kind.toUpperCase();
      fixedType.setAttribute("aria-label", table.name + " " + name + " original SQLite type (read only)");
      const input = doc.createElement(
        cell.kind === "text" || cell.kind === "blob" ? "textarea" : "input");
      input.value = cell.kind === "null" ? "(NULL)" : (cell.value ?? "");
      input.spellcheck = false;
      if (cell.kind === "null") input.disabled = true;
      if (input.tagName === "TEXTAREA") input.rows = 2;
      input.setAttribute("aria-label", table.name + " " + name + " value");
      let acceptedValue = cell.value;
      if (cell.kind !== "null") {
        input.addEventListener("change", () => {
          try {
            onEdit(rowIndex, name, cell.kind, input.value);
            acceptedValue = input.value;
          } catch(error) {
            input.value = acceptedValue ?? "";
            onError(error);
          }
        });
      }
      td.append(fixedType, input);
      tr.append(td);
    });
    body.append(tr);
  });
  grid.append(body); scroll.append(grid); root.append(scroll);
}

export {stageFullCell,fullRowCorrections,fullReviewSummary};
