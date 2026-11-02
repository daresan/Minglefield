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


    def test_direct_gateway_script_import(self):
        import subprocess
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        command = [sys.executable, "-B", "-c",
                   "import host_runtime_config; import sec01_host_commit_policy_sim"]
        result = subprocess.run(command, cwd=root / "server",
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_sqlite_persistence_and_owner_authorization(self):
        import os
        import sys
        import tempfile
        from pathlib import Path
        server_dir = str(Path(__file__).resolve().parents[2] / "server")
        if server_dir not in sys.path:
            sys.path.insert(0, server_dir)
        from private_alpha_auth import AlphaAuthStore
        from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
        from sec01_host_commit_policy_sim import HostCommitPolicy

        with tempfile.TemporaryDirectory() as directory:
            store = AlphaAuthStore(os.path.join(directory, "alpha.db"))
            policy = HostCommitPolicy(IntegratedAlphaAdmission(store))
            with store._tx() as db:
                db.execute("INSERT INTO sec01_host_owners(host_id,owner_id) VALUES(?,?)",
                           ("host.example", "alice"))
            runtime = {"id": "comfy-main", "type": "comfyui",
                       "endpoint": "http://127.0.0.1:8188", "enabled": True}
            self.assertEqual(policy.upsert_runtime("host.example", "bob", runtime).state, "denied")
            self.assertEqual(policy.upsert_runtime("host.example", "alice", runtime).state, "saved")
            self.assertIsNone(policy.list_runtimes("host.example", "bob"))
            reopened = HostCommitPolicy(IntegratedAlphaAdmission(AlphaAuthStore(
                os.path.join(directory, "alpha.db"))))
            self.assertEqual(reopened.list_runtimes("host.example", "alice"), [runtime])
            self.assertEqual(reopened.delete_runtime("host.example", "bob", "comfy-main").state, "denied")
            self.assertEqual(reopened.delete_runtime("host.example", "alice", "comfy-main").state, "deleted")
            self.assertEqual(reopened.list_runtimes("host.example", "alice"), [])


if __name__ == "__main__":
    unittest.main()
