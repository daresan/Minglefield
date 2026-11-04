"""Offline tests: never invoke real git, gh or network."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import subprocess
import unittest

from probe_git_tools import probe


class GitToolProbeTests(unittest.TestCase):
    def test_missing_tool(self):
        self.assertEqual(probe("git", which=lambda _: None)["state"], "missing")

    def test_version_without_auth_or_install(self):
        with TemporaryDirectory() as tmp:
            exe = Path(tmp) / "gh"
            exe.write_text("fixture", encoding="utf-8")
            calls = []

            def runner(argv, **kwargs):
                calls.append((argv, kwargs))
                return SimpleNamespace(returncode=0, stdout="gh version 2.99.0\n", stderr="")

            result = probe("gh", which=lambda _: str(exe), runner=runner)
            self.assertEqual(result["state"], "available")
            self.assertEqual(calls[0][0], [str(exe), "--version"])
            self.assertEqual(calls[0][1]["timeout"], 5)
            self.assertIs(calls[0][1]["stdin"], subprocess.DEVNULL)

    def test_failure_and_unexpected_output_fail_closed(self):
        with TemporaryDirectory() as tmp:
            exe = Path(tmp) / "git"
            exe.write_text("fixture", encoding="utf-8")
            for output in ("", "credential secret", "git login ok"):
                result = probe("git", which=lambda _: str(exe),
                               runner=lambda *a, **k: SimpleNamespace(
                                   returncode=0, stdout=output, stderr=""))
                self.assertEqual(result["state"], "unverified")
            result = probe("git", which=lambda _: str(exe),
                           runner=lambda *a, **k: SimpleNamespace(
                               returncode=1, stdout="git version 2.0", stderr=""))
            self.assertEqual(result["state"], "unverified")

    def test_relative_or_unsupported_tool(self):
        self.assertEqual(probe("git", which=lambda _: "git")["state"], "unverified")
        with self.assertRaises(ValueError):
            probe("bash")


if __name__ == "__main__":
    unittest.main()
