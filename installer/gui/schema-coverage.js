// Validate a schema-only migration rehearsal report before presenting it.
// Unrecognized source tables are kept and all their fields stay protected.
export function assessFieldCoverage(fieldCoverage, preservedTables) {
  if (!Array.isArray(fieldCoverage) || !Array.isArray(preservedTables) ||
      fieldCoverage.length !== preservedTables.length || fieldCoverage.length > 512) {
    throw new Error("Schema coverage does not match the complete table inventory");
  }
  const rowCounts = new Map();
  for (const table of preservedTables) {
    if (!table || typeof table.table !== "string" || !table.table ||
        rowCounts.has(table.table) || !Number.isSafeInteger(table.rows) || table.rows < 0) {
      throw new Error("Invalid or duplicate table inventory");
    }
    rowCounts.set(table.table, table.rows);
  }
  const seen = new Set();
  let columns = 0;
  let protectedColumns = 0;
  let editableColumns = 0;
  const entries = fieldCoverage.map(entry => {
    if (!entry || typeof entry.table !== "string" || !rowCounts.has(entry.table) ||
        seen.has(entry.table) ||
        !Array.isArray(entry.columns) || !Array.isArray(entry.stagedEditableColumns) ||
        !Array.isArray(entry.protectedColumns)) {
      throw new Error("Invalid or duplicate schema field coverage");
    }
    seen.add(entry.table);
    const validNames = names => names.every(name => typeof name === "string" &&
      name.length > 0 && name.length <= 256);
    if (!validNames(entry.columns) || !validNames(entry.stagedEditableColumns) ||
        !validNames(entry.protectedColumns) ||
        new Set(entry.columns).size !== entry.columns.length) {
      throw new Error("Invalid database column names or duplicates");
    }
    const original = new Set(entry.columns);
    const editable = new Set(entry.stagedEditableColumns);
    const protectedSet = new Set(entry.protectedColumns);
    if (editable.size !== entry.stagedEditableColumns.length ||
        protectedSet.size !== entry.protectedColumns.length ||
        [...editable].some(name => !original.has(name) || protectedSet.has(name)) ||
        [...protectedSet].some(name => !original.has(name)) ||
        editable.size + protectedSet.size !== original.size) {
      throw new Error("A source column is missing or misclassified");
    }
    columns += entry.columns.length;
    editableColumns += editable.size;
    protectedColumns += protectedSet.size;
    return {
      table: entry.table,
      rows: rowCounts.get(entry.table),
      editable: [...entry.stagedEditableColumns],
      protected: [...entry.protectedColumns]
    };
  });
  if (seen.size !== rowCounts.size) throw new Error("A database table is missing from field coverage");
  return { tables: entries.length, columns, editableColumns, protectedColumns, entries };
}
