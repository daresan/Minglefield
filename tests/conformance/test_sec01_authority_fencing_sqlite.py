"""SEC-01 isolated multi-authority fencing regression tests."""
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))

from sec01_authority_fencing_sqlite import (
    KINDS, AuthoritySnapshot, SQLiteAuthorityFence)

IDS = ("session.1", "grant.1", "agent.1", "user.1")
BINDING = ("job.1", "game.feedback", "target.1", "fake.test", "digest.1")


class SEC01AuthorityFenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "authority.db"
        self.fence = SQLiteAuthorityFence(self.path)
        self.fence.provision(IDS)

    def test_each_revocation_before_admission_denies(self):
        for kind, identity in zip(KINDS, IDS):
            with self.subTest(kind=kind):
                # Independent DB per subtest prevents cross-authority contamination.
                with tempfile.TemporaryDirectory() as directory:
                    fence = SQLiteAuthorityFence(Path(directory) / "test.db")
                    fence.provision(IDS)
                    snapshot = fence.snapshot(IDS)
                    fence.invalidate(kind, identity)
                    result = fence.accept(
                        snapshot=snapshot, effect_key="effect.1", binding=BINDING)
                    self.assertEqual((result.accepted, result.reason),
                                     (False, "authority_revoked_or_changed"))
                    self.assertEqual(fence.accepted_count(), 0)

    def test_agent_policy_change_without_suspension_fences_old_snapshot(self):
        before = self.fence.snapshot(IDS)
        self.fence.invalidate("agent", IDS[2], revoke=False)
        self.assertEqual(self.fence.accept(
            snapshot=before, effect_key="effect.1", binding=BINDING).reason,
            "authority_revoked_or_changed")
        after = self.fence.snapshot(IDS)
        self.assertNotEqual(before.epochs, after.epochs)
        self.assertEqual(self.fence.accept(
            snapshot=after, effect_key="effect.2", binding=BINDING).reason,
            "accepted_once")

    def test_admitted_effect_survives_revocation_and_restart(self):
        before = self.fence.snapshot(IDS)
        self.assertEqual(self.fence.accept(
            snapshot=before, effect_key="effect.1", binding=BINDING).reason,
            "accepted_once")
        self.fence.invalidate("grant", IDS[1])
        restarted = SQLiteAuthorityFence(self.path)
        self.assertEqual(restarted.accept(
            snapshot=before, effect_key="effect.1", binding=BINDING).reason,
            "already_accepted_no_new_effect")
        self.assertEqual(restarted.accept(
            snapshot=before, effect_key="effect.2", binding=BINDING).reason,
            "authority_revoked_or_changed")
        self.assertEqual(restarted.accepted_count(), 1)

    def test_binding_and_identity_reuse_denied(self):
        snapshot = self.fence.snapshot(IDS)
        self.assertTrue(self.fence.accept(
            snapshot=snapshot, effect_key="effect.1", binding=BINDING).accepted)
        self.assertEqual(self.fence.accept(
            snapshot=snapshot, effect_key="effect.1",
            binding=BINDING[:-1] + ("different",)).reason,
            "idempotency_binding_mismatch")
        changed = AuthoritySnapshot(
            IDS[:-1] + ("user.other",), snapshot.epochs)
        self.assertEqual(self.fence.accept(
            snapshot=changed, effect_key="effect.1", binding=BINDING).reason,
            "idempotency_binding_mismatch")

    def test_unknown_and_revoked_authority_fail_closed(self):
        with self.assertRaises(ValueError):
            self.fence.snapshot(IDS[:-1] + ("unknown",))
        self.fence.invalidate("session", IDS[0])
        with self.assertRaises(ValueError):
            self.fence.snapshot(IDS)
        # Trusted provisioning cannot accidentally reactivate a revoked entry.
        self.fence.provision(IDS)
        with self.assertRaises(ValueError):
            self.fence.snapshot(IDS)

    def test_concurrent_revoke_and_accept_serialized_across_connections(self):
        before = self.fence.snapshot(IDS)
        start = Barrier(2)
        other = SQLiteAuthorityFence(self.path)
        def accept():
            start.wait()
            return self.fence.accept(
                snapshot=before, effect_key="effect.1", binding=BINDING)
        def revoke():
            start.wait()
            other.invalidate("principal", IDS[3])
        with ThreadPoolExecutor(max_workers=2) as pool:
            admitted = pool.submit(accept)
            revoked = pool.submit(revoke)
            result = admitted.result()
            revoked.result()
        self.assertIn(result.reason,
                      ("accepted_once", "authority_revoked_or_changed"))
        self.assertEqual(self.fence.accepted_count(), int(result.accepted))
        self.assertEqual(other.accept(
            snapshot=before, effect_key="effect.2", binding=BINDING).reason,
            "authority_revoked_or_changed")

    def test_invalid_snapshot_is_inert(self):
        good = self.fence.snapshot(IDS)
        bad = AuthoritySnapshot(good.identities, (True, 0, 0, 0))
        result = self.fence.accept(
            snapshot=bad, effect_key="effect.1", binding=BINDING)
        self.assertEqual(result.reason, "invalid_capability")
        self.assertEqual(self.fence.accepted_count(), 0)


if __name__ == "__main__":
    unittest.main()
