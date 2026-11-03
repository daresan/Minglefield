"""Offline tests for the Alpha release prerequisite audit."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from check_alpha_release_readiness import check_release_tree


class ReleaseReadinessTests(unittest.TestCase):
    def test_currently_missing_license_and_package_are_blocked(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "# Minglefield\nLicense selection is pending.\n", encoding="utf-8"
            )
            result = check_release_tree(root)
            self.assertFalse(result["release_ready"])
            self.assertFalse(result["execution_enabled"])
            blocked = {c["check"] for c in result["checks"] if not c["passed"]}
            self.assertIn("LICENSE", blocked)
            self.assertIn("license_status", blocked)
            self.assertIn("runtime_dependency_lock", blocked)
            self.assertIn("packaged_launch_contract", blocked)

    def test_complete_synthetic_tree_meets_only_declared_prerequisites(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Minglefield\n", encoding="utf-8")
            (root / "LICENSE").write_text("Synthetic license fixture\n", encoding="utf-8")
            (root / "release").mkdir()
            (root / "release" / "runtime-dependencies.lock").write_text(
                "fixture\n", encoding="utf-8"
            )
            (root / "release" / "alpha-launch-contract.json").write_text(
                '{"fixture":true}\n', encoding="utf-8"
            )
            result = check_release_tree(root)
            self.assertTrue(result["release_ready"])
            self.assertFalse(result["execution_enabled"])

    def test_empty_license_is_blocked(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Minglefield\n", encoding="utf-8")
            (root / "LICENSE").write_text("  \n", encoding="utf-8")
            result = check_release_tree(root)
            self.assertFalse(next(c for c in result["checks"] if c["check"] == "LICENSE")["passed"])


if __name__ == "__main__":
    unittest.main()
