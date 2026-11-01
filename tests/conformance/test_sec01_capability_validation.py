"""SEC-01 capability shape validation only; deliberately no authentication."""
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from sec01_b2_intent_projection import CommittedIntent
from sec01_authority_fencing_sqlite import SQLiteAuthorityFence
from sec01_capability_validation import validate_capability_shape

INTENT = CommittedIntent(
    contract_version=1, job_id="job.1", user_id="user.1", agent_id="agent.1",
    delegation_id="grant.1", action_type="game.feedback", scope="game.feedback",
    target_id="target.1", request_fingerprint="a" * 64,
    policy_revision=1, adapter_id="fake.test", adapter_version="1",
    effect_idempotency_key="effect." + "b" * 64)
IDS = ("session.1", "grant.1", "agent.1", "user.1")


class SEC01CapabilityValidationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.fence = SQLiteAuthorityFence(Path(temp.name) / "authority.db")
        self.fence.provision(IDS)
        self.candidate = dict(asdict(INTENT), version=1, issuer="map.test",
                              audience="fake.test", executor_identity="worker.one",
                              issued_at=1000, expires_at=1100,
                              authority_identities=IDS,
                              authority_epochs=self.fence.snapshot(IDS).epochs)

    def check(self, candidate=None, **changes):
        return validate_capability_shape(
            self.candidate if candidate is None else candidate,
            intent=INTENT, authority=self.fence, now=1050,
            expected_issuer="map.test", expected_audience="fake.test",
            expected_executor="worker.one", **changes)

    def test_valid_shape_explicitly_is_not_authenticated(self):
        result = self.check()
        self.assertEqual((result.valid, result.reason),
                         (True, "shape_valid_not_authenticated"))
        self.assertEqual(self.fence.accepted_count(), 0)

    def test_exact_fields_and_version_required(self):
        for changed in (dict(self.candidate, unexpected=1),
                        {k: v for k, v in self.candidate.items() if k != "scope"},
                        dict(self.candidate, version=True),
                        dict(self.candidate, version=2)):
            with self.subTest(changed=changed):
                self.assertFalse(self.check(changed).valid)

    def test_every_intent_field_is_bound(self):
        for key in asdict(INTENT):
            changed = dict(self.candidate)
            changed[key] = 2 if key in ("contract_version", "policy_revision") else "other"
            with self.subTest(key=key):
                self.assertEqual(self.check(changed).reason, "intent_binding_mismatch")

    def test_issuer_audience_and_executor_are_bound(self):
        for key in ("issuer", "audience", "executor_identity"):
            changed = dict(self.candidate, **{key: "other"})
            with self.subTest(key=key):
                self.assertEqual(self.check(changed).reason, "context_binding_mismatch")

    def test_lifetime_is_half_open_and_rejects_bool(self):
        for issued, expires in ((1050, 1050), (1060, 1100), (1000, 1050),
                                (True, 1100), (1000, False), (-1, 1100)):
            with self.subTest(issued=issued, expires=expires):
                changed = dict(self.candidate, issued_at=issued, expires_at=expires)
                self.assertEqual(self.check(changed).reason, "invalid_lifetime")

    def test_each_authority_revocation_or_epoch_change_denies(self):
        for kind, identity in zip(
                ("session", "grant", "agent", "principal"), IDS):
            with self.subTest(kind=kind):
                with tempfile.TemporaryDirectory() as temp:
                    fence = SQLiteAuthorityFence(Path(temp) / "authority.db")
                    fence.provision(IDS)
                    case = dict(self.candidate,
                                authority_epochs=fence.snapshot(IDS).epochs)
                    fence.invalidate(kind, identity, revoke=kind != "agent")
                    result = validate_capability_shape(
                        case, intent=INTENT, authority=fence, now=1050,
                        expected_issuer="map.test", expected_audience="fake.test",
                        expected_executor="worker.one")
                    self.assertFalse(result.valid)
                    self.assertIn(result.reason,
                                  ("authority_unavailable", "authority_epoch_changed"))

    def test_authority_identity_and_epoch_shapes_fail_closed(self):
        variants = (
            dict(self.candidate, authority_identities=IDS[:-1] + ("user.other",)),
            dict(self.candidate, authority_identities=list(IDS)),
            dict(self.candidate, authority_epochs=(True, 0, 0, 0)),
            dict(self.candidate, authority_epochs=(0, 0, 0)),
        )
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertFalse(self.check(variant).valid)
        self.assertEqual(self.fence.accepted_count(), 0)


if __name__ == "__main__":
    unittest.main()
