import test from "node:test";
import assert from "node:assert/strict";
import { stagedMigrationChanges } from "./migration-rehearsal.js";

const alpha = () => [{ userId: "alice", disabled: false }];
const legacy = () => ({
  agents: [{ agentId: "agent1", userId: "alice", disabled: false }],
  hosts: [{ hostId: "host1", ownerId: "alice" }],
  effects: [{ hostId: "host1", effectId: "effect1", description: "Old", enabled: false }],
  hostJobs: [{ jobId: "job1", hostId: "host1", effectId: "effect1", requestedBy: "alice", state: "queued" }],
  games: [{ projectId: "game1", hostId: "host1", ownerId: "alice", name: "Old game", repositoryRoot: "/games/one", jobAttachmentsRoot: "/games/one/attachments", outputRoot: "/games/one/output", settingsRevision: 1 }],
  unavailable: []
});

test("converts all supported edits to strictly typed rehearsal changes", () => {
  const users = alpha();
  const modifiedUsers = [{ ...users[0], disabled: true }];
  const records = legacy();
  const edited = legacy();
  edited.effects[0].description = "Updated";
  edited.games[0].name = "Renamed";
  assert.deepEqual(stagedMigrationChanges(users, modifiedUsers, records, edited, []), [
    { kind: "user_disabled", user_id: "alice", before: false, after: true },
    { kind: "effect_description", host_id: "host1", effect_id: "effect1", before: "Old", after: "Updated" },
    { kind: "game_name", project_id: "game1", before: "Old game", after: "Renamed" }
  ]);
  assert.equal(users[0].disabled, false);
  assert.equal(records.games[0].name, "Old game");
});

test("refuses incomplete reader state and any read-only field changes", () => {
  const users = alpha();
  const records = legacy();
  assert.throws(
    () => stagedMigrationChanges(users, users, records, records, ["Alpha jobs failed"]),
    /Complete application record review/
  );
  assert.throws(
    () => stagedMigrationChanges(null, null, records, records, []),
    /Complete application record review/
  );
  const tampered = legacy();
  tampered.hosts[0].ownerId = "mallory";
  assert.throws(
    () => stagedMigrationChanges(users, users, records, tampered, []),
    /Read-only field changed/
  );
});

test("produces a valid no-change rehearsal on a complete review", () => {
  assert.deepEqual(stagedMigrationChanges(alpha(), alpha(), legacy(), legacy(), []), []);
});

test("maps additional safe fields to typed rehearsal changes", () => {
  const before = legacy();
  const after = legacy();
  after.effects[0].enabled = true;
  after.games[0].repositoryRoot = "/new/project";
  after.games[0].jobAttachmentsRoot = "/new/attachments";
  after.games[0].outputRoot = "/new/output";
  const changes = stagedMigrationChanges(alpha(), alpha(), before, after, []);
  assert.deepEqual(changes, [
    {kind: "effect_enabled", host_id: "host1", effect_id: "effect1", before: false, after: true},
    {kind: "game_path", project_id: "game1", field: "repository_root", before: "/games/one", after: "/new/project"},
    {kind: "game_path", project_id: "game1", field: "job_attachments_root", before: "/games/one/attachments", after: "/new/attachments"},
    {kind: "game_path", project_id: "game1", field: "output_root", before: "/games/one/output", after: "/new/output"}
  ]);
});
