"""Isolated staging tests; game repository must remain unchanged."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_executor import stage_installation_bytes


class IsolatedInstallationStagingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repository"
        self.staging = self.root / "installation-staging"
        self.repo.mkdir()
        self.staging.mkdir()
        self.files = {"assets/model.glb": b"model", "scripts/init.py": b"hello"}
        self.entries = [
            {"path": name, "size": len(data),
             "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in self.files.items()
        ]

    def stage(self, op="operation.one", loader=None, root=None):
        return stage_installation_bytes(
            self.staging if root is None else root, op, self.repo,
            self.entries, self.files.__getitem__ if loader is None else loader)

    def test_verified_bytes_only_enter_dedicated_staging(self):
        result = self.stage()
        self.assertEqual(result["state"], "staged")
        self.assertFalse(result["installation_allowed"])
        for name, data in self.files.items():
            self.assertEqual((self.staging / "operation.one" / name).read_bytes(), data)
            self.assertFalse((self.repo / name).exists())

    def test_existing_operation_is_not_overwritten(self):
        self.assertEqual(self.stage()["state"], "staged")
        self.assertEqual(self.stage()["reason"], "operation_staging_already_exists")
        self.assertEqual((self.staging / "operation.one" / "assets/model.glb").read_bytes(), b"model")

    def test_invalid_bytes_do_not_create_operation_directory(self):
        result = self.stage(loader=lambda name: b"tampered")
        self.assertEqual(result["reason"], "staged_bytes_mismatch")
        self.assertFalse((self.staging / "operation.one").exists())

    def test_repository_and_staging_must_be_separate(self):
        self.assertEqual(self.stage(root=self.repo)["reason"], "staging_repository_overlap")
        self.assertEqual(self.stage(op="../escape")["reason"], "invalid_operation_id")
        self.assertFalse((self.root / "escape").exists())

    def test_symlinked_staging_root_is_rejected(self):
        linked = self.root / "linked-staging"
        try:
            linked.symlink_to(self.staging, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks unavailable")
        self.assertEqual(self.stage(root=linked)["reason"],
                         "unsafe_installation_staging_root")
        self.assertFalse((self.staging / "operation.one").exists())

    def test_symlinked_staging_ancestor_is_rejected(self):
        linked = self.root / "linked-parent"
        try:
            linked.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks unavailable")
        self.assertEqual(self.stage(root=linked / "installation-staging")["reason"],
                         "unsafe_installation_staging_root")
        self.assertFalse((self.staging / "operation.one").exists())

    def test_symlinked_repository_ancestor_is_rejected(self):
        linked = self.root / "linked-parent"
        try:
            linked.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks unavailable")
        result = stage_installation_bytes(
            self.staging, "operation.one", linked / "repository",
            self.entries, self.files.__getitem__)
        self.assertEqual(result["reason"], "unsafe_repository_root")
        self.assertFalse((self.staging / "operation.one").exists())

    def test_existing_repository_destination_blocks_staging(self):
        (self.repo / "assets").mkdir()
        (self.repo / "assets/model.glb").write_bytes(b"original")
        self.assertEqual(self.stage()["reason"], "existing_destination_conflicts")
        self.assertFalse((self.staging / "operation.one").exists())
        self.assertEqual((self.repo / "assets/model.glb").read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
