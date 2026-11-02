"""SEC-01 owner/requester/executor/host isolation; no real side effects."""
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from sec01_executor_host_admission_sim import MockExecutorAuthority

class ExecutorHostAdmissionTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.file=Path(temp.name)/"authority.db"
        self.auth=MockExecutorAuthority(self.file)
        self.auth.add_agent("agent.images","user.owner")
        self.auth.add_host("host.cloud","operator.cloud")
        self.auth.add_host("host.other","operator.other")
        self.auth.assign_host("agent.images","host.cloud")
        self.kw=dict(effect_key="effect.one",job_id="job.one",
                     fingerprint="fingerprint.one",requester_id="user.friend",
                     agent_id="agent.images",owner_id="user.owner",
                     executor_id="operator.cloud",host_id="host.cloud")

    def admit(self,**changes):
        return self.auth.admit(**(self.kw|changes))

    def test_foreign_agent_requires_grant_and_host_assignment(self):
        self.assertEqual(self.admit().reason,"requester_not_delegated")
        self.auth.grant("agent.images","user.friend")
        self.assertEqual(self.admit().reason,"admitted_once_no_effect")
        self.assertEqual(self.auth.admission_count(),1)

    def test_requester_cannot_select_arbitrary_host_or_executor(self):
        self.auth.grant("agent.images","user.friend")
        self.assertEqual(self.admit(host_id="host.other").reason,"executor_host_mismatch")
        self.assertEqual(self.admit(host_id="host.other",
                         executor_id="operator.other").reason,"host_not_authorized_for_agent")
        self.assertEqual(self.admit(executor_id="user.friend").reason,
                         "executor_host_mismatch")
        self.assertEqual(self.auth.admission_count(),0)

    def test_grant_revocation_blocks_new_admission(self):
        self.auth.grant("agent.images","user.friend")
        self.auth.grant("agent.images","user.friend",enabled=False)
        self.assertEqual(self.admit().reason,"requester_not_delegated")
        self.assertEqual(self.auth.admission_count(),0)

    def test_host_revocation_and_assignment_revocation(self):
        self.auth.grant("agent.images","user.friend")
        self.auth.assign_host("agent.images","host.cloud",enabled=False)
        self.assertEqual(self.admit().reason,"host_not_authorized_for_agent")
        self.auth.assign_host("agent.images","host.cloud")
        self.auth.set_active("host","host.cloud",False)
        self.assertEqual(self.admit().reason,"host_unavailable")
        self.assertEqual(self.auth.admission_count(),0)

    def test_agent_owner_mismatch_and_disabled_agent(self):
        self.auth.grant("agent.images","user.friend")
        self.assertEqual(self.admit(owner_id="user.friend").reason,
                         "agent_owner_or_state_mismatch")
        self.auth.set_active("agent","agent.images",False)
        self.assertEqual(self.admit().reason,"agent_owner_or_state_mismatch")

    def test_owner_can_request_without_foreign_grant(self):
        self.assertEqual(self.admit(requester_id="user.owner").reason,
                         "admitted_once_no_effect")

    def test_duplicate_and_cross_binding_deny_reuse(self):
        self.auth.grant("agent.images","user.friend")
        self.assertEqual(self.admit().reason,"admitted_once_no_effect")
        self.assertEqual(self.admit().reason,"already_admitted_no_new_effect")
        self.assertEqual(self.admit(job_id="job.other").reason,
                         "idempotency_binding_mismatch")
        self.assertEqual(self.auth.admission_count(),1)

    def test_concurrent_admission_and_revocation_serialized(self):
        self.auth.grant("agent.images","user.friend")
        def accept():
            return MockExecutorAuthority(self.file).admit(**self.kw).reason
        def revoke():
            MockExecutorAuthority(self.file).grant(
                "agent.images","user.friend",enabled=False)
        with ThreadPoolExecutor(max_workers=2) as pool:
            admitted=pool.submit(accept)
            revoked=pool.submit(revoke)
            result=admitted.result()
            revoked.result()
        self.assertIn(result,("admitted_once_no_effect","requester_not_delegated"))
        self.assertEqual(self.auth.admission_count(),
                         1 if result=="admitted_once_no_effect" else 0)
        self.assertEqual(self.admit(effect_key="effect.two").reason,
                         "requester_not_delegated")

if __name__=="__main__":
    unittest.main()
