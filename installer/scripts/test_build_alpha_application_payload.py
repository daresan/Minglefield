"""Real Alpha application module-closure ZIP construction and verification."""
import hashlib
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile, ZipInfo, ZIP_STORED

from build_alpha_application_payload import (
    ROOT, build_payload, inspect_payload, _source_inventory
)


class AlphaPayloadTests(unittest.TestCase):
    def test_real_gateway_entrypoint_is_present_and_runtime_is_not_falsely_claimed(self):
        with TemporaryDirectory(prefix="minglefield-alpha-payload-") as temp:
            payload = Path(temp) / "app.zip"
            report = build_payload(ROOT / "server", payload)
            self.assertTrue(payload.is_file())
            self.assertFalse(report["installable"])
            self.assertFalse(report["runtimeDependencyLockVerified"])
            manifest = inspect_payload(payload)
            self.assertIn("server/installed_alpha_launch.py", manifest["modules"])
            self.assertIn("server/private_alpha_gateway.py", manifest["modules"])
            self.assertIn("server/private_alpha_auth.py", manifest["modules"])
            self.assertFalse(manifest["publisherSignatureVerified"])
            self.assertFalse(manifest["pythonRuntimeIncluded"])
            self.assertEqual(hashlib.sha256(payload.read_bytes()).hexdigest(), report["sha256"])
            with ZipFile(payload) as archive:
                archive.extractall(Path(temp) / "installed-source")
            # The packaged real process can import its own dependency closure,
            # without the original checkout on PYTHONPATH.
            script = Path(temp) / "installed-source" / "server" / "installed_alpha_launch.py"
            child = subprocess.run(
                [sys.executable, "-I", "-B", str(script)],
                input=b'{"invalid":true}', stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, timeout=20, check=False)
            self.assertEqual(child.returncode, 2)
            self.assertEqual(child.stdout, b"")
            self.assertIn(b"installed_alpha_start_rejected", child.stderr)

    def test_reproducible_and_collision_safe(self):
        with TemporaryDirectory() as temp:
            a = Path(temp) / "a.zip"
            b = Path(temp) / "b.zip"
            build_payload(ROOT / "server", a)
            build_payload(ROOT / "server", b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            before = a.read_bytes()
            with self.assertRaises(ValueError):
                build_payload(ROOT / "server", a)
            self.assertEqual(a.read_bytes(), before)

    def test_untracked_module_is_excluded_and_missing_import_is_blocked(self):
        with TemporaryDirectory() as temp:
            directory = Path(temp) / "server"
            directory.mkdir()
            (directory / "installed_alpha_launch.py").write_text(
                "import private_alpha_gateway\n", encoding="utf-8")
            (directory / "private_alpha_gateway.py").write_text(
                "import pathlib\n", encoding="utf-8")
            (directory / "unrelated.py").write_text(
                "raise RuntimeError('not part of application')\n", encoding="utf-8")
            manifest, modules = _source_inventory(directory)
            self.assertEqual(set(modules), {
                "server/installed_alpha_launch.py", "server/private_alpha_gateway.py"})
            (directory / "private_alpha_gateway.py").unlink()
            with self.assertRaises(ValueError):
                _source_inventory(directory)

    def test_symlink_module_is_rejected(self):
        with TemporaryDirectory() as temp:
            directory = Path(temp) / "server"
            directory.mkdir()
            (directory / "installed_alpha_launch.py").write_text(
                "import dependency\n", encoding="utf-8")
            actual = Path(temp) / "external.py"
            actual.write_text("PASS = True\n", encoding="utf-8")
            try:
                (directory / "dependency.py").symlink_to(actual)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on runner")
            with self.assertRaises(ValueError):
                _source_inventory(directory)

    def test_corrupt_member_is_rejected_even_if_zip_itself_is_readable(self):
        with TemporaryDirectory() as temp:
            good = Path(temp) / "good.zip"
            corrupt = Path(temp) / "corrupt.zip"
            build_payload(ROOT / "server", good)
            with ZipFile(good) as original, ZipFile(corrupt, "w") as edited:
                for file in original.infolist():
                    data = original.read(file.filename)
                    if file.filename == "server/installed_alpha_launch.py":
                        data = data + b"\n# unapproved changed code"
                    edited.writestr(file.filename, data)
            with self.assertRaisesRegex(ValueError, "(size|digest) mismatch"):
                inspect_payload(corrupt)


if __name__ == "__main__":
    unittest.main()
