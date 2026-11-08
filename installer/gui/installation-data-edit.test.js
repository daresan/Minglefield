import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { approvedSchemaAdditions, selectedDataCorrections, existingInstallerAdmin, DATABASE_DOMAINS } from "./installation-data-edit.js";
import { createFullReview, stageFullCell } from "./full-database-review.js";

test("existing product DB editor retains all five domains plus extra tables", () => {
  assert.deepEqual(DATABASE_DOMAINS, ["login", "hosts", "effects", "jobs", "games", "all"]);
  const html = readFileSync(new URL("./index.html", import.meta.url), "utf8");
  const main = readFileSync(new URL("./main.js", import.meta.url), "utf8");
  for (const domain of DATABASE_DOMAINS) {
    assert.ok(html.includes('id="data-fields-' + domain + '"'), domain);
    assert.ok(html.includes('id="data-tab-' + domain + '"'), domain);
  }
  assert.ok(main.includes('createInstallationDataEditor(document, invoke)'));
  assert.ok(main.includes('request: installationRequest(form, continueExisting, staged)'));
  assert.ok(!main.includes('create_experimental_encrypted_copy'));
  assert.ok(!main.includes('verify_temporary_encrypted_copy'));
});

test("schema migration remains an explicit yes/no choice, separate from installation and launch", () => {
  assert.deepEqual(approvedSchemaAdditions(["idx_A", "trigger_B"], "no"), []);
  assert.deepEqual(approvedSchemaAdditions(["idx_A", "trigger_B"], "yes"), ["idx_A", "trigger_B"]);
  assert.throws(() => approvedSchemaAdditions(["idx_A"], "maybe"));
  assert.throws(() => approvedSchemaAdditions(["idx_A", "idx_A"], "yes"));
  const html = readFileSync(new URL("./index.html", import.meta.url), "utf8");
  assert.equal((html.match(/type="checkbox"/g) ?? []).length, 2);
  assert.ok(html.includes('id="installation-approved"'));
  assert.ok(html.includes('id="start-after-install"'));
  assert.ok(html.includes('id="schema-migrate-choice"'));
  assert.ok(html.includes('<option value="no" selected>'));
  assert.ok(html.includes('<option value="yes">'));
});

test("typed edited records survive staging and become full_row corrections for actual install", () => {
  const original = createFullReview({ tables: [{
    name: "alpha_users", columns: ["user_id", "disabled"],
    rows: [{ rowId: "1", cells: [
      { kind: "text", value: "existing-user" },
      { kind: "integer", value: "0" }
    ] }]
  }] });
  const edited = stageFullCell(original, "alpha_users", 0, "disabled", "integer", "1");
  const changes = selectedDataCorrections(original, edited);
  assert.equal(changes.length, 1);
  assert.equal(changes[0].kind, "full_row");
  assert.equal(changes[0].table, "alpha_users");
  assert.equal(changes[0].row_id, "1");
  assert.deepEqual(changes[0].before[1], { kind: "integer", value: "0" });
  assert.deepEqual(changes[0].after[1], { kind: "integer", value: "1" });
  assert.deepEqual(selectedDataCorrections(null, null), []);
  assert.throws(() => selectedDataCorrections(original, null));
  assert.equal(original.tables[0].rows[0].cells[1].value, "0");
});

test("page-five account inventory allows existing mingleadmin but prevents missing new password", () => {
  const account = disabled => createFullReview({ tables: [{
    name: "alpha_users", columns: ["user_id", "disabled"],
    rows: [{rowId:"1", cells:[
      {kind:"text", value:"mingleadmin"},
      {kind:"integer", value:String(disabled)}
    ]}]
  }]});
  const other = createFullReview({ tables: [{
    name: "alpha_users", columns: ["user_id", "disabled"],
    rows: [{rowId:"1", cells:[
      {kind:"text", value:"other-admin"},
      {kind:"integer", value:"0"}
    ]}]
  }]});
  assert.equal(existingInstallerAdmin(account(0)), true);
  assert.equal(existingInstallerAdmin(other), false);
  assert.equal(existingInstallerAdmin(null), false);
  // A disabled account is still an existing identity. The backend must
  // reject unauthorized reactivation rather than silently creating a clone.
  assert.equal(existingInstallerAdmin(account(1)), true);
});
