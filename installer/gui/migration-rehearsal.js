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
  const owners = new Map(originalLegacyRecords.agents.map(agent => [agent.agentId, agent.userId]));
  const records = legacyCorrections(originalLegacyRecords, editedLegacyRecords).map(change => {
    if (change.category === "agents" && change.field === "disabled") {
      return {
        kind: "agent_disabled", agent_id: change.key,
        user_id: owners.get(change.key),
        before: change.previous, after: change.next
      };
    }
    if (change.category === "effects" && change.field === "description") {
      const [host_id, effect_id] = JSON.parse(change.key);
      return {
        kind: "effect_description", host_id, effect_id,
        before: change.previous, after: change.next
      };
    }
    if (change.category === "effects" && change.field === "enabled") {
      const [host_id, effect_id] = JSON.parse(change.key);
      return {
        kind: "effect_enabled", host_id, effect_id,
        before: change.previous, after: change.next
      };
    }
    if (change.category === "games" &&
        ["repositoryRoot", "jobAttachmentsRoot", "outputRoot"].includes(change.field)) {
      return {
        kind: "game_path", project_id: change.key,
        field: {
          repositoryRoot: "repository_root",
          jobAttachmentsRoot: "job_attachments_root",
          outputRoot: "output_root"
        }[change.field],
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
