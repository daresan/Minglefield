"""Isolated staging tests; game repository must remain unchanged."""
import hashlib
import json
import os
import subprocess
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
        operation = self.staging / "operation.one"
        mapping = json.loads((operation / "manifest.json").read_text("utf-8"))
        self.assertEqual(mapping["plan_sha256"], result["plan_sha256"])
        self.assertEqual(result["layout"], "flat-v1")
        self.assertEqual(len(mapping["files"]), len(self.files))
        for entry in mapping["files"]:
            self.assertEqual((operation / entry["blob"]).read_bytes(),
                             self.files[entry["path"]])
            self.assertEqual(entry["sha256"],
                             hashlib.sha256(self.files[entry["path"]]).hexdigest())
            self.assertFalse((self.repo / entry["path"]).exists())
        self.assertEqual(sorted(p.name for p in operation.iterdir()),
                         ["blob-000000", "blob-000001", "manifest.json"])

    def test_existing_operation_is_not_overwritten(self):
        self.assertEqual(self.stage()["state"], "staged")
        self.assertEqual(self.stage()["reason"], "operation_staging_already_exists")
        self.assertEqual((self.staging / "operation.one" / "blob-000000").read_bytes(), b"model")

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

    def _junction(self, link, target):
        if os.name != "nt":
            self.skipTest("Windows junction-specific test")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True)
        if result.returncode:
            details = result.stderr.decode("utf-8", errors="replace").strip()
            self.skipTest("junction creation unavailable: " + details)
        self.assertTrue(link.exists())

    def test_junction_staging_root_is_rejected(self):
        link = self.root / "junction-staging"
        self._junction(link, self.staging)
        self.assertEqual(self.stage(root=link)["reason"],
                         "unsafe_installation_staging_root")
        self.assertFalse((self.staging / "operation.one").exists())

    def test_junction_staging_ancestor_is_rejected(self):
        link = self.root / "junction-parent"
        self._junction(link, self.root)
        self.assertEqual(self.stage(root=link / "installation-staging")["reason"],
                         "unsafe_installation_staging_root")
        self.assertFalse((self.staging / "operation.one").exists())

    def test_junction_repository_ancestor_is_rejected(self):
        link = self.root / "junction-parent"
        self._junction(link, self.root)
        result = stage_installation_bytes(
            self.staging, "operation.one", link / "repository",
            self.entries, self.files.__getitem__)
        self.assertEqual(result["reason"], "unsafe_repository_root")
        self.assertFalse((self.staging / "operation.one").exists())

    def test_junction_inside_repository_destination_is_rejected(self):
        external = self.root / "external"
        external.mkdir()
        self._junction(self.repo / "assets", external)
        self.assertEqual(self.stage()["reason"], "symlink_in_destination")
        self.assertFalse((external / "model.glb").exists())
        self.assertFalse((self.staging / "operation.one").exists())

    def test_existing_repository_destination_blocks_staging(self):
        (self.repo / "assets").mkdir()
        (self.repo / "assets/model.glb").write_bytes(b"original")
        self.assertEqual(self.stage()["reason"], "existing_destination_conflicts")
        self.assertFalse((self.staging / "operation.one").exists())
        self.assertEqual((self.repo / "assets/model.glb").read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
