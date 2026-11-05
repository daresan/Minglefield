import test from "node:test";
import assert from "node:assert/strict";
import { createLegacyReview, stageLegacyText, stageLegacyToggle, legacyCorrections } from "./legacy-record-review.js";

const sample = () => ({
  hosts: [{ hostId: "host-a", ownerId: "alice" }],
  effects: [{ hostId: "host-a", effectId: "effect-a", description: "Before", enabled: false }],
  hostJobs: [{ jobId: "job-a", hostId: "host-a", effectId: "effect-a", requestedBy: "alice", state: "queued" }],
  games: [{ projectId: "game-a", hostId: "host-a", ownerId: "alice", name: "Original", repositoryRoot: "/games/demo", jobAttachmentsRoot: "/games/demo/attachments", outputRoot: "/games/demo/output", settingsRevision: 2 }],
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

test("refuses changes to identifiers, owners, execution state and revisions", () => {
  const original = sample();
  for (const [category, key, field] of [
    ["effects", JSON.stringify(["host-a", "effect-a"]), "enabled"],
    ["hosts", "host-a", "ownerId"],
    ["hostJobs", "job-a", "state"],
  ]) {
    assert.throws(() => stageLegacyText(original, category, key, field, "changed"), /not editable/);
  }
  for (const [category, field, value] of [
    ["hosts", "ownerId", "mallory"],
    ["hostJobs", "state", "completed"],
    ["games", "settingsRevision", 3],
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

test("stages all three project paths and effect activation without touching original rows", () => {
  const original = sample();
  const effectKey = JSON.stringify(["host-a", "effect-a"]);
  let edited = stageLegacyToggle(original, "effects", effectKey, "enabled", true);
  edited = stageLegacyText(edited, "games", "game-a", "repositoryRoot", "/new/game");
  edited = stageLegacyText(edited, "games", "game-a", "jobAttachmentsRoot", "/new/assets");
  edited = stageLegacyText(edited, "games", "game-a", "outputRoot", "/new/output");
  assert.deepEqual(legacyCorrections(original, edited), [
    {category: "effects", key: effectKey, field: "enabled", previous: false, next: true},
    {category: "games", key: "game-a", field: "repositoryRoot", previous: "/games/demo", next: "/new/game"},
    {category: "games", key: "game-a", field: "jobAttachmentsRoot", previous: "/games/demo/attachments", next: "/new/assets"},
    {category: "games", key: "game-a", field: "outputRoot", previous: "/games/demo/output", next: "/new/output"}
  ]);
  assert.equal(original.effects[0].enabled, false);
  assert.equal(original.games[0].repositoryRoot, "/games/demo");
});

test("rejects relative paths, parent traversals, invalid toggles and malformed revision", () => {
  const original = sample();
  for (const value of ["relative/directory", "/game/../escape", "", "/bad\\0path"]) {
    assert.throws(() => stageLegacyText(original, "games", "game-a", "repositoryRoot", value));
  }
  assert.throws(() => stageLegacyToggle(original, "effects", JSON.stringify(["host-a", "effect-a"]), "enabled", "true"), /not editable/);
  assert.throws(() => stageLegacyToggle(original, "hosts", "host-a", "enabled", true), /not editable/);
  const bad = sample();
  bad.games[0].settingsRevision = 0;
  assert.throws(() => createLegacyReview(bad), /Invalid game project fields/);
});
