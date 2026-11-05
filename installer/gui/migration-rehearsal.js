import { alphaUserCorrections } from "./alpha-user-review.js";
import { legacyCorrections } from "./legacy-record-review.js";

// Translate checked memory-only edits to the narrow, typed Rust rehearsal API.
// Never pass credentials, job execution state, owner IDs, or source rows.
export function stagedMigrationChanges(
  originalAlphaUsers, editedAlphaUsers, originalLegacyRecords, editedLegacyRecords, loadIssues
) {
  if (!originalAlphaUsers || !editedAlphaUsers ||
      !originalLegacyRecords || !editedLegacyRecords ||
      !Array.isArray(loadIssues) || loadIssues.length) {
    throw new Error("Complete application record review is required before rehearsal.");
  }
  const before = new Map(originalAlphaUsers.map(row => [row.userId, row]));
  const users = alphaUserCorrections(originalAlphaUsers, editedAlphaUsers).map(change => ({
    kind: "user_disabled",
    user_id: change.userId,
    before: before.get(change.userId).disabled,
    after: change.disabled
  }));
  const records = legacyCorrections(originalLegacyRecords, editedLegacyRecords).map(change => {
    if (change.category === "effects" && change.field === "description") {
      const [host_id, effect_id] = JSON.parse(change.key);
      return {
        kind: "effect_description", host_id, effect_id,
        before: change.previous, after: change.next
      };
    }
    if (change.category === "games" && change.field === "name") {
      return {
        kind: "game_name", project_id: change.key,
        before: change.previous, after: change.next
      };
    }
    throw new Error("Unsupported staged correction");
  });
  return [...users, ...records];
}
