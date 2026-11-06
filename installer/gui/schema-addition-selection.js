// Select missing registered DDL objects as an ordinary version-compatibility
// choice. This frontend input is advisory; Rust validates exact registered
// names and runs all selected DDL in one isolated transaction.
export function validateSchemaAdditionSelection(missingObjects, selection) {
  if (!Array.isArray(missingObjects) ||
      !missingObjects.every(x => typeof x === "string" && x.length > 0) ||
      new Set(missingObjects).size !== missingObjects.length) {
    throw new Error("Missing schema-object evidence must be valid.");
  }
  if (!Array.isArray(selection) || selection.some(x => typeof x !== "string") ||
      new Set(selection).size !== selection.length ||
      selection.some(x => !missingObjects.includes(x))) {
    throw new Error("Select only the currently reported missing schema objects.");
  }
  return [...selection];
}
