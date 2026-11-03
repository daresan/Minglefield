"""Offline fixture tests for the transitive Alpha runtime import audit."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from audit_alpha_runtime_imports import audit


class AlphaRuntimeImportAuditTests(unittest.TestCase):
    def test_reachable_external_imports_and_dynamic_sites(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "private_alpha_gateway.py").write_text(
                "import json\nfrom helper import run\n", encoding="utf-8"
            )
            (root / "helper.py").write_text(
                "from jsonschema import Draft202012Validator\n"
                "import importlib\n"
                "def run():\n    return importlib.import_module('packaging')\n",
                encoding="utf-8",
            )
            (root / "unreachable.py").write_text("import unrelated_vendor\n", encoding="utf-8")
            result = audit(root)
            self.assertEqual(result["scanned_modules"], ["helper", "private_alpha_gateway"])
            self.assertEqual(result["external_imports"], {"jsonschema": ["helper"]})
            self.assertEqual(len(result["dynamic_import_sites"]), 1)
            self.assertFalse(result["runtime_lock_verified"])

    def test_reports_relative_imports_and_parse_errors(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "private_alpha_gateway.py").write_text(
                "from .local import x\nimport helper\n", encoding="utf-8"
            )
            (root / "helper.py").write_text("def broken(:\n", encoding="utf-8")
            result = audit(root)
            self.assertEqual(len(result["errors"]), 2)

    def test_missing_entrypoint_is_error(self):
        with TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            audit(Path(tmp))


if __name__ == "__main__":
    unittest.main()
