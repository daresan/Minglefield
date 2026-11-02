"""SEC-01 ordering-contract simulation; no real external effects."""
import unittest
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))

from sec01_fencing_sim import SimulatedEffectBoundary


BINDING = ("job.1", "agent.1", "grant.1", "game.feedback",
           "target.1", "fake.test", "1", "sha256.example")


class SEC01FencingSimulationTests(unittest.TestCase):
    def test_revocation_before_acceptance_denies(self):
        boundary = SimulatedEffectBoundary()
        epoch = boundary.capability_epoch()
        boundary.revoke()
        result = boundary.accept(epoch=epoch, effect_key="effect.1", binding=BINDING)
        self.assertEqual((result.accepted, result.reason),
                         (False, "revoked_or_stale_epoch"))
        self.assertEqual(boundary.accepted_count(), 0)

    def test_acceptance_before_revocation_is_not_undone(self):
        boundary = SimulatedEffectBoundary()
        epoch = boundary.capability_epoch()
        result = boundary.accept(epoch=epoch, effect_key="effect.1", binding=BINDING)
        self.assertEqual((result.accepted, result.reason), (True, "accepted_once"))
        boundary.revoke()
        replay = boundary.accept(epoch=epoch, effect_key="effect.1", binding=BINDING)
        self.assertEqual((replay.accepted, replay.reason),
                         (True, "already_accepted_no_new_effect"))
        self.assertEqual(boundary.accepted_count(), 1)
        self.assertFalse(boundary.accept(
            epoch=epoch, effect_key="effect.2", binding=BINDING).accepted)

    def test_effect_key_cannot_be_rebound(self):
        boundary = SimulatedEffectBoundary()
        epoch = boundary.capability_epoch()
        self.assertTrue(boundary.accept(
            epoch=epoch, effect_key="effect.1", binding=BINDING).accepted)
        result = boundary.accept(
            epoch=epoch, effect_key="effect.1",
            binding=BINDING[:-1] + ("different-fingerprint",))
        self.assertEqual((result.accepted, result.reason),
                         (False, "idempotency_binding_mismatch"))
        self.assertEqual(boundary.accepted_count(), 1)

    def test_concurrent_revocation_and_acceptance_have_serial_order(self):
        for _ in range(20):
            boundary = SimulatedEffectBoundary()
            epoch = boundary.capability_epoch()
            start = Barrier(2)

            def accept():
                start.wait()
                return boundary.accept(epoch=epoch, effect_key="effect.1", binding=BINDING)

            def revoke():
                start.wait()
                boundary.revoke()

            with ThreadPoolExecutor(max_workers=2) as pool:
                accepted = pool.submit(accept)
                revoked = pool.submit(revoke)
                result = accepted.result()
                revoked.result()
            self.assertIn(result.reason, ("accepted_once", "revoked_or_stale_epoch"))
            self.assertEqual(boundary.accepted_count(), int(result.accepted))
            self.assertFalse(boundary.accept(
                epoch=epoch, effect_key="effect.2", binding=BINDING).accepted)

    def test_invalid_capability_is_inert(self):
        boundary = SimulatedEffectBoundary()
        result = boundary.accept(epoch=True, effect_key="effect.1", binding=BINDING)
        self.assertEqual((result.accepted, result.reason),
                         (False, "invalid_capability"))
        self.assertEqual(boundary.accepted_count(), 0)


if __name__ == "__main__":
    unittest.main()
