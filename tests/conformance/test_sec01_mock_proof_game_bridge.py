"""SEC-01 isolated mock proof + game receipt integration negative tests."""
import copy
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from sec01_mock_admission_proof import issue_mock_proof
from sec01_mock_game_adapter import MockTransactionalGame
from sec01_mock_proof_game_bridge import apply_mock_proof

SECRET=b"simulation-only-issuer-key-000000000000"
PAYLOAD=dict(version=1,issuer="map.mock",audience="game.one",
             job_id="job.one",request_fingerprint="f"*64,effect_key="effect.one",
             executor="worker.one",issued_at=1000,expires_at=1100,nonce="nonce.one")


class ProofGameBridgeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.game=MockTransactionalGame(Path(tmp.name)/"game.db")
        self.proof=issue_mock_proof(PAYLOAD,issuer_secret=SECRET)

    def apply(self, proof=None, **changes):
        args=dict(game=self.game, proof=self.proof if proof is None else proof,
                  verifier_secret=SECRET,issuer="map.mock",audience="game.one",
                  executor="worker.one",job_id="job.one",fingerprint="f"*64,
                  effect_key="effect.one",now=1050)
        return apply_mock_proof(**(args|changes))

    def provision(self):
        self.game.install_trusted_fixture_receipt(
            effect_key="effect.one",binding="f"*64,audience="game.one")

    def test_authenticated_proof_alone_is_not_admission(self):
        self.assertEqual(self.apply().reason,"missing_admission_receipt")
        self.assertEqual(self.game.effect_count(),0)

    def test_preinstalled_receipt_and_proof_apply_once(self):
        self.provision()
        self.assertEqual(self.apply().state,"applied_mock")
        self.assertEqual(self.apply().reason,"historical_mock_effect_only")
        self.assertEqual(self.game.effect_count(),1)

    def test_modified_proof_and_wrong_audience_fail(self):
        self.provision()
        tampered=copy.deepcopy(self.proof)
        tampered["payload"]["nonce"]="other"
        self.assertEqual(self.apply(proof=tampered).reason,"invalid_mac")
        self.assertEqual(self.apply(audience="game.other").reason,"binding_mismatch")
        self.assertEqual(self.apply(now=1100).reason,"expired")
        self.assertEqual(self.game.effect_count(),0)

    def test_changed_fixture_binding_denies_even_signed_proof(self):
        self.game.install_trusted_fixture_receipt(
            effect_key="effect.one",binding="different",audience="game.one")
        self.assertEqual(self.apply().reason,"receipt_binding_mismatch")
        self.assertEqual(self.game.effect_count(),0)

    def test_concurrent_proofs_cause_only_one_mock_application(self):
        self.provision()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _: self.apply().state,(0,1)))
        self.assertEqual(sorted(results),["applied_mock","duplicate"])
        self.assertEqual(self.game.effect_count(),1)

if __name__=="__main__":
    unittest.main()
