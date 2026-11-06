import { test } from "node:test";
import assert from "node:assert/strict";
import { prepareReadOnlyRecoveryRequest } from "./read-only-recovery-request.js";

const required = () => ({
  sourcePath: " /tmp/source.sqlite3 ", destinationPath: " /tmp/encrypted.sqlite3 ",
  backupPath: " /tmp/backup.sqlite3 ", existingSourcePassword: "OldSourceKey123!",
  newPassword: "NewCipherKey123!", confirmation: "NewCipherKey123!",
  corrections: [{ table: "alpha_users", field: "disabled", after: 0 }],
  schemaAdditions: ["registered_index"]
});

test("recovery request is read-only, restart-independent and passes exact reviewed values", () => {
  const input = required();
  const got = prepareReadOnlyRecoveryRequest(input);
  assert.deepEqual(Object.keys(got).sort(), [
    "sourcePath", "backupPath", "destinationPath", "newPassword", "existingPassword",
    "corrections", "schemaAdditions"
  ].sort());
  assert.equal(got.sourcePath, "/tmp/source.sqlite3");
  assert.equal(got.backupPath, "/tmp/backup.sqlite3");
  assert.equal(got.destinationPath, "/tmp/encrypted.sqlite3");
  assert.equal(got.existingPassword, input.existingSourcePassword);
  assert.equal(got.newPassword, input.newPassword);
  assert.deepEqual(got.corrections, input.corrections);
  assert.deepEqual(got.schemaAdditions, input.schemaAdditions);
  assert.notStrictEqual(got.corrections, input.corrections);
  assert.notStrictEqual(got.schemaAdditions, input.schemaAdditions);
});

test("recovery does not need prior GUI approval or in-memory rehearsal", () => {
  const got = prepareReadOnlyRecoveryRequest({ ...required(),
    corrections: [], schemaAdditions: [],
    lastMigrationRehearsal: null, lastTemporaryEncryptedProof: null,
    experimentalCopyConfirmation: "CREATE EXPERIMENTAL ENCRYPTED COPY"
  });
  assert.deepEqual(got.corrections, []);
  assert.deepEqual(got.schemaAdditions, []);
  assert.equal("experimentalCopyConfirmation" in got, false);
  assert.equal("lastMigrationRehearsal" in got, false);
  assert.equal("approval" in got, false);
});

test("rejects absent paths and malformed selections before IPC", () => {
  for (const bad of [
    {sourcePath: ""}, {backupPath: " "}, {destinationPath: null},
    {corrections: null}, {corrections: [null]},
    {schemaAdditions: "index"}, {schemaAdditions: [""]}
  ]) {
    assert.throws(() => prepareReadOnlyRecoveryRequest({ ...required(), ...bad }));
  }
});

test("a missing or mismatched current SQLCipher password is rejected without exposing it", () => {
  for (const bad of [{newPassword:""}, {confirmation:"WrongCipherKey123!"}]) {
    const request = {...required(), ...bad};
    assert.throws(() => prepareReadOnlyRecoveryRequest(request), (error) =>
      (!request.newPassword || !error.message.includes(request.newPassword)) &&
      (!request.confirmation || !error.message.includes(request.confirmation)));
  }
});

test("restart can inspect only destination and receipt without disclosing credentials", () => {
  const raw = { ...required(), mode: "reservation_only" };
  const result = prepareReadOnlyRecoveryRequest(raw);
  assert.deepEqual(result, {
    sourcePath: "", backupPath: "", destinationPath: "/tmp/encrypted.sqlite3",
    existingPassword: "", newPassword: "", corrections: [], schemaAdditions: []
  });
  // Other form inputs must never be forwarded or accidentally used here.
  assert.equal(JSON.stringify(result).includes(raw.newPassword), false);
  assert.equal(JSON.stringify(result).includes(raw.existingSourcePassword), false);
  assert.equal(JSON.stringify(result).includes(raw.corrections[0].table), false);
});

test("reservation-only triage works after restart with only a target name", () => {
  const result = prepareReadOnlyRecoveryRequest({
    mode: "reservation_only", destinationPath: "/tmp/recovery.sqlite3",
    sourcePath: null, backupPath: null, newPassword: undefined,
    confirmation: undefined, corrections: null, schemaAdditions: null
  });
  assert.equal(result.destinationPath, "/tmp/recovery.sqlite3");
  assert.equal(result.sourcePath, "");
  assert.equal(result.newPassword, "");
});

test("unknown inspection modes and absent target fail closed", () => {
  assert.throws(() => prepareReadOnlyRecoveryRequest({ ...required(), mode: "unchecked" }),
    /Unbekannter Recovery-Prüfmodus/);
  for (const destinationPath of [undefined, null, "", "  "]) {
    assert.throws(() => prepareReadOnlyRecoveryRequest({ mode: "reservation_only", destinationPath }),
      /Zieldatei/);
  }
});

test("the wizard wires distinct provisional and full recovery readers to one read-only IPC", async () => {
  const { readFileSync } = await import("node:fs");
  const html = readFileSync(new URL("./index.html", import.meta.url), "utf8");
  const gui = readFileSync(new URL("./main.js", import.meta.url), "utf8");
  for (const id of ["inspect-interrupted-copy", "inspect-interrupted-copy-status-only"]) {
    assert.equal((html.match(new RegExp('id="' + id + '"', "g")) ?? []).length, 1);
  }
  assert.equal((gui.match(/invoke\("inspect_interrupted_encrypted_copy_status"/g) ?? []).length, 1);
  assert.match(gui, /briefRecoveryButton\.addEventListener\("click", \(\) => inspectRecovery\("reservation_only"\)\)/);
  assert.match(gui, /fullRecoveryButton\.addEventListener\("click", \(\) => inspectRecovery\("full"\)\)/);
  assert.match(html, /keine Passwörter/);
  assert.match(html, /keine Wiederherstellungsfreigabe/);
});
