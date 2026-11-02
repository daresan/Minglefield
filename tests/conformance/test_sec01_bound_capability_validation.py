"""SEC-01 composite validation / time-of-check gap tests; simulation only."""
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
import test_sec01_original_session_binding as session_fixture
from sec01_authority_fencing_sqlite import (
    AuthoritySnapshot, SQLiteAuthorityFence)
from sec01_bound_capability_validation import validate_bound_capability

class SEC01BoundCapabilityTests(unittest.TestCase):
    setUp = session_fixture.SEC01OriginalSessionBindingTests.setUp
    issue = session_fixture.SEC01OriginalSessionBindingTests.issue
    new_service = session_fixture.SEC01OriginalSessionBindingTests.new_service
    query = session_fixture.SEC01OriginalSessionBindingTests.query
    counts = session_fixture.SEC01OriginalSessionBindingTests.counts
    committed = session_fixture.SEC01OriginalSessionBindingTests.committed
    reference = session_fixture.SEC01OriginalSessionBindingTests.reference

    def prepare(self):
        intent = self.committed()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fence = SQLiteAuthorityFence(Path(tmp.name) / "fence.db")
        ids = ("session.1", intent.delegation_id, intent.agent_id, intent.user_id)
        fence.provision(ids)
        candidate = dict(asdict(intent), version=1, issuer="map.test",
                         audience=intent.adapter_id, executor_identity="worker.one",
                         issued_at=int(self.now) - 1, expires_at=int(self.now) + 50,
                         authority_identities=ids,
                         authority_epochs=fence.snapshot(ids).epochs,
                         original_session_reference=self.reference(intent))
        return intent, fence, candidate

    def check(self, intent, fence, candidate):
        return validate_bound_capability(
            candidate, intent=intent, authority=fence, database=self.db,
            issuer_secret=session_fixture.SECRET, now=self.now, expected_issuer="map.test",
            expected_audience=intent.adapter_id, expected_executor="worker.one")

    def test_valid_composite_is_not_admission(self):
        intent, fence, candidate = self.prepare()
        before = self.counts()
        result = self.check(intent, fence, candidate)
        self.assertEqual((result.valid, result.reason),
                         (True, "bound_shape_not_authenticated_or_admitted"))
        self.assertEqual(fence.accepted_count(), 0)
        self.assertEqual(self.counts(), before)

    def test_foreign_or_modified_session_reference_rejected(self):
        intent, fence, candidate = self.prepare()
        other = dict(candidate, original_session_reference="0" * 64)
        self.assertEqual(self.check(intent, fence, other).reason,
                         "original_session_mismatch")
        self.assertEqual(self.check(intent, fence, dict(candidate,
            original_session_reference=self.token)).reason,
            "invalid_session_reference")

    def test_original_session_revocation_after_validation_denies(self):
        intent, fence, candidate = self.prepare()
        self.assertTrue(self.check(intent, fence, candidate).valid)
        self.assertTrue(self.sessions.revoke(
            self.token, user_id="user.charlie", credential=self.credential))
        self.assertEqual(self.check(intent, fence, candidate).reason,
                         "original_session_unavailable")
        # The isolated fence does NOT share B2 session revocation state:
        # without an explicit synchronized invalidation, admission remains
        # possible. This demonstrates the missing real integration contract.
        snapshot = AuthoritySnapshot(candidate["authority_identities"],
                                     candidate["authority_epochs"])
        simulated = fence.accept(
            snapshot=snapshot, effect_key=intent.effect_idempotency_key,
            binding=(intent.job_id, intent.request_fingerprint))
        self.assertEqual(simulated.reason, "accepted_once")

    def test_simulated_epoch_invalidation_blocks_after_prior_validation(self):
        intent, fence, candidate = self.prepare()
        self.assertTrue(self.check(intent, fence, candidate).valid)
        fence.invalidate("session", candidate["authority_identities"][0])
        snapshot = AuthoritySnapshot(candidate["authority_identities"],
                                     candidate["authority_epochs"])
        rejected = fence.accept(
            snapshot=snapshot, effect_key=intent.effect_idempotency_key,
            binding=(intent.job_id, intent.request_fingerprint))
        self.assertEqual(rejected.reason, "authority_revoked_or_changed")
        self.assertEqual(fence.accepted_count(), 0)

    def test_unknown_fields_and_intent_tampering_rejected(self):
        intent, fence, candidate = self.prepare()
        self.assertEqual(self.check(intent, fence,
            dict(candidate, token_hash="secret")).reason, "invalid_shape")
        self.assertEqual(self.check(intent, fence,
            dict(candidate, target_id="target.other")).reason,
            "intent_binding_mismatch")

if __name__ == "__main__":
    unittest.main()
