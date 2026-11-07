import { test } from "node:test";
import assert from "node:assert/strict";
import {
  EXPERIMENTAL_COPY_CONFIRMATION, validateExperimentalCopyRequest
} from "./experimental-copy-review.js";

const valid = () => ({
  sourcePath: "/data/source.sqlite3",
  destinationPath: "/data/migrated.sqlite3",
  backupPath: "/backup/separate-source.sqlite3",
  confirmation: EXPERIMENTAL_COPY_CONFIRMATION,
  verifiedRehearsal: {
    sourcePath: "/data/source.sqlite3", destinationPath: "/data/migrated.sqlite3",
    fullDataCopyVerified: true, sourcePreserved: true, verifiedChanges: 1
  },
  temporaryProof: {
    temporaryEncryptedCopyVerified: true, stagedValuesMatchCiphertext: true,
    temporaryFilesRemoved: true, destinationCreated: false, verifiedStagedChanges: 1
  },
  stagedCorrections: [{kind: "full_row"}],
  credentialsValid: true
});

test("direct encrypted copy needs no redundant developer trial proofs", () => {
  const input = valid();
  input.verifiedRehearsal = null;
  input.temporaryProof = null;
  assert.equal(validateExperimentalCopyRequest(input).destinationPath, input.destinationPath);
  for (const patch of [{sourcePath: ""}, {destinationPath: ""},
                      {stagedCorrections: null}, {credentialsValid: false}]) {
    assert.throws(() => validateExperimentalCopyRequest({...input, ...patch}));
  }
});
test("requires independent backup path and exact typed confirmation", () => {
  for (const change of [
    {backupPath: ""},
    {backupPath: "  "},
    {confirmation: true},
    {confirmation: "YES"},
    {confirmation: ""}
  ]) {
    assert.throws(() => validateExperimentalCopyRequest({...valid(), ...change}));
  }
});

test("stale trial proofs cannot prevent reuse with a distinct new target", () => {
  const input = {...valid(), destinationPath: "/fresh/target.sqlite3",
                 verifiedRehearsal: null, temporaryProof: {destinationCreated: true}};
  assert.equal(validateExperimentalCopyRequest(input).destinationPath, input.destinationPath);
});
