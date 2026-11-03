"""Integration checks for DB-bound read-only cleanup preflight."""
import hashlib
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

    def test_unknown_operation_denied(self):
        self.assertEqual(self.inspect()["reason"], "operation_not_found")


if __name__ == "__main__":
    unittest.main()
