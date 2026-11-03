"""Integration checks for DB-bound read-only cleanup preflight."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy
from game_integration_install_executor import stage_installation_bytes
from game_integration_install_staging import validate_staging_manifest


class JournalBoundCleanupTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve(strict=True)
        self.repo = self.root / "repo"
        self.staging = self.root / "install-staging"
        self.repo.mkdir()
        self.staging.mkdir()
        self.store = AlphaAuthStore(self.root / "db.sqlite3")
        self.policy = HostCommitPolicy(IntegratedAlphaAdmission(self.store))
        with self.store._tx() as db:
            db.execute("INSERT INTO sec01_host_owners(host_id,owner_id) VALUES(?,?)",
                       ("host.one", "owner.one"))
            db.execute("""INSERT INTO alpha_game_projects
                (host_id,owner_id,project_id,name,repository_root,
                 job_attachments_root,output_root,settings_revision)
                VALUES(?,?,?,?,?,?,?,?)""",
                ("host.one", "owner.one", "project.one", "Game",
                 str(self.repo), str(self.root / "attachments"),
                 str(self.root / "output"), 1))
        self.payload = b"test"
        self.entries = [{"path": "assets/test.bin", "size": len(self.payload),
                         "sha256": hashlib.sha256(self.payload).hexdigest()}]
        self.digest = validate_staging_manifest(self.entries)["plan_sha256"]
        self.args = ("host.one", "owner.one", "project.one", "op.one")

    def inspect(self, *args, entries=None):
        return self.policy.inspect_game_install_cleanup(
            *(args or self.args), self.entries if entries is None else entries,
            self.staging)

    def prepare_and_stage(self):
        self.assertEqual(self.policy.prepare_game_install_journal(
            *self.args, self.digest)["state"], "prepared")
        self.assertEqual(stage_installation_bytes(
            self.staging, "op.one", self.repo, self.entries,
            lambda _: self.payload)["state"], "staged")

    def test_cancelled_operation_eligible_but_never_deleted(self):
        self.prepare_and_stage()
        self.assertEqual(self.policy.cancel_prepared_game_install(
            *self.args, self.digest)["state"], "cancelled")
        result = self.inspect()
        self.assertEqual(result["state"], "eligible_snapshot")
        self.assertFalse(result["cleanup_allowed"])
        self.assertFalse(result["deletion_performed"])
        self.assertTrue((self.staging / "op.one" / "blob-000000").exists())

    def test_prepared_operation_denied(self):
        self.prepare_and_stage()
        self.assertEqual(self.inspect()["reason"], "journal_cleanup_not_authorized")

    def test_wrong_owner_and_project_denied(self):
        self.prepare_and_stage()
        self.assertEqual(self.inspect("host.one", "other", "project.one", "op.one")["reason"],
                         "not_host_owner")
        self.assertEqual(self.inspect("host.one", "owner.one", "other", "op.one")["reason"],
                         "project_not_found")

    def test_wrong_plan_denied(self):
        self.prepare_and_stage()
        self.policy.cancel_prepared_game_install(*self.args, self.digest)
        wrong = [dict(self.entries[0], sha256="0" * 64)]
        self.assertEqual(self.inspect(entries=wrong)["reason"],
                         "journal_cleanup_not_authorized")

    def test_backend_candidate_requires_terminal_journal(self):
        self.prepare_and_stage()
        pending = self.policy.inspect_game_install_cleanup_backend(
            *self.args, self.entries, self.staging)
        self.assertEqual(pending["state"], "blocked")
        self.assertEqual(pending["reason"], "journal_cleanup_not_authorized")
        self.assertFalse(pending["deletion_performed"])
        self.policy.cancel_prepared_game_install(*self.args, self.digest)
        result = self.policy.inspect_game_install_cleanup_backend(
            *self.args, self.entries, self.staging)
        self.assertFalse(result["cleanup_allowed"])
        self.assertFalse(result["deletion_performed"])
        self.assertTrue((self.staging / "op.one" / "manifest.json").exists())
        if sys.platform == "win32":
            self.assertEqual(result["reason"],
                             "windows_native_handle_backend_required")
        else:
            self.assertIn(result["state"], ("candidate_snapshot", "blocked"))

    def test_backend_rejects_wrong_owner_without_deletion(self):
        self.prepare_and_stage()
        self.policy.cancel_prepared_game_install(*self.args, self.digest)
        result = self.policy.inspect_game_install_cleanup_backend(
            "host.one", "other", "project.one", "op.one",
            self.entries, self.staging)
        self.assertEqual(result["reason"], "not_host_owner")
        self.assertFalse(result["deletion_performed"])
        self.assertTrue((self.staging / "op.one").exists())

    def test_posix_cleanup_requires_terminal_journal_and_owner(self):
        self.prepare_and_stage()
        def cleanup(*args):
            return self.policy.cleanup_game_install_staging_posix(
                *(args or self.args), self.entries, self.staging)
        pending = cleanup()
        self.assertEqual(pending["state"], "blocked")
        self.assertTrue((self.staging / "op.one" / "blob-000000").exists())
        self.policy.cancel_prepared_game_install(*self.args, self.digest)
        wrong_owner = cleanup("host.one", "other", "project.one", "op.one")
        self.assertEqual(wrong_owner["reason"], "not_host_owner")
        self.assertTrue((self.staging / "op.one").exists())
        result = cleanup()
        if os.name == "nt":
            self.assertEqual(result["reason"], "secure_cleanup_backend_unavailable")
            self.assertTrue((self.staging / "op.one").exists())
        else:
            self.assertEqual(result["state"], "removed")
            self.assertFalse((self.staging / "op.one").exists())
        self.assertTrue(self.repo.is_dir())

    def test_posix_cleanup_rejects_wrong_plan_after_cancellation(self):
        self.prepare_and_stage()
        self.policy.cancel_prepared_game_install(*self.args, self.digest)
        wrong = [dict(self.entries[0], sha256="0" * 64)]
        result = self.policy.cleanup_game_install_staging_posix(
            *self.args, wrong, self.staging)
        self.assertEqual(result["reason"], "journal_cleanup_not_authorized")
        self.assertTrue((self.staging / "op.one" / "manifest.json").exists())

    def test_unknown_operation_denied(self):
        self.assertEqual(self.inspect()["reason"], "operation_not_found")


if __name__ == "__main__":
    unittest.main()
