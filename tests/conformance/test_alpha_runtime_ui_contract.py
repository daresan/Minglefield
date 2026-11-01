"""Regression checks for the local Alpha runtime/workflow UI contract."""
import unittest
from pathlib import Path


class AlphaRuntimeUIContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (Path(__file__).resolve().parents[2] /
                      "server" / "private_alpha_gateway.py").read_text(encoding="utf-8")

    def test_runtime_controls_are_present(self):
        for control in ("runtimeSelect", "runtimeId", "runtimeEndpoint",
                        "runtimeNew", "runtimeSave", "runtimeDelete"):
            self.assertIn('id="' + control + '"', self.source)

    def test_workflow_file_picker_supports_verified_persistent_import(self):
        self.assertIn('type="file" id="comfyWorkflowFile"', self.source)
        self.assertIn('id="comfyWorkflowInspect"', self.source)
        self.assertIn('id="comfyWorkflowSave"', self.source)
        self.assertIn('"/api/host/comfy/inspect"', self.source)
        self.assertIn('"/api/host/comfy/import"', self.source)
        self.assertIn("policy.import_comfy_workflow(", self.source)

    def test_runtime_endpoints_use_existing_host_policy(self):
        self.assertIn('policy.upsert_runtime(', self.source)
        self.assertIn('policy.delete_runtime(', self.source)
        self.assertIn('policy.list_runtimes(', self.source)


if __name__ == "__main__":
    unittest.main()
