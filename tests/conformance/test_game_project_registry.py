"""Persistent game project registry, owner isolation and legacy compatibility."""
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy


class GameProjectRegistryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = AlphaAuthStore(self.root / "alpha.sqlite3")
        self.authority = IntegratedAlphaAdmission(self.store)
        self.policy = HostCommitPolicy(self.authority)
        with self.store._tx() as db:
            db.execute("INSERT INTO sec01_host_owners(host_id,owner_id) VALUES(?,?)",
                       ("host.one", "user.owner"))

    def test_persistence_and_owner_isolation(self):
        args = ("host.one", "user.owner", "game.one", "My Game",
                str(self.root / "game"), str(self.root / "stage"), str(self.root / "output"))
        self.assertEqual(self.policy.create_game_project(*args).state, "created")
        self.assertEqual(self.policy.create_game_project(*args).reason, "project_id_exists")
        self.assertIsNone(self.policy.list_game_projects("host.one", "user.other"))
        self.assertEqual(self.policy.create_game_project(
            "host.one", "user.other", "game.two", "Other",
            "/workspace/game", "/workspace/stage", "/workspace/output").state, "denied")
        restored = HostCommitPolicy(self.authority)
        projects = restored.list_game_projects("host.one", "user.owner")
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["project_id"], "game.one")
        self.assertEqual(projects[0]["settings_revision"], 1)

    def test_update_revision_and_owner_isolation(self):
        paths = tuple(str(self.root / part) for part in ("game", "stage", "output"))
        self.assertEqual(self.policy.create_game_project(
            "host.one", "user.owner", "game.one", "Original", *paths).state, "created")
        self.assertEqual(self.policy.update_game_project(
            "host.one", "user.other", "game.one", 1, "Unauthorized", *paths).state, "denied")
        self.assertEqual(self.policy.update_game_project(
            "host.one", "user.owner", "game.one", 1, "Updated", *paths).state, "saved")
        self.assertEqual(self.policy.update_game_project(
            "host.one", "user.owner", "game.one", 1, "Stale", *paths).reason, "revision_conflict")
        project = self.policy.list_game_projects("host.one", "user.owner")[0]
        self.assertEqual((project["name"], project["settings_revision"]), ("Updated", 2))
        self.assertEqual(self.policy.update_game_project(
            "host.one", "user.owner", "game.one", 2, "Invalid",
            "relative", paths[1], paths[2]).state, "denied")
        self.assertEqual(self.policy.list_game_projects("host.one", "user.owner")[0], project)

    def test_rejects_invalid_paths_and_preserves_host_settings(self):
        original = self.policy.host_settings("host.one", "user.owner")
        self.assertEqual(self.policy.create_game_project(
            "host.one", "user.owner", "game.one", "Test",
            "relative/path", str(self.root / "stage"), str(self.root / "output")).state, "denied")
        self.assertEqual(self.policy.host_settings("host.one", "user.owner"), original)
        self.assertEqual(self.policy.list_game_projects("host.one", "user.owner"), [])


if __name__ == "__main__":
    unittest.main()
