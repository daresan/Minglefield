import { selectTemporaryCopyCredentials } from "./temporary-encrypted-review.js";

// Build *only* the read-only IPC payload from current user selections.
// In particular, an interrupted operation must not depend on a prior
// successful in-memory rehearsal or carry experimental write approval.
export function prepareReadOnlyRecoveryRequest({
  sourcePath, destinationPath, backupPath,
  existingSourcePassword, newPassword, confirmation,
  corrections, schemaAdditions
}) {
  for (const path of [sourcePath, destinationPath, backupPath]) {
    if (typeof path !== "string" || !path.trim()) {
      throw new Error("Quelle, Ziel und bestehendes separates Backup auswählen.");
    }
  }
  if (!Array.isArray(corrections) || !Array.isArray(schemaAdditions) ||
      !corrections.every(item => item && typeof item === "object" && !Array.isArray(item)) ||
      !schemaAdditions.every(name => typeof name === "string" && name.length > 0)) {
    throw new Error("Recovery-Auswahl ungültig; Daten und Schema erneut prüfen.");
  }
  const credentials = selectTemporaryCopyCredentials({
    newPassword, confirmation, existingSourcePassword
  });
  return {
    sourcePath: sourcePath.trim(),
    backupPath: backupPath.trim(),
    destinationPath: destinationPath.trim(),
    ...credentials,
    corrections: corrections.map(value => ({ ...value })),
    schemaAdditions: [...schemaAdditions]
  };
}
