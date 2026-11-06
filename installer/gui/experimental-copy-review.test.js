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

test("requires exact reviewed source, output and verified stages", () => {
  assert.equal(validateExperimentalCopyRequest(valid()).destinationPath, "/data/migrated.sqlite3");
  for (const change of [
    {sourcePath: "/data/other.sqlite3"},
    {destinationPath: "/data/different.sqlite3"},
    {verifiedRehearsal: null},
    {temporaryProof: null},
    {stagedCorrections: []},
    {credentialsValid: false}
  ]) {
    assert.throws(() => validateExperimentalCopyRequest({...valid(), ...change}));
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

test("rejects unverified and mutated temporary proof", () => {
  const base = valid();
  assert.throws(() => validateExperimentalCopyRequest({
    ...base, temporaryProof: {...base.temporaryProof, destinationCreated: true}
  }));
  assert.throws(() => validateExperimentalCopyRequest({
    ...base, temporaryProof: {...base.temporaryProof, stagedValuesMatchCiphertext: false}
  }));
});
