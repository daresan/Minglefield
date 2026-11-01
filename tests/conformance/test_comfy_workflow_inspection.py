"""Read-only workflow importer conformance smoke tests."""
import json
import unittest
from server.comfy_workflow_inspection import WorkflowError, inspect_api_workflow


class ComfyWorkflowInspectionTests(unittest.TestCase):
    def setUp(self):
        self.graph = {"1": {"class_type": "CLIPTextEncode",
                            "inputs": {"text": "castle", "clip": ["2", 0]}},
                      "2": {"class_type": "CheckpointLoaderSimple",
                            "inputs": {"ckpt_name": "model.safetensors"}}}

    def test_candidates_never_auto_exposed(self):
        result = inspect_api_workflow(json.dumps(self.graph))
        self.assertEqual(result["selected_bindings"], [])
        self.assertEqual([x["binding"] for x in result["candidates"]],
                         ["1.text", "2.ckpt_name"])
        self.assertFalse(result["candidates"][0]["verified"])

    def test_authoritative_metadata(self):
        meta = {"CLIPTextEncode": {"input": {"required": {
            "text": ["STRING", {"multiline": True}]}}}}
        result = inspect_api_workflow(json.dumps(self.graph), meta)
        self.assertTrue(result["candidates"][0]["verified"])
        self.assertEqual(result["candidates"][0]["type"], "string")

    def test_reject_ui_format(self):
        with self.assertRaises(WorkflowError):
            inspect_api_workflow('{"nodes": [], "links": []}')

    def test_reject_oversized(self):
        with self.assertRaises(WorkflowError):
            inspect_api_workflow(b"x" * (2 * 1024 * 1024 + 1))


if __name__ == "__main__":
    unittest.main()
