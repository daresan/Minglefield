"""SEC-01 mock game receipts: transaction-only reference tests."""
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from sec01_mock_game_adapter import MockTransactionalGame


class MockGameAdapterTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "game.db"
        self.game = MockTransactionalGame(self.db)

    def test_without_receipt_no_mock_effect(self):
        outcome = self.game.apply(effect_key="effect.1",
                                  binding="fingerprint.1", audience="game.1")
        self.assertEqual(outcome.reason, "missing_admission_receipt")
        self.assertEqual(self.game.effect_count(), 0)

    def test_receipt_is_bound_to_adapter_and_intent(self):
        self.game.install_trusted_fixture_receipt(
            effect_key="effect.1", binding="fingerprint.1", audience="game.1")
        for binding, audience in (("changed", "game.1"),
                                  ("fingerprint.1", "other")):
            with self.subTest(binding=binding, audience=audience):
                result = self.game.apply(effect_key="effect.1",
                                         binding=binding, audience=audience)
                self.assertEqual(result.reason, "receipt_binding_mismatch")
        self.assertEqual(self.game.effect_count(), 0)

    def test_receipt_consumption_is_persistent_and_idempotent(self):
        self.game.install_trusted_fixture_receipt(
            effect_key="effect.1", binding="fingerprint.1", audience="game.1")
        first = self.game.apply(effect_key="effect.1",
                                binding="fingerprint.1", audience="game.1")
        self.assertEqual(first.state, "applied_mock")
        restarted = MockTransactionalGame(self.db)
        second = restarted.apply(effect_key="effect.1",
                                 binding="fingerprint.1", audience="game.1")
        self.assertEqual(second.state, "duplicate")
        self.assertEqual(restarted.effect_count(), 1)

    def test_parallel_same_receipt_is_consumed_once(self):
        self.game.install_trusted_fixture_receipt(
            effect_key="effect.1", binding="fingerprint.1", audience="game.1")
        def apply(_):
            return MockTransactionalGame(self.db).apply(
                effect_key="effect.1", binding="fingerprint.1",
                audience="game.1").state
        with ThreadPoolExecutor(max_workers=2) as pool:
            states = sorted(pool.map(apply, (0, 1)))
        self.assertEqual(states, ["applied_mock", "duplicate"])
        self.assertEqual(self.game.effect_count(), 1)

    def test_invalid_fields_do_not_mutate(self):
        result = self.game.apply(effect_key=True,
                                 binding="fingerprint.1", audience="game.1")
        self.assertEqual(result.reason, "invalid_binding")
        self.assertEqual(self.game.effect_count(), 0)


if __name__ == "__main__":
    unittest.main()
