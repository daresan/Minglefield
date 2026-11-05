// Typed, schema-driven, in-memory review of every SQLite application table.
// No source writes. Values are never included in the public install plan.
const KINDS = new Set(["null", "integer", "real", "text", "blob"]);
const INT64_MIN = -(1n << 63n);
const INT64_MAX = (1n << 63n) - 1n;

export function verifyFullCell(cell) {
  if (!cell || typeof cell !== "object" || !KINDS.has(cell.kind)) {
    throw new Error("Unrecognized SQLite storage type");
  }
  if (cell.kind === "null") {
    if (cell.value !== null) throw new Error("Invalid NULL value");
    return;
  }
  if (typeof cell.value !== "string") throw new Error("Invalid SQLite value");
  if (cell.kind === "integer") {
    if (!/^-?\d+$/.test(cell.value)) throw new Error("Invalid SQLite integer");
    const value = BigInt(cell.value);
    if (value < INT64_MIN || value > INT64_MAX) throw new Error("SQLite integer outside signed 64-bit range");
  } else if (cell.kind === "real") {
    if (!cell.value.trim() || !Number.isFinite(Number(cell.value))) {
      throw new Error("Invalid SQLite real number");
    }
  } else if (cell.kind === "blob") {
    if (cell.value.length > 8 * 1024 * 1024 ||
        cell.value.length % 2 || !/^[a-fA-F0-9]*$/.test(cell.value)) {
      throw new Error("BLOB must contain hexadecimal byte pairs (max 4 MiB)");
    }
  } else if (cell.value.length > 4 * 1024 * 1024) {
    throw new Error("SQLite text exceeds the review limit");
  }
}

export function createFullReview(review) {
  if (!review || !Array.isArray(review.tables) || review.tables.length > 4096) {
    throw new Error("Invalid full database review");
  }
  const names = new Set();
  for (const table of review.tables) {
    if (!table || typeof table.name !== "string" || !table.name ||
        names.has(table.name) || !Array.isArray(table.columns) ||
        table.columns.length < 1 || table.columns.length > 1024 ||
        new Set(table.columns).size !== table.columns.length ||
        table.columns.some(c => typeof c !== "string" || !c) ||
        !Array.isArray(table.rows) || table.rows.length > 5000) {
      throw new Error("Incomplete or duplicate table layout");
    }
    names.add(table.name);
    const ids = new Set();
    for (const row of table.rows) {
      if (!row || (row.rowId !== null && (typeof row.rowId !== "string" ||
            !/^-?\d+$/.test(row.rowId))) ||
          !Array.isArray(row.cells) || row.cells.length !== table.columns.length) {
        throw new Error("Incomplete SQLite row");
      }
      if (row.rowId !== null) {
        if (ids.has(row.rowId)) throw new Error("Duplicate SQLite rowid");
        ids.add(row.rowId);
      }
      row.cells.forEach(verifyFullCell);
    }
  }
  return { tables: review.tables.map(table => ({
    name: table.name, columns: [...table.columns],
    rows: table.rows.map(row => ({rowId: row.rowId,
      cells: row.cells.map(cell => ({kind: cell.kind, value: cell.value}))}))
  })) };
}

export function stageFullCell(review, tableName, rowIndex, columnName, kind, value) {
  const typed = { kind, value };
  verifyFullCell(typed);
  const next = createFullReview(review);
  const table = next.tables.find(item => item.name === tableName);
  if (!table) throw new Error("Unknown source table");
  const index = table.columns.indexOf(columnName);
  if (index < 0 || !Number.isInteger(rowIndex) ||
      rowIndex < 0 || rowIndex >= table.rows.length) throw new Error("Unknown source cell");
  table.rows[rowIndex].cells[index] = typed;
  return next;
}

export function fullRowCorrections(original, edited) {
  const before = createFullReview(original);
  const after = createFullReview(edited);
  if (before.tables.length !== after.tables.length) throw new Error("Table inventory changed");
  const changes = [];
  for (let t = 0; t < before.tables.length; t++) {
    const a = before.tables[t], b = after.tables[t];
    if (a.name !== b.name || JSON.stringify(a.columns) !== JSON.stringify(b.columns) ||
        a.rows.length !== b.rows.length) throw new Error("Source schema changed");
    for (let r = 0; r < a.rows.length; r++) {
      const left = a.rows[r], right = b.rows[r];
      if (left.rowId !== right.rowId) throw new Error("Original row identity changed");
      if (JSON.stringify(left.cells) !== JSON.stringify(right.cells)) {
        changes.push({
          kind: "full_row", table: a.name, row_id: left.rowId,
          columns: [...a.columns], before: left.cells, after: right.cells
        });
      }
    }
  }
  if (changes.length > 1500) throw new Error("Too many staged rows");
  return changes;
}

export function fullReviewSummary(corrections) {
  return corrections.map(change => ({
    table: change.table,
    rowId: change.row_id,
    changedColumns: change.columns.filter((col, index) =>
      JSON.stringify(change.before[index]) !== JSON.stringify(change.after[index]))
  }));
}
