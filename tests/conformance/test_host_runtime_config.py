import json
import unittest

from server.host_runtime_config import (
    HostRuntimeRegistry, RuntimeConfigurationError,
    prepare_comfy_effect, validate_runtime,
)
from server.comfy_workflow_inspection import WorkflowError


class HostRuntimeConfigTests(unittest.TestCase):
    def test_per_host_isolation_and_multiple_instances(self):
        registry = HostRuntimeRegistry()
        for name, port in (("primary", 8188), ("secondary", 8190)):
            registry.put("alice", "shadow", {"id": name, "type": "comfyui",
                         "endpoint": f"http://127.0.0.1:{port}", "enabled": True})
        self.assertEqual(len(registry.list("alice", "shadow")), 2)
        self.assertEqual(registry.list("bob", "shadow"), [])
        self.assertEqual(registry.list("alice", "other"), [])
        self.assertEqual(registry.require("alice", "shadow", "secondary")["endpoint"],
                         "http://127.0.0.1:8190")
        self.assertTrue(registry.remove("alice", "shadow", "primary"))
        self.assertEqual(len(registry.list("alice", "shadow")), 1)

    def test_reject_remote_or_injected_endpoints(self):
        for endpoint in ("http://example.com:8188", "https://127.0.0.1:8188",
                         "http://127.0.0.1:8188/path", "http://user:pass@localhost:8188",
                         "http://localhost:8188/?x=1", "file:///tmp/socket"):
            with self.subTest(endpoint=endpoint), self.assertRaises(RuntimeConfigurationError):
                validate_runtime({"id": "x", "type": "comfyui",
                                  "endpoint": endpoint, "enabled": True})

    def test_disabled_runtime_cannot_dispatch(self):
        registry = HostRuntimeRegistry()
        registry.put("alice", "pc", {"id": "c", "type": "comfyui",
                     "endpoint": "http://localhost:8188"})
        with self.assertRaises(RuntimeConfigurationError):
            registry.require("alice", "pc", "c")

    def test_verified_selection_only(self):
        workflow = json.dumps({"1": {"class_type": "Example",
                            "inputs": {"steps": 10, "prompt": "hi"}}}).encode()
        metadata = {"Example": {"input": {"required": {
            "steps": ["INT", {"min": 1, "max": 100}],
            "prompt": ["STRING", {}]}}}}
        effect = prepare_comfy_effect(workflow, metadata, ["1.steps"])
        self.assertEqual([p["binding"] for p in effect["parameters"]], ["1.steps"])
        self.assertEqual(effect["parameters"][0]["limits"]["max"], 100)
        with self.assertRaises(WorkflowError):
            prepare_comfy_effect(workflow, None, ["1.steps"])


if __name__ == "__main__":
    unittest.main()
