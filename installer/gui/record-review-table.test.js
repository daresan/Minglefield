import test from "node:test";
import assert from "node:assert/strict";
import { REVIEW_COLUMNS, appendReviewTable } from "./record-review-table.js";

test("every verified reader field is represented by exactly one table column", () => {
  const shape = {
    users: ["userId","disabled"], agents: ["agentId","userId","disabled"],
    hosts: ["hostId","ownerId"],
    hostRuntimes: ["hostId","runtimeId","runtimeType","endpoint","enabled","inputFolder"],
    gitProfiles: ["hostId","profileId","ownerId","label","authMethod","gitExecutable","authorName","authorEmail"],
    effects: ["hostId","effectId","description","enabled"],
    alphaJobs: ["jobId","userId","agentId"],
    hostJobs: ["jobId","hostId","effectId","requestedBy","state"],
    games: ["projectId","hostId","ownerId","name","repositoryRoot","jobAttachmentsRoot","outputRoot","settingsRevision"]
  };
  assert.deepEqual(Object.keys(REVIEW_COLUMNS), Object.keys(shape));
  for (const [category, fields] of Object.entries(shape)) {
    assert.deepEqual(REVIEW_COLUMNS[category].map(c => c.name), fields);
  }
});

test("only previously implemented migration corrections get editable controls", () => {
  const actual = Object.fromEntries(Object.entries(REVIEW_COLUMNS).map(([name, cols]) =>
    [name, cols.filter(c => c.editor).map(c => c.name)]));
  assert.deepEqual(actual, {
    users: ["disabled"], agents: ["disabled"], hosts: [],
    hostRuntimes: [], gitProfiles: ["label","authorName","authorEmail"],
    effects: ["description","enabled"], alphaJobs: [], hostJobs: [],
    games: ["name","repositoryRoot","jobAttachmentsRoot","outputRoot"]
  });
});

class FakeNode {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.listeners = {};
    this.style = {};
  }
  append(...items) { this.children.push(...items); }
  setAttribute(name, value) { this[name] = value; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
}
test("table edits pass through validation and are restored when rejected", () => {
  const saved = globalThis.document;
  globalThis.document = { createElement: tag => new FakeNode(tag) };
  try {
    const root = new FakeNode("root");
    const rows = [{ hostId: "host1", effectId: "effect1",
      description: "Old", enabled: false }];
    let edits = 0;
    let errors = 0;
    appendReviewTable(root, "effects", rows, {
      onEdit: (_row, name, value) => {
        edits++;
        if (name === "description" && value === "invalid") throw new Error("invalid");
        return value === " New " ? "New" : value;
      },
      onError: () => { errors++; }
    });
    const table = root.children[1].children[0];
    const row = table.children[1].children[0];
    assert.equal(row.children.length, 4);
    assert.equal(row.children[0].children.length, 0);
    const input = row.children[2].children[0];
    input.value = " New ";
    input.listeners.change();
    assert.equal(rows[0].description, "New");
    assert.equal(input.value, "New");
    input.value = "invalid";
    input.listeners.change();
    assert.equal(input.value, "New");
    const checkbox = row.children[3].children[0];
    checkbox.checked = true;
    checkbox.listeners.change();
    assert.equal(rows[0].enabled, true);
    assert.equal(edits, 3);
    assert.equal(errors, 1);
  } finally {
    globalThis.document = saved;
  }
});

test("missing vetted fields fail closed instead of silently hiding columns", () => {
  const saved = globalThis.document;
  globalThis.document = { createElement: tag => new FakeNode(tag) };
  try {
    const root = new FakeNode("root");
    assert.throws(() => appendReviewTable(root, "effects",
      [{ hostId: "host1", effectId: "effect1", enabled: true }], {
        onEdit: () => true
      }), /Missing verified review field/);
  } finally {
    globalThis.document = saved;
  }
});
