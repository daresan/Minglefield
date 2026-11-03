import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy
from game_integration_install_journal import recovery_classification, inspect_journal_transition


class InstallJournalTransitionTests(unittest.TestCase):
    def test_authorized_verified_forward_transitions(self):
        for before, after in (
                ("prepared", "applying"), ("applying", "committed"),
                ("applying", "rollback_required"),
                ("rollback_required", "rolled_back"),
                ("rollback_required", "manual_recovery_required"),
                ("manual_recovery_required", "rolled_back"),
                ("prepared", "cancelled")):
            with self.subTest(before=before, after=after):
                result = inspect_journal_transition(
                    before, after, owner_authorized=True, plan_verified=True)
                self.assertEqual(result["state"], "transition_permitted")
                self.assertFalse(result["mutation_performed"])

    def test_no_unauthorized_or_unverified_activation(self):
        for before, after in (("prepared", "applying"), ("applying", "committed")):
            self.assertEqual(inspect_journal_transition(
                before, after, owner_authorized=True)["reason"],
                "verified_plan_required")
            self.assertEqual(inspect_journal_transition(
                before, after, plan_verified=True)["reason"],
                "owner_authorization_required")

    def test_no_replay_skips_or_terminal_state_mutation(self):
        for before, after in (
                ("prepared", "committed"), ("prepared", "rolled_back"),
                ("committed", "applying"), ("cancelled", "applying"),
                ("rolled_back", "committed"), ("unknown", "applying")):
            with self.subTest(before=before, after=after):
                self.assertEqual(inspect_journal_transition(
                    before, after, owner_authorized=True,
                    plan_verified=True)["state"], "blocked")


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

    def test_persistent_transition_cas_and_recovery(self):
        args = ("host.one", "user.owner", "game.one", "op.transition", "a" * 64)
        self.assertEqual(self.policy.prepare_game_install_journal(*args)["state"],
                         "prepared")
        transition = lambda before, after, **kw: self.policy.record_game_install_transition(
            *args, before, after, **kw)
        self.assertEqual(transition("prepared", "applying",
                                    plan_verified=True)["reason"],
                         "trusted_executor_required")
        self.assertEqual(transition("prepared", "applying",
                                    executor_authorized=True)["reason"],
                         "verified_plan_required")
        self.assertEqual(transition("prepared", "applying",
                                    executor_authorized=True,
                                    plan_verified=True)["state"], "applying")
        self.assertEqual(transition("prepared", "applying",
                                    executor_authorized=True,
                                    plan_verified=True)["reason"],
                         "journal_state_conflict")
        self.assertEqual(self.policy.game_install_journal_status(*args[:3])[0]["state"],
                         "applying")
        self.assertEqual(transition("applying", "rollback_required",
                                    executor_authorized=True)["state"],
                         "rollback_required")
        self.assertEqual(transition("rollback_required", "manual_recovery_required",
                                    executor_authorized=True)["state"],
                         "manual_recovery_required")
        self.assertEqual(transition("manual_recovery_required", "rolled_back",
                                    executor_authorized=True)["state"], "rolled_back")
        self.assertEqual(transition("rolled_back", "applying",
                                    executor_authorized=True,
                                    plan_verified=True)["reason"],
                         "invalid_journal_transition")

    def test_transition_rejects_wrong_owner_or_plan(self):
        args = ("host.one", "user.owner", "game.one", "op.scope", "a" * 64)
        self.policy.prepare_game_install_journal(*args)
        for bad in (
                ("host.one", "user.other", "game.one", "op.scope", "a" * 64),
                ("host.one", "user.owner", "game.one", "op.scope", "b" * 64),
                ("host.one", "user.owner", "game.one", "missing", "a" * 64)):
            result = self.policy.record_game_install_transition(
                *bad, "prepared", "applying",
                executor_authorized=True, plan_verified=True)
            self.assertEqual(result["state"], "denied")
        self.assertEqual(self.policy.game_install_journal_status(*args[:3])[0]["state"],
                         "prepared")

    def test_restart_inspection_never_replays_interrupted_install(self):
        args = ("host.one", "user.owner", "game.one", "op.crash", "a" * 64)
        self.assertEqual(self.policy.prepare_game_install_journal(*args)["state"],
                         "prepared")
        self.assertEqual(self.policy.record_game_install_transition(
            *args, "prepared", "applying", executor_authorized=True,
            plan_verified=True)["state"], "applying")
        # Reconstruct the policy using the same persisted database, as after restart.
        restarted = HostCommitPolicy(IntegratedAlphaAdmission(self.store))
        status = restarted.game_install_journal_status(*args[:3])
        self.assertEqual(len(status), 1)
        self.assertEqual(status[0]["state"], "applying")
        self.assertEqual(status[0]["recovery"]["state"],
                         "manual_recovery_required")
        self.assertFalse(status[0]["recovery"]["auto_retry_allowed"])
        self.assertEqual(restarted.prepare_game_install_journal(
            *args[:3], "op.second", "b" * 64)["reason"],
            "project_install_operation_pending")
        self.assertEqual(restarted.cancel_prepared_game_install(*args)["reason"],
                         "operation_not_cancellable")
        self.assertEqual(restarted.game_install_journal_status(
            *args[:3])[0]["state"], "applying")

    def test_rollback_required_is_never_automatically_committed(self):
        args = ("host.one", "user.owner", "game.one", "op.rollback", "a" * 64)
        self.policy.prepare_game_install_journal(*args)
        for before, after in (("prepared", "applying"),
                              ("applying", "rollback_required")):
            self.assertEqual(self.policy.record_game_install_transition(
                *args, before, after, executor_authorized=True,
                plan_verified=True)["state"], after)
        restarted = HostCommitPolicy(IntegratedAlphaAdmission(self.store))
        entry = restarted.game_install_journal_status(*args[:3])[0]
        self.assertEqual(entry["recovery"]["state"], "manual_recovery_required")
        self.assertFalse(entry["recovery"]["auto_retry_allowed"])
        self.assertEqual(restarted.record_game_install_transition(
            *args, "rollback_required", "committed",
            executor_authorized=True, plan_verified=True)["reason"],
            "invalid_journal_transition")

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
        with self.store._tx() as db:
            persisted = json.loads(db.execute("SELECT settings FROM sec01_host_settings WHERE host_id=?", ("host.one",)).fetchone()[0])
        self.assertEqual(persisted["job_attachments_root"], legacy_root)
        self.assertNotIn("staging_root", persisted)
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
