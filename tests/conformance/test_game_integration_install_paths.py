import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_paths import inspect_installation_paths


class InstallationPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "game"
        self.root.mkdir()

    def inspect(self, paths):
        return inspect_installation_paths(self.root, paths)

    def test_valid_new_destinations_are_read_only(self):
        result = self.inspect(["assets/hero.glb", "scripts/entry.py"])
        self.assertEqual(result["state"], "ready_for_staging")
        self.assertFalse(result["mutation_performed"])
        self.assertFalse((self.root / "assets").exists())

    def test_traversal_absolute_windows_and_reserved_names_rejected(self):
        for path in ("../escape", "assets/../escape", "/tmp/file", "C:/escape",
                     "assets\\escape", "assets//hero", "assets/./hero",
                     "assets/CON.txt", "aux", "assets/hero.", "a:b"):
            with self.subTest(path=path):
                self.assertEqual(self.inspect([path])["reason"],
                                 "invalid_destination_path")

    def test_case_insensitive_duplicates_and_parent_file_overlap(self):
        self.assertEqual(self.inspect(["A/file", "a/FILE"])["reason"],
                         "duplicate_destination_path")
        self.assertEqual(self.inspect(["assets", "assets/hero"])["reason"],
                         "overlapping_destination_paths")

    def test_existing_file_is_conflict_without_modification(self):
        existing = self.root / "hero.glb"
        existing.write_bytes(b"original")
        result = self.inspect(["hero.glb"])
        self.assertEqual(result["reason"], "existing_destination_conflicts")
        self.assertEqual(result["conflicting_paths"], ["hero.glb"])
        self.assertEqual(existing.read_bytes(), b"original")

    def test_symlink_components_are_rejected(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        try:
            (self.root / "linked").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        self.assertEqual(self.inspect(["linked/evil.txt"])["reason"],
                         "symlink_in_destination")
        self.assertFalse((outside / "evil.txt").exists())

    def test_missing_or_unsafe_repository_is_denied(self):
        self.assertEqual(inspect_installation_paths(self.root / "missing", ["x"])["reason"],
                         "unsafe_repository_root")
        self.assertEqual(self.inspect([])["reason"], "invalid_destination_path")


if __name__ == "__main__":
    unittest.main()
