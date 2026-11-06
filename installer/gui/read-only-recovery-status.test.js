import { test } from "node:test";
import assert from "node:assert/strict";
import { assessReadOnlyRecoveryStatus } from "./read-only-recovery-status.js";

const statuses = [
  "no_recorded_operation", "unrecorded_destination",
  "reserved_without_destination", "published_content_matches_untrusted_receipt",
  "manual_review_required"
];
const operationId = "0123456789abcdef0123456789abcdef";
const valid = (status) => ({
  status, operationId: ["reserved_without_destination", "published_content_matches_untrusted_receipt"].includes(status) ? operationId : null,
  automaticRetryPermitted: false,
  automaticDeletePermitted: false, installationEnabled: false
});

test("displays every read-only state without inferring recovery rights", () => {
  for (const status of statuses) {
    const assessed = assessReadOnlyRecoveryStatus(valid(status));
    assert.equal(assessed.status, status);
    assert.ok(assessed.message.length > 35);
    assert.equal(assessed.automaticRetryPermitted, false);
    assert.equal(assessed.automaticDeletePermitted, false);
    assert.equal(assessed.installationEnabled, false);
  }
});

test("rejects any attempt to turn a receipt into installation or deletion authority", () => {
  for (const invalid of [
    { automaticRetryPermitted: true },
    { automaticDeletePermitted: true },
    { installationEnabled: true },
    { status: "automatic_recovery_allowed" },
    { operationId: "untrusted id" },
    { operationId: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" }
  ]) {
    assert.throws(() => assessReadOnlyRecoveryStatus({
      ...valid("published_content_matches_untrusted_receipt"), ...invalid
    }));
  }
  assert.equal(
    assessReadOnlyRecoveryStatus(valid("published_content_matches_untrusted_receipt")).operationId,
    operationId
  );
});

test("rejects state and operation-ID contradictions without authorizing recovery", () => {
  for (const status of ["reserved_without_destination", "published_content_matches_untrusted_receipt"]) {
    assert.throws(() => assessReadOnlyRecoveryStatus({ ...valid(status), operationId: null }),
      /Inconsistent recovery status/);
    assert.throws(() => assessReadOnlyRecoveryStatus({ ...valid(status), operationId: undefined }),
      /Inconsistent recovery status/);
  }
  for (const status of ["no_recorded_operation", "unrecorded_destination"]) {
    assert.throws(() => assessReadOnlyRecoveryStatus({ ...valid(status), operationId }),
      /Inconsistent recovery status/);
  }
  // Corrupted or mismatched receipts may be classed for manual review
  // before or after an ID was read; neither case grants recovery rights.
  for (const id of [null, operationId]) {
    const assessed = assessReadOnlyRecoveryStatus({ ...valid("manual_review_required"), operationId: id });
    assert.equal(assessed.installationEnabled, false);
    assert.equal(assessed.automaticDeletePermitted, false);
    assert.equal(assessed.automaticRetryPermitted, false);
  }
});

test("rejects any future backend field without explicit schema review", () => {
  for (const field of [
    "executionEnabled", "migrationEnabled", "applicationInstallationEnabled",
    "hostProvisioningEnabled", "automaticResumePermitted", "automaticRollbackPermitted",
    "automaticCleanupPermitted", "receiptTrusted", "recoveryAuthorized",
    "arbitraryMetadata", "newUnreviewedPermission"
  ]) {
    for (const value of [true, "yes", false, null]) {
      assert.throws(
        () => assessReadOnlyRecoveryStatus({ ...valid("reserved_without_destination"), [field]: value }),
        /Unexpected recovery response field/
      );
    }
  }
  assert.equal(assessReadOnlyRecoveryStatus(valid("reserved_without_destination")).automaticRetryPermitted, false);
});

test("destination-only inspection cannot claim ciphertext fidelity or execution rights", () => {
  for (const status of [
    "no_recorded_operation", "unrecorded_destination",
    "reserved_without_destination", "manual_review_required"
  ]) {
    const assessed = assessReadOnlyRecoveryStatus(valid(status), { mode: "reservation_only" });
    assert.equal(assessed.status, status);
    assert.equal(assessed.automaticDeletePermitted, false);
    assert.equal(assessed.automaticRetryPermitted, false);
    assert.equal(assessed.installationEnabled, false);
  }
  assert.throws(() => assessReadOnlyRecoveryStatus(
    valid("published_content_matches_untrusted_receipt"), { mode: "reservation_only" }),
    /Content verification requires/);
  assert.throws(() => assessReadOnlyRecoveryStatus(valid("no_recorded_operation"), { mode: "unsafe" }),
    /Unknown recovery inspection scope/);
});
