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
