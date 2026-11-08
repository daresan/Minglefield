import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  WIZARD_PAGES, validateInstallSelections, reviewRows,
  isExistingTargetWarning, installationRequest, verifyInstalledRunning
} from "./installation-review.js";
const form = {
  mode: "standard", installDir: "C:\\Programs\\Minglefield",
  databasePath: "C:\\Data\\minglefield.sqlite3",
  sourceDatabase: "C:\\old\\alpha.sqlite3", sourcePassword: "Old-Secret!",
  databasePassword: "New-Db-Password123!",
  databasePasswordConfirmation: "New-Db-Password123!",
  loginPassword: "New-Login-Password123!",
  loginPasswordConfirmation: "New-Login-Password123!"
};
test("six-page product wizard has administrator on five and review only on six", () => {
  const html = readFileSync(new URL("./index.html", import.meta.url), "utf8");
  assert.equal(WIZARD_PAGES.length, 6);
  assert.equal((html.match(/class="wizard-page"/g) || []).length, 6);
  assert.ok(html.indexOf('data-wizard-page="admin"') <
            html.indexOf('data-wizard-page="review"'));
  assert.equal((html.match(/type="checkbox"/g) || []).length, 1);
  assert.ok(html.includes("Installation durchführen"));
  assert.ok(html.includes('id="install-now"'));
  for (const forbidden of [
    "CREATE EXPERIMENTAL", "INSTALL MINGLEFIELD ALPHA", "Validate installation plan",
    "Geprüfte Alpha-Anwendungsdateien installieren", "Testkopie", "Migrationsprobe",
    "Lokalen Host und Administrator einrichten"
  ]) assert.ok(!html.includes(forbidden), forbidden);
});
test("one click owns all operations and the summary contains no credentials", () => {
  assert.equal(validateInstallSelections(form), null);
  assert.deepEqual(installationRequest(form, true), {
    installDir: form.installDir, databasePath: form.databasePath,
    sourceDatabase: form.sourceDatabase, sourcePassword: form.sourcePassword,
    databasePassword: form.databasePassword, loginPassword: form.loginPassword,
    loginPasswordConfirmation: form.loginPasswordConfirmation,
    approved: true, continueExisting: true
  });
  assert.equal(isExistingTargetWarning("INSTALL_WARNING_EXISTING: caution"), true);
  assert.equal(isExistingTargetWarning("other error"), false);
  assert.ok(!JSON.stringify(reviewRows(form)).includes(form.databasePassword));
  assert.ok(!JSON.stringify(reviewRows(form)).includes(form.loginPassword));
});
test("existing mingleadmin can be preserved without resetting credentials", () => {
  const existing = { ...form, loginPassword: "", loginPasswordConfirmation: "" };
  assert.equal(validateInstallSelections(existing), null);
  assert.equal(installationRequest(existing).approved, true);
});
test("running-app receipt must be encrypted loopback, not a false install success", () => {
  const good = {
    status: "minglefield_installed_and_running",
    encryptedDatabaseVerified: true, nativeApplicationRunning: true,
    localAdminUser: "mingleadmin",
    installedApplication: "C:\\Programs\\Minglefield",
    encryptedDatabase: "C:\\Data\\minglefield.sqlite3",
    localHostId: "local.0123456789abcdef0123456789abcdef",
    nativeProcessId: 1421, localUrl: "http://127.0.0.1:42900/"
  };
  assert.deepEqual(verifyInstalledRunning(good), good);
  for (const invalid of [
    { nativeApplicationRunning: false }, { encryptedDatabaseVerified: false },
    { localUrl: "http://0.0.0.0:42900/" }, { localAdminUser: "globaladmin" },
    { nativeProcessId: 0 }
  ]) assert.throws(() => verifyInstalledRunning({ ...good, ...invalid }));
});
