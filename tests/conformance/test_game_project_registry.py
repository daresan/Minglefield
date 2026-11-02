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

    def test_git_profile_persistence_and_owner_isolation(self):
        profile = dict(profile_id="git.default", label="Local Git",
                       auth_method="local", git_executable="git",
                       author_name="Tester", author_email="tester@example.invalid")
        self.assertIsNone(self.policy.list_git_profiles("host.one", "user.other"))
        self.assertEqual(self.policy.save_git_profile(
            "host.one", "user.other", profile).reason, "not_host_owner")
        self.assertEqual(self.policy.save_git_profile(
            "host.one", "user.owner", profile).state, "saved")
        profile["auth_method"] = "ssh"
        self.assertEqual(self.policy.save_git_profile(
            "host.one", "user.owner", profile).state, "saved")
        restored = HostCommitPolicy(self.authority)
        profiles = restored.list_git_profiles("host.one", "user.owner")
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["auth_method"], "ssh")
        self.assertEqual(self.policy.save_git_profile(
            "host.one", "user.owner", dict(profile, auth_method="token")).state, "denied")

    def test_git_inspection_and_explicit_initialization(self):
        import shutil
        if not shutil.which("git"):
            self.skipTest("git executable unavailable")
        repo=self.root / "new-repo"
        repo.mkdir()
        self.assertEqual(self.policy.create_game_project(
            "host.one","user.owner","game.git","Git Game",
            str(repo),str(repo/"staging"),str(repo/"output")).state,"created")
        profile=dict(profile_id="git.local",label="Local",auth_method="local",
                     git_executable="git",author_name="Tester",
                     author_email="tester@example.invalid")
        self.assertEqual(self.policy.save_git_profile(
            "host.one","user.owner",profile).state,"saved")
        self.assertEqual(self.policy.inspect_game_git(
            "host.one","user.owner","game.git")["state"],"not_initialized")
        self.assertFalse((repo/".git").exists())
        self.assertEqual(self.policy.initialize_game_git(
            "host.one","user.other","game.git",1,"git.local")["state"],"denied")
        self.assertEqual(self.policy.initialize_game_git(
            "host.one","user.owner","game.git",2,"git.local")["reason"],"revision_conflict")
        self.assertEqual(self.policy.initialize_game_git(
            "host.one","user.owner","game.git",1,"git.local")["state"],"initialized")
        self.assertTrue((repo/".git").is_dir())
        self.assertEqual(self.policy.inspect_game_git(
            "host.one","user.owner","game.git")["state"],"initialized")
        self.assertEqual(self.policy.initialize_game_git(
            "host.one","user.owner","game.git",1,"git.local")["state"],"denied")

    def test_explicit_directory_preparation(self):
        repo=self.root / "repo"
        repo.mkdir()
        marker=repo / "keep.txt"
        marker.write_text("keep")
        stage=repo / "stage"
        output=repo / "output"
        self.assertEqual(self.policy.create_game_project(
            "host.one","user.owner","game.prepare","Prepare",
            str(repo),str(stage),str(output)).state,"created")
        self.assertEqual(self.policy.prepare_game_project_directories(
            "host.one","user.other","game.prepare",1)["reason"],"not_host_owner")
        self.assertEqual(self.policy.prepare_game_project_directories(
            "host.one","user.owner","game.prepare",2)["reason"],"revision_conflict")
        self.assertFalse(stage.exists())
        result=self.policy.prepare_game_project_directories(
            "host.one","user.owner","game.prepare",1)
        self.assertEqual(result["state"],"prepared")
        self.assertEqual(set(result["created"]),{str(stage),str(output)})
        self.assertTrue(stage.is_dir())
        self.assertTrue(output.is_dir())
        self.assertEqual(self.policy.prepare_game_project_directories(
            "host.one","user.owner","game.prepare",1)["created"],[])
        self.assertEqual(marker.read_text(),"keep")

    def test_directory_preparation_distinguishes_missing_repository(self):
        repo=self.root / "not_created"
        self.assertEqual(self.policy.create_game_project(
            "host.one","user.owner","game.missing","Missing",
            str(repo),str(repo/"staging"),str(repo/"output")).state,"created")
        result=self.policy.prepare_game_project_directories(
            "host.one","user.owner","game.missing",1)
        self.assertEqual(result["state"],"prepared")
        self.assertTrue(repo.is_dir())
        self.assertIn(str(repo),result["created"])
        self.assertTrue((repo/"staging").is_dir())
        self.assertTrue((repo/"output").is_dir())

    def test_prepare_gitignore_preserves_existing_and_is_idempotent(self):
        repo=self.root/"ignore_repo"
        repo.mkdir()
        ignore=repo/".gitignore"
        ignore.write_text("*.tmp\n",encoding="utf-8")
        stage=repo/"staging"
        output=repo/"output"
        self.assertEqual(self.policy.create_game_project(
            "host.one","user.owner","game.ignore","Ignore",
            str(repo),str(stage),str(output)).state,"created")
        first=self.policy.prepare_game_project_directories(
            "host.one","user.owner","game.ignore",1)
        self.assertEqual(first["gitignore"]["rules_added"],["/staging/","/output/"])
        self.assertEqual(ignore.read_text(encoding="utf-8"),
                         "*.tmp\n/staging/\n/output/\n")
        second=self.policy.prepare_game_project_directories(
            "host.one","user.owner","game.ignore",1)
        self.assertEqual(second["gitignore"]["rules_added"],[])
        self.assertEqual(ignore.read_text(encoding="utf-8"),
                         "*.tmp\n/staging/\n/output/\n")

    def test_prepare_gitignore_skips_external_asset_directories(self):
        repo=self.root/"external_repo"
        repo.mkdir()
        stage=self.root/"external_staging"
        output=self.root/"external_output"
        self.assertEqual(self.policy.create_game_project(
            "host.one","user.owner","game.external","External",
            str(repo),str(stage),str(output)).state,"created")
        result=self.policy.prepare_game_project_directories(
            "host.one","user.owner","game.external",1)
        self.assertEqual(result["state"],"prepared")
        self.assertFalse((repo/".gitignore").exists())

    def test_directory_preparation_rejects_unsafe_paths(self):
        repo=self.root / "repo"
        repo.mkdir()
        self.assertEqual(self.policy.create_game_project(
            "host.one","user.owner","game.unsafe","Unsafe",
            str(repo),str(repo),str(self.root / "output")).state,"created")
        result=self.policy.prepare_game_project_directories(
            "host.one","user.owner","game.unsafe",1)
        self.assertEqual(result["reason"],"unsafe_project_paths")
        self.assertFalse((self.root / "output").exists())

    def test_read_only_directory_inspection(self):
        repo = self.root / "repo"
        repo.mkdir()
        file_path = self.root / "not_a_directory"
        file_path.write_text("keep")
        stage = self.root / "missing_stage"
        self.assertEqual(self.policy.create_game_project(
            "host.one", "user.owner", "game.paths", "Paths",
            str(repo), str(stage), str(file_path)).state, "created")
        self.assertIsNone(self.policy.inspect_game_project_paths(
            "host.one", "user.other", "game.paths"))
        self.assertIsNone(self.policy.inspect_game_project_paths(
            "host.one", "user.owner", "missing.game"))
        result = self.policy.inspect_game_project_paths(
            "host.one", "user.owner", "game.paths")
        self.assertEqual(result["repository_root"]["state"], "directory")
        self.assertEqual(result["staging_root"]["state"], "missing")
        self.assertEqual(result["output_root"]["state"], "not_directory")
        self.assertFalse(stage.exists())
        self.assertEqual(file_path.read_text(), "keep")

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
