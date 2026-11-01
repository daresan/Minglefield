"""SEC-01 local proof issuer and online precommit fail-closed tests."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_remote_precommit_sim import LocalProofIssuer,online_precommit_check

KEY=b"sec01-local-test-key-not-for-any-real-executor-000"
PW="local-only-password-123"

class RemotePrecommitTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store=AlphaAuthStore(Path(temp.name)/"auth.db",clock=lambda:10000)
        self.owner=self.store.redeem(self.store.invite("user.owner"),password=PW)
        self.requester=self.store.redeem(self.store.invite("user.friend"),password=PW)
        self.store.create_agent("Bearer "+self.owner,"agent.images")
        self.authority=IntegratedAlphaAdmission(self.store)
        self.authority.provision_host("host.cloud","operator.cloud")
        self.authority.provision_host("host.other","operator.other")
        self.authority.assign_agent("agent.images","host.cloud")
        self.kw=dict(effect_key="effect.one",job_id="job.one",
                     fingerprint="fingerprint.one",agent_id="agent.images",
                     owner_id="user.owner",executor_id="operator.cloud",
                     host_id="host.cloud")
        self.issuer=LocalProofIssuer(self.authority,issuer_secret=KEY)

    def grant(self, revoke=False):
        return self.store.grant_agent("Bearer "+self.owner,
            agent_id="agent.images",grantee_user_id="user.friend",revoke=revoke)

    def issue(self,**overrides):
        return self.issuer.issue("Bearer "+self.requester,now=10000,**(self.kw|overrides))

    def check(self,proof,**overrides):
        kw=dict(authority=self.authority,proof=proof,verifier_secret=KEY,
                issuer="alpha.local",requester_id="user.friend",now=10010,
                **self.kw)
        return online_precommit_check(**(kw|overrides))

    def test_no_proof_without_real_alpha_grant(self):
        self.assertIsNone(self.issue())
        self.assertEqual(self.authority.admission_count(),0)

    def test_issue_only_after_new_integrated_admission(self):
        self.grant()
        proof=self.issue()
        self.assertIsNotNone(proof)
        self.assertEqual(self.check(proof).reason,"online_precheck_only_no_effect")
        self.assertIsNone(self.issue())
        self.assertEqual(self.authority.admission_count(),1)

    def test_bad_mac_wrong_host_executor_and_expiration(self):
        self.grant()
        proof=self.issue()
        modified=copy.deepcopy(proof)
        modified["payload"]["nonce"]="different"
        self.assertEqual(self.check(modified).reason,"invalid_mac")
        self.assertEqual(self.check(proof,host_id="host.other").reason,"binding_mismatch")
        self.assertEqual(self.check(proof,executor_id="operator.other").reason,
                         "binding_mismatch")
        self.assertEqual(self.check(proof,now=10030).reason,"expired")

    def test_grant_revoke_after_proof_denies_precommit(self):
        self.grant()
        proof=self.issue()
        self.grant(True)
        self.assertEqual(self.check(proof).reason,"grant_revoked")

    def test_host_revoke_and_placement_revoke_after_proof(self):
        self.grant()
        proof=self.issue()
        self.authority.assign_agent("agent.images","host.cloud",enabled=False)
        self.assertEqual(self.check(proof).reason,"host_assignment_revoked")
        self.authority.assign_agent("agent.images","host.cloud")
        self.authority.set_host_active("host.cloud",False)
        self.assertEqual(self.check(proof).reason,"host_revoked_or_mismatched")

    def test_owner_and_requester_disable_after_proof(self):
        self.grant()
        proof=self.issue()
        self.store.disable_user("user.friend")
        self.assertEqual(self.check(proof).reason,"requester_revoked")
        self.store.disable_user("user.owner")
        self.assertEqual(self.check(proof).reason,"agent_or_owner_revoked")

    def test_wrong_requester_cannot_rebind_proof(self):
        self.grant()
        proof=self.issue()
        self.assertEqual(self.check(proof,requester_id="user.other").reason,
                         "admission_not_found_or_mismatched")
        self.assertEqual(self.check(proof,job_id="job.other").reason,
                         "binding_mismatch")

    def test_missing_authority_fails_closed(self):
        self.grant()
        proof=self.issue()
        self.assertEqual(self.check(proof,authority=None).reason,
                         "authority_unavailable")

    def test_admission_record_not_manufactured_from_proof(self):
        self.grant()
        proof=self.issue()
        with self.store._tx() as db:
            db.execute("DELETE FROM alpha_sec01_admissions WHERE effect_key=?",
                       ("effect.one",))
        self.assertEqual(self.check(proof).reason,
                         "admission_not_found_or_mismatched")

    def test_online_check_does_not_apply_any_effect(self):
        self.grant()
        proof=self.issue()
        for _ in range(3):
            self.assertTrue(self.check(proof).allowed)
        self.assertEqual(self.authority.admission_count(),1)
        with self.store._tx() as db:
            count=db.execute("SELECT count(*) FROM alpha_jobs").fetchone()[0]
        self.assertEqual(count,0)

if __name__=="__main__":
    unittest.main()
