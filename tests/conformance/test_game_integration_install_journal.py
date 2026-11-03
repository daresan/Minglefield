import sys
import json
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
                (host_id,owner_id,project_id,name,repository_root,job_attachments_root,output_root,settings_revision)
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

    def test_pending_operation_blocks_second_plan_until_cancelled(self):
        first = ("host.one", "user.owner", "game.one", "op.one", "a" * 64)
        second = ("host.one", "user.owner", "game.one", "op.two", "b" * 64)
        self.assertEqual(self.policy.prepare_game_install_journal(*first)["state"],
                         "prepared")
        self.assertEqual(self.policy.prepare_game_install_journal(*second)["reason"],
                         "project_install_operation_pending")
        self.assertEqual(self.policy.cancel_prepared_game_install(*first)["state"],
                         "cancelled")
        self.assertEqual(self.policy.cancel_prepared_game_install(*first)["reason"],
                         "idempotent_replay")
        self.assertEqual(self.policy.prepare_game_install_journal(*second)["state"],
                         "prepared")
        self.assertEqual(self.policy.prepare_game_install_journal(*first)["state"],
                         "cancelled")

    def test_cancel_requires_matching_owner_and_plan_digest(self):
        args = ("host.one", "user.owner", "game.one", "op.one", "a" * 64)
        self.policy.prepare_game_install_journal(*args)
        self.assertEqual(self.policy.cancel_prepared_game_install(
            "host.one", "user.other", "game.one", "op.one", "a" * 64)["reason"],
            "not_host_owner")
        self.assertEqual(self.policy.cancel_prepared_game_install(
            *args[:4], "b" * 64)["reason"], "plan_digest_conflict")
        self.assertEqual(self.policy.game_install_journal_status(*args[:3])[0]["state"],
                         "prepared")

    def test_host_settings_persist_canonical_key_and_reject_conflicts(self):
        root = str(self.root / "jobattachments")
        result = self.policy.save_host_settings(
            "host.one", "user.owner",
            {"job_attachments_root": root, "output_root": ""})
        self.assertEqual(result.state, "saved")
        settings = self.policy.host_settings("host.one", "user.owner")
        self.assertEqual(settings["job_attachments_root"], root)
        self.assertNotIn("staging_root", settings)
        with self.store._tx() as db:
            saved = json.loads(db.execute("SELECT settings FROM sec01_host_settings WHERE host_id=?", ("host.one",)).fetchone()[0])
        self.assertEqual(saved["job_attachments_root"], root)
        self.assertNotIn("staging_root", saved)
        self.assertEqual(self.policy.save_host_settings(
            "host.one", "user.owner",
            {"staging_root": root, "job_attachments_root": str(self.root / "other"),
             "output_root": ""}).state, "denied")
        self.assertEqual(self.policy.host_settings(
            "host.one", "user.owner")["job_attachments_root"], root)

    def test_legacy_host_settings_remain_readable_without_filesystem_changes(self):
        legacy_root = str(self.root / "old-attachments")
        with self.store._tx() as db:
            db.execute("INSERT INTO sec01_host_settings(host_id,settings) VALUES(?,?)",
                       ("host.one", json.dumps({"staging_root": legacy_root,
                                                "output_root": ""})))
        settings = self.policy.host_settings("host.one", "user.owner")
        self.assertEqual(settings["job_attachments_root"], legacy_root)
        self.assertNotIn("staging_root", settings)
        self.assertFalse(Path(legacy_root).exists())

    def test_game_project_reports_job_attachments_alias_without_moving_files(self):
        projects = self.policy.list_game_projects("host.one", "user.owner")
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["job_attachments_root"], str(self.root / "staging"))
        self.assertNotIn("staging_root", projects[0])
        inspected = self.policy.inspect_game_project_paths(
            "host.one", "user.owner", "game.one")
        self.assertEqual(inspected["job_attachments_root"]["path"], str(self.root / "staging"))
        self.assertNotIn("staging_root", inspected)
        self.assertFalse((self.root / "staging").exists())

    def test_recovery_is_conservative(self):
        for state in ("prepared", "applying", "rollback_required", "committed",
                      "rolled_back", "unexpected"):
            with self.subTest(state=state):
                self.assertFalse(recovery_classification(state)["auto_retry_allowed"])


if __name__ == "__main__":
    unittest.main()
