"""Integrated admission: real Alpha tables + host state in one transaction."""
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission

PASSWORD="local-test-password-123"

class IntegratedAdmissionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file=Path(tmp.name)/"alpha.db"
        self.now=10000
        self.store=AlphaAuthStore(self.file,clock=lambda:self.now)
        self.owner=self.store.redeem(
            self.store.invite("user.owner"),password=PASSWORD)
        self.friend=self.store.redeem(
            self.store.invite("user.friend"),password=PASSWORD)
        self.assertEqual(self.store.create_agent(
            "Bearer "+self.owner,"agent.images")[0],201)
        self.service=IntegratedAlphaAdmission(self.store)
        self.service.provision_host("host.cloud","operator.cloud")
        self.service.provision_host("host.other","operator.other")
        self.service.assign_agent("agent.images","host.cloud")
        self.kw=dict(effect_key="effect.one",job_id="job.one",
                     fingerprint="fingerprint.one",agent_id="agent.images",
                     owner_id="user.owner",host_id="host.cloud",
                     executor_id="operator.cloud")

    def admit(self,token=None,**changes):
        return self.service.admit("Bearer "+(token or self.friend),
                                  **(self.kw|changes))

    def grant(self,revoke=False):
        return self.store.grant_agent("Bearer "+self.owner,
            agent_id="agent.images",grantee_user_id="user.friend",revoke=revoke)

    def test_real_alpha_grant_required(self):
        self.assertEqual(self.admit().reason,"requester_not_delegated")
        self.assertEqual(self.grant()[0],200)
        self.assertEqual(self.admit().reason,"admitted_once_no_effect")
        self.assertEqual(self.service.admission_count(),1)

    def test_real_alpha_revoke_blocks_new_admission(self):
        self.grant()
        self.grant(True)
        self.assertEqual(self.admit().reason,"requester_not_delegated")
        self.assertEqual(self.service.admission_count(),0)

    def test_logout_and_expiration_block_admission(self):
        self.grant()
        self.store.revoke_session("Bearer "+self.friend)
        self.assertEqual(self.admit().reason,"session_invalid")
        fresh=self.store.login("user.friend",PASSWORD)
        self.assertIsNotNone(fresh)
        self.now+=901
        self.assertEqual(self.admit(token=fresh).reason,"session_invalid")
        self.assertEqual(self.service.admission_count(),0)

    def test_disabled_requester_owner_and_agent(self):
        self.grant()
        self.store.disable_user("user.owner")
        self.assertEqual(self.admit().reason,"agent_owner_or_state_mismatch")
        self.assertEqual(self.service.admission_count(),0)

    def test_disabled_requester_even_with_grant(self):
        self.grant()
        self.store.disable_user("user.friend")
        self.assertEqual(self.admit().reason,"session_invalid")

    def test_host_assignment_and_executor_authority(self):
        self.grant()
        self.assertEqual(self.admit(host_id="host.other",
            executor_id="operator.other").reason,"host_not_authorized_for_agent")
        self.assertEqual(self.admit(executor_id="user.friend").reason,
                         "executor_host_mismatch")
        self.service.assign_agent("agent.images","host.cloud",enabled=False)
        self.assertEqual(self.admit().reason,"host_not_authorized_for_agent")
        self.service.assign_agent("agent.images","host.cloud")
        self.service.set_host_active("host.cloud",False)
        self.assertEqual(self.admit().reason,"host_unavailable")
        self.assertEqual(self.service.admission_count(),0)

    def test_owner_does_not_require_friends_grant(self):
        self.assertEqual(self.admit(token=self.owner).reason,
                         "admitted_once_no_effect")

    def test_effect_key_is_bound_to_requester_and_host(self):
        self.grant()
        self.assertEqual(self.admit().reason,"admitted_once_no_effect")
        self.assertEqual(self.admit().reason,"already_admitted_no_new_effect")
        self.assertEqual(self.admit(job_id="job.changed").reason,
                         "idempotency_binding_mismatch")
        self.assertEqual(self.admit(token=self.owner).reason,
                         "idempotency_binding_mismatch")
        self.assertEqual(self.service.admission_count(),1)

    def test_revocation_race_is_serialized_in_shared_database(self):
        self.grant()
        def attempt():
            store=AlphaAuthStore(self.file,clock=lambda:self.now)
            return IntegratedAlphaAdmission(store).admit(
                "Bearer "+self.friend,**self.kw).reason
        def revoke():
            self.grant(True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            f=pool.submit(attempt)
            r=pool.submit(revoke)
            result=f.result()
            r.result()
        self.assertIn(result,("admitted_once_no_effect","requester_not_delegated"))
        self.assertEqual(self.service.admission_count(),
                         1 if result=="admitted_once_no_effect" else 0)
        self.assertEqual(self.admit(effect_key="effect.later").reason,
                         "requester_not_delegated")

    def test_agent_deactivation_blocks_issued_grant(self):
        self.grant()
        with self.store._tx() as db:
            db.execute("UPDATE alpha_agents SET disabled=1 WHERE agent_id=?",
                       ("agent.images",))
        self.assertEqual(self.admit().reason,"agent_owner_or_state_mismatch")
        self.assertEqual(self.service.admission_count(),0)

    def test_historical_admission_not_new_execution_after_revoke(self):
        self.grant()
        self.assertEqual(self.admit().reason,"admitted_once_no_effect")
        self.grant(True)
        self.assertEqual(self.admit().reason,"already_admitted_no_new_effect")
        self.assertEqual(self.admit(effect_key="effect.new").reason,
                         "requester_not_delegated")
        self.assertEqual(self.service.admission_count(),1)

    def test_no_host_placement_from_requester_grant_alone(self):
        self.grant()
        self.service.assign_agent("agent.images","host.cloud",enabled=False)
        self.assertEqual(self.admit().reason,"host_not_authorized_for_agent")

if __name__=="__main__":
    unittest.main()
