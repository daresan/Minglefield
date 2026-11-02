import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from game_integration_evidence import evaluate_evidence

A="a"*64
B="b"*64


class IntegrationEvidenceTests(unittest.TestCase):
    def test_declaration_is_not_verification(self):
        self.assertEqual(evaluate_evidence(declared=True)["state"],"declared")
        self.assertEqual(evaluate_evidence()["state"],"unknown")
        self.assertEqual(evaluate_evidence(declared=True,observed_digest=A)["state"],"declared")

    def test_requires_all_independent_checks(self):
        checks=dict(source_authorized=True,release_identity_valid=True,
                    expected_digest=A,observed_digest=A)
        self.assertEqual(evaluate_evidence(**checks)["state"],"integrity_verified")
        self.assertEqual(evaluate_evidence(**checks,installation_matches=True)["state"],"installation_verified")
        for key in checks:
            partial=dict(checks)
            del partial[key]
            with self.subTest(missing=key):
                self.assertEqual(evaluate_evidence(**partial)["state"],"unknown")

    def test_mismatches_fail_closed(self):
        checks=dict(source_authorized=True,release_identity_valid=True,
                    expected_digest=A,observed_digest=A)
        for change in ({"source_authorized":False},{"release_identity_valid":False},
                       {"installation_matches":False},{"observed_digest":B},
                       {"expected_digest":"bad"},{"observed_digest":"bad"}):
            with self.subTest(change=change):
                self.assertEqual(evaluate_evidence(**dict(checks,**change))["state"],"invalid")

    def test_installation_claim_without_integrity_is_insufficient(self):
        self.assertEqual(evaluate_evidence(installation_matches=True)["state"],"unknown")


if __name__=="__main__":
    unittest.main()
