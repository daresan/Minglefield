"""Owner and host isolation for the read-only evidence journal inventory."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy


class EvidenceJournalTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.store=AlphaAuthStore(self.root/"alpha.sqlite3")
        self.policy=HostCommitPolicy(IntegratedAlphaAdmission(self.store))
        with self.store._tx() as db:
            db.execute("INSERT INTO sec01_host_owners(host_id,owner_id) VALUES(?,?)",
                       ("host.one","user.owner"))
            db.execute("INSERT INTO sec01_host_owners(host_id,owner_id) VALUES(?,?)",
                       ("host.two","user.other"))
        for host,owner,project in (("host.one","user.owner","game.one"),
                                   ("host.two","user.other","game.two")):
            repo=self.root/project
            repo.mkdir()
            self.assertEqual(self.policy.create_game_project(
                host,owner,project,project,str(repo),str(repo/"stage"),str(repo/"output")
            ).state,"created")
        with self.store._tx() as db:
            for host,project,run in (("host.one","game.one","run.one"),
                                     ("host.two","game.two","run.two")):
                db.execute("""INSERT INTO alpha_game_installation_evidence
                    (host_id,project_id,integration_id,installer_run_id,evidence_json,recorded_at)
                    VALUES(?,?,?,?,?,?)""",
                    (host,project,"integration.example",run,'{"untrusted":"secret"}',
                     "2026-11-02T00:00:00Z"))

    def test_owner_and_host_isolation(self):
        self.assertIsNone(self.policy.inspect_game_installation_evidence(
            "host.one","user.other","game.one"))
        self.assertIsNone(self.policy.inspect_game_installation_evidence(
            "host.two","user.owner","game.two"))
        self.assertIsNone(self.policy.inspect_game_installation_evidence(
            "host.one","user.owner","game.two"))
        report=self.policy.inspect_game_installation_evidence(
            "host.one","user.owner","game.one")
        self.assertEqual([x["installer_run_id"] for x in report["records"]],["run.one"])
        self.assertEqual(report["records"][0]["verification_state"],"unknown")
        self.assertEqual(report["records"][0]["verification_reason"],"installer_origin_not_authenticated")
        self.assertNotIn("evidence_json",str(report))
        self.assertEqual(report["state"],"unverified")

    def test_forged_journal_claims_cannot_promote_verification(self):
        import json
        forged={"host_id":"host.one","project_id":"game.one",
                "integration_id":"integration.example",
                "release_source":{"provider":"github","repository":"example/repo"},
                "trusted_origin":True,
                "independent_checks":{"source_authorized":True,
                                      "release_identity_valid":True,
                                      "expected_digest":"a"*64,"observed_digest":"a"*64},
                "installed_files":{"file.bin":"a"*64}}
        with self.store._tx() as db:
            db.execute("""UPDATE alpha_game_installation_evidence
                SET evidence_json=? WHERE host_id=? AND project_id=?""",
                (json.dumps(forged),"host.one","game.one"))
        report=self.policy.inspect_game_installation_evidence(
            "host.one","user.owner","game.one")
        self.assertEqual(report["records"][0]["verification_state"],"unknown")
        self.assertEqual(report["records"][0]["verification_reason"],
                         "installer_origin_not_authenticated")
        self.assertNotIn("independent_checks",str(report))

    def test_empty_inventory_does_not_verify_installation(self):
        with self.store._tx() as db:
            db.execute("DELETE FROM alpha_game_installation_evidence WHERE host_id=?",
                       ("host.one",))
        report=self.policy.inspect_game_installation_evidence(
            "host.one","user.owner","game.one")
        self.assertEqual(report["records"],[])
        self.assertEqual(report["state"],"unverified")


if __name__=="__main__":
    unittest.main()
