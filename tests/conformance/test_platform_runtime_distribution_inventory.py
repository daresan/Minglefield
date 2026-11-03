import json
import tempfile
import unittest
from pathlib import Path
from scripts.platform_runtime_distribution_inventory import inventory, read_audit_json


class RuntimeDistributionInventoryTests(unittest.TestCase):
    def test_statuses_and_dynamic_review(self):
        report = {"third_party_candidates": ["zeta", "alpha", "beta"],
                  "dynamic_import_review": [{"kind": "exec"}]}
        result = inventory(report, {"alpha": ["alpha-dist"], "beta": ["b", "a", "a"]})
        self.assertEqual([(x["import"], x["status"]) for x in result["imports"]],
                         [("alpha", "mapped"), ("beta", "ambiguous"), ("zeta", "unresolved")])
        self.assertFalse(result["release_dependency_closure_verified"])
        self.assertEqual(result["dynamic_import_review"], [{"kind": "exec"}])

    def test_read_audit_json_powershell_utf16_and_utf8(self):
        payload = {"third_party_candidates": ["jsonschema"]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            for encoding in ("utf-16", "utf-8", "utf-8-sig"):
                with self.subTest(encoding=encoding):
                    path.write_bytes(json.dumps(payload).encode(encoding))
                    self.assertEqual(read_audit_json(path), payload)

    def test_invalid_candidates(self):
        for names in (["a", "a"], ["a", ""], [None], "a"):
            with self.subTest(names=names):
                with self.assertRaises(ValueError):
                    inventory({"third_party_candidates": names}, {})


if __name__ == "__main__":
    unittest.main()
