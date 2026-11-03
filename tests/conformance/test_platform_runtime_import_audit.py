import tempfile
import unittest
from pathlib import Path

from scripts.platform_runtime_import_audit import audit


class RuntimeImportAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, source):
        p = self.root / name
        p.write_text(source, encoding="utf-8")
        return p

    def test_local_transitive_import_and_third_party(self):
        entry = self.write("main.py", "import os\nimport helper\n")
        self.write("helper.py", "import json\nimport imaginary_external_pkg\n")
        report = audit(entry, self.root)
        self.assertEqual(report["local_modules"], ["helper.py", "main.py"])
        self.assertEqual(report["third_party_candidates"], ["imaginary_external_pkg"])

    def test_nested_import_detected(self):
        entry = self.write("main.py", "def run():\n    from helper import work\n")
        self.write("helper.py", "def work(): pass\n")
        self.assertEqual(len(audit(entry, self.root)["local_modules"]), 2)

    def test_dynamic_import_flagged(self):
        entry = self.write("main.py", "import importlib\nimportlib.import_module('plugin')\n")
        self.assertEqual(audit(entry, self.root)["dynamic_import_review"][0]["kind"], "import_module")

    def test_actual_alpha_gateway_audit(self):
        from scripts.platform_runtime_import_audit import ENTRY, SERVER
        report = audit(ENTRY, SERVER)
        self.assertIn("private_alpha_gateway.py", report["local_modules"])
        self.assertTrue(report["local_modules"])
        self.assertEqual(report["entry"], "private_alpha_gateway.py")

    def test_literal_stdlib_dynamic_import_is_not_unresolved(self):
        entry = self.write("main.py", "__import__('os')\\n")
        self.assertEqual(audit(entry, self.root)["dynamic_import_review"], [])

    def test_relative_local_import_is_resolved(self):
        entry = self.write("main.py", "from .helper import work\\n")
        self.write("helper.py", "def work(): pass\\n")
        report = audit(entry, self.root)
        self.assertEqual(report["local_modules"], ["helper.py", "main.py"])
        self.assertEqual(report["dynamic_import_review"], [])

    def test_reject_outside_root(self):
        entry = self.write("main.py", "import os\n")
        other = self.root / "nested"
        other.mkdir()
        with self.assertRaises(ValueError):
            audit(entry, other)


if __name__ == "__main__":
    unittest.main()
