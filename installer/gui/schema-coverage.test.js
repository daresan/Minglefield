import test from "node:test";
import assert from "node:assert/strict";
import { assessFieldCoverage } from "./schema-coverage.js";

const inventory = () => [
  {table: "alpha_users", rows: 2},
  {table: "alpha_passwords", rows: 2},
  {table: "new_extension", rows: 1}
];
const coverage = () => [
  {table: "alpha_users", columns: ["user_id", "disabled"],
    stagedEditableColumns: ["disabled"], protectedColumns: ["user_id"]},
  {table: "alpha_passwords", columns: ["user_id", "salt", "password_hash"],
    stagedEditableColumns: [], protectedColumns: ["user_id", "salt", "password_hash"]},
  {table: "new_extension", columns: ["secret", "id"],
    stagedEditableColumns: [], protectedColumns: ["secret", "id"]}
];

test("accounts for all fields including protected credentials and unknown extensions", () => {
  const summary = assessFieldCoverage(coverage(), inventory());
  assert.deepEqual(
    [summary.tables, summary.columns, summary.editableColumns, summary.protectedColumns],
    [3, 7, 1, 6]
  );
  assert.deepEqual(summary.entries[2], {
    table: "new_extension", rows: 1, editable: [], protected: ["secret", "id"]
  });
});

test("rejects absent tables, missing or double-classified columns, bad counts and duplicate names", () => {
  const examples = [];
  let missingTable = coverage();
  missingTable.pop();
  examples.push([missingTable, inventory()]);
  let unclassified = coverage();
  unclassified[1].protectedColumns.pop();
  examples.push([unclassified, inventory()]);
  let duplicated = coverage();
  duplicated[0].protectedColumns.push("disabled");
  examples.push([duplicated, inventory()]);
  let repeated = coverage();
  repeated[0].columns.push("disabled");
  examples.push([repeated, inventory()]);
  let noRows = inventory();
  noRows[1].rows = -1;
  examples.push([coverage(), noRows]);
  let badTables = inventory();
  badTables[1].table = "alpha_users";
  examples.push([coverage(), badTables]);
  for (const [fields, counts] of examples) {
    assert.throws(() => assessFieldCoverage(fields, counts));
  }
});
