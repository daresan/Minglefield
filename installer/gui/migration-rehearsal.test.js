import test from "node:test";
import assert from "node:assert/strict";
import { stagedMigrationChanges } from "./migration-rehearsal.js";

const alpha = () => [{ userId: "alice", disabled: false }];
const legacy = () => ({
  hosts: [{ hostId: "host1", ownerId: "alice" }],
  effects: [{ hostId: "host1", effectId: "effect1", description: "Old", enabled: false }],
  hostJobs: [{ jobId: "job1", hostId: "host1", effectId: "effect1", requestedBy: "alice", state: "queued" }],
  games: [{ projectId: "game1", hostId: "host1", ownerId: "alice", name: "Old game", repositoryRoot: "/games/one" }],
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
