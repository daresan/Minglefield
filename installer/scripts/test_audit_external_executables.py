"""Tests for read-only external executable invocation audit."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from audit_external_executables import scan


class ExternalExecutableAuditTests(unittest.TestCase):
    def test_finds_literal_git_and_gh_without_running_them(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "server").mkdir()
            (root / "scripts").mkdir()
            (root / "server" / "demo.py").write_text(
                "import subprocess\n"
                "subprocess.run(['git', 'status'])\n"
                "subprocess.run(['gh', 'auth', 'status'])\n"
                "subprocess.run(['python', '--version'])\n",
                encoding="utf-8",
            )
            result = scan(root)
            self.assertEqual([x["tools"] for x in result["findings"]], [["git"], ["gh"]])
            self.assertFalse(result["executable_dependencies_verified"])
            self.assertEqual(result["errors"], [])

    def test_parse_failure_is_not_silent(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "server").mkdir()
            (root / "server" / "bad.py").write_text("def bad(:\n", encoding="utf-8")
            self.assertEqual(len(scan(root)["errors"]), 1)


if __name__ == "__main__":
    unittest.main()
