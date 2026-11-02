"""Persistent SEC-01 fencing simulation; no real adapter or external effects."""
import sys
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))

from sec01_fencing_sqlite import SQLiteEffectBoundary


BINDING = ("job.1", "agent.1", "grant.1", "game.feedback",
           "target.1", "fake.test", "1", "sha256.example")


class SEC01SQLiteFencingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "sec01.db"
        self.boundary = SQLiteEffectBoundary(self.path)

    def test_revoked_before_accept_deny_survives_restart(self):
        epoch = self.boundary.capability_epoch()
        self.boundary.revoke()
        restarted = SQLiteEffectBoundary(self.path)
        result = restarted.accept(epoch=epoch, effect_key="effect.1", binding=BINDING)
        self.assertEqual((result.accepted, result.reason),
                         (False, "revoked_or_stale_epoch"))
        self.assertEqual(restarted.capability_epoch(), epoch + 1)
        self.assertEqual(restarted.accepted_count(), 0)

    def test_accepted_before_revocation_remains_single_after_restart(self):
        epoch = self.boundary.capability_epoch()
        self.assertEqual(self.boundary.accept(
            epoch=epoch, effect_key="effect.1", binding=BINDING).reason,
            "accepted_once")
        self.boundary.revoke()
        restarted = SQLiteEffectBoundary(self.path)
        replay = restarted.accept(epoch=epoch, effect_key="effect.1", binding=BINDING)
        self.assertEqual((replay.accepted, replay.reason),
                         (True, "already_accepted_no_new_effect"))
        self.assertEqual(restarted.accepted_count(), 1)
        self.assertFalse(restarted.accept(
            epoch=epoch, effect_key="effect.2", binding=BINDING).accepted)

    def test_changed_binding_is_rejected_after_restart(self):
        epoch = self.boundary.capability_epoch()
        self.assertTrue(self.boundary.accept(
            epoch=epoch, effect_key="effect.1", binding=BINDING).accepted)
        restarted = SQLiteEffectBoundary(self.path)
        result = restarted.accept(epoch=epoch, effect_key="effect.1",
                                  binding=BINDING[:-1] + ("different",))
        self.assertEqual((result.accepted, result.reason),
                         (False, "idempotency_binding_mismatch"))
        self.assertEqual(restarted.accepted_count(), 1)

    def test_concurrent_accept_and_revoke_across_connections(self):
        for _ in range(12):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "race.db"
                left = SQLiteEffectBoundary(path)
                right = SQLiteEffectBoundary(path)
                epoch = left.capability_epoch()
                barrier = Barrier(2)

                def accept():
                    barrier.wait()
                    return left.accept(epoch=epoch, effect_key="effect.1",
                                       binding=BINDING)

                def revoke():
                    barrier.wait()
                    right.revoke()

                with ThreadPoolExecutor(max_workers=2) as pool:
                    a = pool.submit(accept)
                    r = pool.submit(revoke)
                    result = a.result()
                    r.result()
                self.assertIn(result.reason,
                              ("accepted_once", "revoked_or_stale_epoch"))
                self.assertEqual(SQLiteEffectBoundary(path).accepted_count(),
                                 int(result.accepted))
                self.assertFalse(right.accept(
                    epoch=epoch, effect_key="effect.2", binding=BINDING).accepted)

    def test_concurrent_same_key_is_accepted_once(self):
        epoch = self.boundary.capability_epoch()
        barrier = Barrier(2)
        def accept(_):
            barrier.wait()
            return SQLiteEffectBoundary(self.path).accept(
                epoch=epoch, effect_key="effect.1", binding=BINDING)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(accept, (0, 1)))
        self.assertEqual(sorted(r.reason for r in results),
                         ["accepted_once", "already_accepted_no_new_effect"])
        self.assertEqual(self.boundary.accepted_count(), 1)

    def test_invalid_epoch_and_binding_do_not_mutate(self):
        for epoch, binding in ((True, BINDING), (0, []), (-1, BINDING)):
            result = self.boundary.accept(
                epoch=epoch, effect_key="effect.1", binding=binding)
            self.assertEqual(result.reason, "invalid_capability")
        self.assertEqual(self.boundary.accepted_count(), 0)


if __name__ == "__main__":
    unittest.main()
