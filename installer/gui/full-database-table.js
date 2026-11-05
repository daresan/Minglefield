import {stageFullCell, fullRowCorrections, fullReviewSummary} from "./full-database-review.js";
const TYPES = ["null","integer","real","text","blob"];

export function renderFullDatabaseTable(root, table, onEdit, onError) {
  root.replaceChildren();
  if (!table) return;
  const info = document.createElement("p");
  info.textContent = table.name + ": " + table.rows.length + " loaded rows, " +
    table.columns.length + " columns. Changes are staged only on a disposable copy.";
  root.append(info);
  const scroll = document.createElement("div");
  scroll.className = "data-table-scroll";
  const grid = document.createElement("table");
  grid.className = "data-review-table";
  const header = document.createElement("tr");
  for (const name of ["SQLite rowid", ...table.columns]) {
    const th = document.createElement("th");
    th.textContent = name;
    header.append(th);
  }
  const head = document.createElement("thead"); head.append(header);grid.append(head);
  const body = document.createElement("tbody");
  table.rows.forEach((row, rowIndex) => {
    const tr = document.createElement("tr");
    const rowTag = document.createElement("td");
    rowTag.textContent = row.rowId ?? "(without rowid)";
    tr.append(rowTag);
    row.cells.forEach((cell, colIndex) => {
      const name = table.columns[colIndex];
      const td = document.createElement("td");
      const type = document.createElement("select");
      type.setAttribute("aria-label", table.name + " " + name + " SQLite type");
      for (const kind of TYPES) {
        const option=document.createElement("option");
        option.value=kind;option.textContent=kind;type.append(option);
      }
      type.value = cell.kind;
      const input = document.createElement(
        cell.kind === "text" || cell.kind === "blob" ? "textarea" : "input");
      input.value = cell.value ?? "";
      input.spellcheck = false;
      if (cell.kind === "null") input.disabled = true;
      if (input.tagName === "TEXTAREA") input.rows = 2;
      input.setAttribute("aria-label", table.name + " " + name + " value");
      const original = { ...cell };
      type.addEventListener("change", () => {
        const kind = type.value;
        const value = kind === "null" ? null :
          kind === "integer" || kind === "real" ? "0" : "";
        try {
          onEdit(rowIndex, name, kind, value);
          original.kind = kind; original.value = value;
          input.disabled = kind === "null";
          input.value = value ?? "";
        } catch(error) { type.value = original.kind; onError(error); }
      });
      input.addEventListener("change", () => {
        try {
          onEdit(rowIndex, name, type.value, input.value);
          original.value=input.value;
        } catch(error) { input.value = original.value ?? ""; onError(error); }
      });
      td.append(type,input);
      tr.append(td);
    });
    body.append(tr);
  });
  grid.append(body); scroll.append(grid); root.append(scroll);
}

export {stageFullCell,fullRowCorrections,fullReviewSummary};
