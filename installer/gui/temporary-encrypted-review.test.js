import test from "node:test";
import assert from "node:assert/strict";
import { assessTemporaryDiskCopy, selectTemporaryCopyCredentials } from "./temporary-encrypted-review.js";

const rehearsal = () => ({
  verifiedChanges: 0, verifiedRowCount: 143, verifiedTableCount: 27,
  verifiedSchemaEntryCount: 58
});
const valid = () => ({
  status: "temporary_encrypted_copy_verified",
  sourceIntegrityVerified: true, fullSourceCopyVerified: true,
  temporaryEncryptedCopyVerified: true, ciphertextHeaderVerified: true,
  wrongKeyRejected: true, fullDiskCopyVerified: true,
  verifiedStagedChanges: 0, stagedValuesMatchCiphertext: true,
  checkedRows: 143, checkedTables: 27, checkedSchemaEntries: 58,
  temporaryFilesRemoved: true, destinationCreated: false,
  encryptedDestinationVerified: false, executionEnabled: false
});
test("accepts a verified temporary SQLCipher copy without promoting migration execution", () => {
  assert.equal(assessTemporaryDiskCopy(valid(), rehearsal()).temporaryEncryptedCopyVerified, true);
  assert.equal(assessTemporaryDiskCopy(valid(), rehearsal()).executionEnabled, false);
});
test("rejects unfinished cleanup, partial checks, stale source or a persistent destination", () => {
  for (const [name, value] of [
    ["temporaryFilesRemoved", false], ["destinationCreated", true],
    ["encryptedDestinationVerified", true], ["executionEnabled", true],
    ["wrongKeyRejected", false], ["stagedValuesMatchCiphertext", false],
    ["verifiedStagedChanges", 1], ["checkedRows", 142],
    ["checkedTables", 26], ["checkedSchemaEntries", 57]
  ]) {
    assert.throws(() => assessTemporaryDiskCopy({...valid(), [name]: value}, rehearsal()));
  }
  assert.throws(() => assessTemporaryDiskCopy(valid(), {...rehearsal(), verifiedChanges: 1}));
  const edited = {...valid(), verifiedStagedChanges: 2};
  const reviewed = {...rehearsal(), verifiedChanges: 2};
  assert.equal(assessTemporaryDiskCopy(edited, reviewed).verifiedStagedChanges, 2);
});

test("reuses the existing Step 3 password and never includes confirmation in the request", () => {
  const credentials = selectTemporaryCopyCredentials({
    newPassword: "NewDestination9!", confirmation: "NewDestination9!",
    existingSourcePassword: "ExistingKey1!", rehearsalSourcePassword: ""
  });
  assert.deepEqual(credentials, { newPassword: "NewDestination9!", existingPassword: "ExistingKey1!" });
  const replacement = selectTemporaryCopyCredentials({
    newPassword: "NewDestination9!", confirmation: "NewDestination9!",
    existingSourcePassword: "ExistingKey1!", rehearsalSourcePassword: "ReenteredKey1!"
  });
  assert.equal(replacement.existingPassword, "ReenteredKey1!");
  assert.throws(() => selectTemporaryCopyCredentials({
    newPassword: "weak", confirmation: "weak",
    existingSourcePassword: "", rehearsalSourcePassword: ""
  }), /Step 3/);
  assert.throws(() => selectTemporaryCopyCredentials({
    newPassword: "NewDestination9!", confirmation: "Different9!",
    existingSourcePassword: "", rehearsalSourcePassword: ""
  }), /confirmation/);
});
