import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy
from game_integration_install_journal import recovery_classification


class GameInstallJournalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = AlphaAuthStore(self.root / "db.sqlite3")
        self.policy = HostCommitPolicy(IntegratedAlphaAdmission(self.store))
        with self.store._tx() as db:
            db.execute("INSERT INTO sec01_host_owners(host_id,owner_id) VALUES(?,?)",
                       ("host.one", "user.owner"))
            db.execute("""INSERT INTO alpha_game_projects
                (host_id,owner_id,project_id,name,repository_root,staging_root,output_root,settings_revision)
                VALUES(?,?,?,?,?,?,?,?)""",
                ("host.one", "user.owner", "game.one", "Game",
                 str(self.root), str(self.root / "staging"),
                 str(self.root / "output"), 1))

    def test_preparation_is_persistent_and_idempotent(self):
        args = ("host.one", "user.owner", "game.one", "op.one", "a" * 64)
        first = self.policy.prepare_game_install_journal(*args)
        self.assertEqual(first["state"], "prepared")
        self.assertEqual(self.policy.prepare_game_install_journal(*args)["reason"],
                         "idempotent_replay")
        self.assertEqual(len(self.policy.game_install_journal_status(*args[:3])), 1)
        self.assertEqual(self.policy.game_install_journal_status(*args[:3])[0]["state"],
                         "prepared")

    def test_operation_reuse_with_other_digest_is_denied(self):
        args = ("host.one", "user.owner", "game.one", "op.one", "a" * 64)
        self.policy.prepare_game_install_journal(*args)
        self.assertEqual(self.policy.prepare_game_install_journal(
            *args[:4], "b" * 64)["reason"], "operation_id_conflict")

    def test_owner_and_project_scope(self):
        self.assertEqual(self.policy.prepare_game_install_journal(
            "host.one", "user.other", "game.one", "op.one", "a" * 64)["reason"],
            "not_host_owner")
        self.assertEqual(self.policy.prepare_game_install_journal(
            "host.one", "user.owner", "missing", "op.one", "a" * 64)["reason"],
            "project_not_found")
        self.assertIsNone(self.policy.game_install_journal_status(
            "host.one", "user.other", "game.one"))

    def test_recovery_is_conservative(self):
        for state in ("prepared", "applying", "rollback_required", "committed",
                      "rolled_back", "unexpected"):
            with self.subTest(state=state):
                self.assertFalse(recovery_classification(state)["auto_retry_allowed"])


if __name__ == "__main__":
    unittest.main()
