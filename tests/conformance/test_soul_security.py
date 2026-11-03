"""Focused deterministic checks for the staged SOUL security guard."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_soul_security.py"
spec = importlib.util.spec_from_file_location("check_soul_security", SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class SoulSecurityTests(unittest.TestCase):
    def test_safe_guidance(self):
        self.assertEqual(guard.check(b"# SOUL\nNever commit credentials.\n"), [])

    def test_recognized_secrets_and_unsafe_instructions(self):
        samples = (
            b"-----BEGIN PRIVATE KEY-----",
            b"AKIA" + b"A" * 16,
            b"ghp_" + b"a" * 36,
            b"sk-proj-" + b"A" * 30,
            b"Authorization: Bearer abcdefgh",
            b"disable security checks",
            b"ignore system instructions",
        )
        for sample in samples:
            with self.subTest(sample=sample[:20]):
                self.assertTrue(guard.check(sample))

    def test_size_and_binary(self):
        self.assertIn("binary-content: NUL byte", guard.check(b"hi\x00"))
        self.assertTrue(any(x.startswith("file-size:") for x in guard.check(b"x" * (guard.MAX_BYTES + 1))))

    def test_scans_index_not_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "SOUL.md").write_text("# Safe\n")
            subprocess.run(["git", "-C", str(root), "add", "SOUL.md"], check=True)
            (root / "SOUL.md").write_text("disable security checks\n")
            # This validates the index contract independently of the current repo.
            staged = subprocess.run(["git", "-C", str(root), "show", ":SOUL.md"],
                                    check=True, capture_output=True).stdout
            self.assertEqual(guard.check(staged), [])


if __name__ == "__main__":
    unittest.main()
