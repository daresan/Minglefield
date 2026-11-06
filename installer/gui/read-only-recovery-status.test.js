import { test } from "node:test";
import assert from "node:assert/strict";
import { assessReadOnlyRecoveryStatus } from "./read-only-recovery-status.js";

const statuses = [
  "no_recorded_operation", "unrecorded_destination",
  "reserved_without_destination", "published_content_matches_untrusted_receipt",
  "manual_review_required"
];
const valid = (status) => ({
  status, operationId: null, automaticRetryPermitted: false,
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
    assessReadOnlyRecoveryStatus({
      ...valid("published_content_matches_untrusted_receipt"),
      operationId: "0123456789abcdef0123456789abcdef"
    }).operationId,
    "0123456789abcdef0123456789abcdef"
  );
});
