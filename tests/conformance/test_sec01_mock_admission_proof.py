"""Authenticated SEC-01 mock proof negative tests; no real admissions/effects."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from sec01_mock_admission_proof import issue_mock_proof, verify_mock_proof

SECRET=b"sec01-isolated-test-only-secret-0000000"
PAYLOAD=dict(version=1,issuer="map.mock",audience="game.one",
             job_id="job.1",request_fingerprint="f"*64,effect_key="effect.1",
             executor="worker.one",issued_at=1000,expires_at=1100,nonce="nonce.1")

class MockProofTests(unittest.TestCase):
    def check(self,proof,**changes):
        arguments=dict(verifier_secret=SECRET,issuer="map.mock",audience="game.one",
                       executor="worker.one",intent_job="job.1",
                       fingerprint="f"*64,effect_key="effect.1",now=1050)
        return verify_mock_proof(proof,**(arguments|changes))

    def test_mock_proof_positive_is_not_admission(self):
        signed=issue_mock_proof(PAYLOAD,issuer_secret=SECRET)
        self.assertEqual(self.check(signed).reason,
                         "mock_proof_valid_not_effect_authorization")

    def test_tampered_payload_and_mac_denied(self):
        signed=issue_mock_proof(PAYLOAD,issuer_secret=SECRET)
        for key,value in (("job_id","job.other"),("audience","game.other"),
                          ("effect_key","effect.other"),("executor","worker.other"),
                          ("request_fingerprint","a"*64)):
            with self.subTest(field=key):
                mutated=copy.deepcopy(signed)
                mutated["payload"][key]=value
                self.assertFalse(self.check(mutated).valid)
        mutated=copy.deepcopy(signed)
        mutated["payload"]["nonce"]="nonce.other"
        self.assertEqual(self.check(mutated).reason,"invalid_mac")

    def test_wrong_issuer_secret_context_and_expiry(self):
        signed=issue_mock_proof(PAYLOAD,issuer_secret=SECRET)
        self.assertEqual(self.check(signed,verifier_secret=b"x"*32).reason,"invalid_mac")
        self.assertEqual(self.check(signed,audience="game.other").reason,"binding_mismatch")
        self.assertEqual(self.check(signed,now=1100).reason,"expired")

    def test_unsigned_or_injected_fields_rejected(self):
        signed=issue_mock_proof(PAYLOAD,issuer_secret=SECRET)
        self.assertEqual(self.check({"payload":PAYLOAD}).reason,"invalid_shape")
        mutated=copy.deepcopy(signed)
        mutated["payload"]["session_token_hash"]="secret"
        self.assertEqual(self.check(mutated).reason,"invalid_shape")

if __name__=="__main__":
    unittest.main()
