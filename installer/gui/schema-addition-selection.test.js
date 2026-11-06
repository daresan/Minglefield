import { test } from "node:test";
import assert from "node:assert/strict";
import { validateSchemaAdditionSelection } from "./schema-addition-selection.js";

test("schema repair selection permits none, a single missing object or all", () => {
  const missing = ["missing_a", "missing_b"];
  assert.deepEqual(validateSchemaAdditionSelection(missing, []), []);
  assert.deepEqual(validateSchemaAdditionSelection(missing, ["missing_b"]), ["missing_b"]);
  assert.deepEqual(validateSchemaAdditionSelection(missing, missing), missing);
});

test("schema repair selection rejects stale, duplicate and invented choices", () => {
  const missing = ["missing_a", "missing_b"];
  for (const chosen of [["unknown"], ["missing_a", "missing_a"], ["missing_b", "unknown"], "missing_a"]) {
    assert.throws(() => validateSchemaAdditionSelection(missing, chosen));
  }
  assert.throws(() => validateSchemaAdditionSelection(["duplicate", "duplicate"], ["duplicate"]));
  assert.throws(() => validateSchemaAdditionSelection(null, []));
});
