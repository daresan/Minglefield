import test from "node:test";
import assert from "node:assert/strict";
import { createLegacyReview, stageLegacyText, legacyCorrections } from "./legacy-record-review.js";

const sample = () => ({
  hosts: [{ hostId: "host-a", ownerId: "alice" }],
  effects: [{ hostId: "host-a", effectId: "effect-a", description: "Before", enabled: false }],
  hostJobs: [{ jobId: "job-a", hostId: "host-a", effectId: "effect-a", requestedBy: "alice", state: "queued" }],
  games: [{ projectId: "game-a", hostId: "host-a", ownerId: "alice", name: "Original", repositoryRoot: "/games/demo" }],
  unavailable: [],
});

test("stages real effect and game text without modifying the original", () => {
  const before = sample();
  const effect = stageLegacyText(createLegacyReview(before), "effects", JSON.stringify(["host-a", "effect-a"]), "description", "After");
  const next = stageLegacyText(effect, "games", "game-a", "name", " Renamed ");
  assert.equal(before.effects[0].description, "Before");
  assert.equal(before.games[0].name, "Original");
  assert.deepEqual(legacyCorrections(before, next), [
    { category: "effects", key: JSON.stringify(["host-a", "effect-a"]), field: "description", previous: "Before", next: "After" },
    { category: "games", key: "game-a", field: "name", previous: "Original", next: "Renamed" },
  ]);
});

test("refuses identifiers, owners, execution state, enabled flags and paths", () => {
  const original = sample();
  for (const [category, key, field] of [
    ["effects", JSON.stringify(["host-a", "effect-a"]), "enabled"],
    ["games", "game-a", "repositoryRoot"],
    ["hosts", "host-a", "ownerId"],
    ["hostJobs", "job-a", "state"],
  ]) {
    assert.throws(() => stageLegacyText(original, category, key, field, "changed"), /not editable/);
  }
  for (const [category, field, value] of [
    ["hosts", "ownerId", "mallory"],
    ["effects", "enabled", true],
    ["hostJobs", "state", "completed"],
    ["games", "repositoryRoot", "/other"],
  ]) {
    const modified = createLegacyReview(original);
    modified[category][0][field] = value;
    assert.throws(() => legacyCorrections(original, modified), /Read-only field changed/);
  }
});

test("rejects invalid names, excessive text, duplicate identities and removed records", () => {
  const before = sample();
  assert.throws(() => stageLegacyText(before, "games", "game-a", "name", "   "), /1–120/);
  assert.throws(() => stageLegacyText(before, "effects", JSON.stringify(["host-a", "effect-a"]), "description", "x".repeat(257)), /256/);
  const duplicate = sample();
  duplicate.games.push({ ...duplicate.games[0] });
  assert.throws(() => createLegacyReview(duplicate), /Duplicate/);
  const fewer = createLegacyReview(before);
  fewer.games.pop();
  assert.throws(() => legacyCorrections(before, fewer), /Record count changed/);
});

test("rejects an extra property", () => {
  const value = sample();
  value.hosts[0].extra = "unexpected";
  assert.throws(() => createLegacyReview(value), /Unexpected record fields/);
});
