"""Regression: legacy SQLite project attachment column is renamed without data loss."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy


class GameProjectAttachmentsMigrationTests(unittest.TestCase):
    def test_existing_sqlite_column_is_renamed_in_place_and_reopen_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = AlphaAuthStore(root / "alpha.sqlite3")
            repo, attachments, output = (str(root / name) for name in
                                         ("repo", "legacy-job-files", "output"))
            with store._tx() as db:
                db.execute("""CREATE TABLE alpha_game_projects(
                    project_id TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL, name TEXT NOT NULL,
                    repository_root TEXT NOT NULL, staging_root TEXT NOT NULL,
                    output_root TEXT NOT NULL, settings_revision INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(host_id,project_id))""")
                db.execute("""CREATE TABLE sec01_host_owners(
                    host_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL)""")
                db.execute("INSERT INTO sec01_host_owners(host_id,owner_id) VALUES(?,?)",
                           ("host.one", "user.owner"))
                db.execute("""INSERT INTO alpha_game_projects
                    (project_id,host_id,owner_id,name,repository_root,staging_root,
                     output_root,settings_revision) VALUES(?,?,?,?,?,?,?,?)""",
                    ("game.one", "host.one", "user.owner", "Legacy",
                     repo, attachments, output, 7))
            policy = HostCommitPolicy(IntegratedAlphaAdmission(store))
            with store._tx() as db:
                columns = {row[1] for row in db.execute(
                    "PRAGMA table_info(alpha_game_projects)")}
                row = db.execute("""SELECT job_attachments_root,settings_revision
                    FROM alpha_game_projects WHERE project_id=?""",
                    ("game.one",)).fetchone()
            self.assertIn("job_attachments_root", columns)
            self.assertNotIn("staging_root", columns)
            self.assertEqual(row, (attachments, 7))
            projects = policy.list_game_projects("host.one", "user.owner")
            self.assertEqual(projects[0]["job_attachments_root"], attachments)
            self.assertNotIn("staging_root", projects[0])
            HostCommitPolicy(IntegratedAlphaAdmission(store))
            self.assertFalse(Path(attachments).exists())


if __name__ == "__main__":
    unittest.main()
