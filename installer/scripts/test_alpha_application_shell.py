"""Focused M2.09 shell adapter tests; no user DB or external download."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from alpha_application_shell import inspect_installed_alpha, start_installed_alpha, main
from build_managed_alpha_runtime import managed_file_inventory

DB_SECRET = "DisposableTestCipherSecret123!"

FAKE_WORKER = """
import json
import sys
import time
frame = json.loads(sys.stdin.buffer.read())
if frame.get("sqlcipherKey") != "DisposableTestCipherSecret123!":
    sys.exit(2)
if frame.get("version") != 1 or frame.get("port") != 0:
    sys.exit(3)
print(json.dumps({
    "version": 1, "status": "ready", "bind": "127.0.0.1",
    "port": 48215, "encryptedDatabase": True,
    "hostClaimBootstrapEnabled": False
}), flush=True)
time.sleep(30)
"""


class AlphaApplicationShellTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="mf-app-shell-")
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        self.install = root / "installed"
        worker_dir = self.install / "application" / "server"
        worker_dir.mkdir(parents=True)
        self.worker = worker_dir / "installed_alpha_launch.py"
        self.worker.write_text(FAKE_WORKER, encoding="utf-8")
        fake_python = self.install / "runtime" / "python" / "bin" / "python3.11"
        fake_python.parent.mkdir(parents=True)
        fake_python.write_bytes(b"Not executable in this inventory-only fixture")
        self.db = root / "existing-encrypted.sqlite3"
        self.db.write_bytes(b"encrypted-fixture" + bytes(range(32)))
        inventory = managed_file_inventory(self.install)
        record = json.dumps(inventory, sort_keys=True, separators=(",", ":")) + "\n"
        (self.install / "managed-file-inventory.json").write_text(record, encoding="utf-8")
        digest = hashlib.sha256(record.encode("utf-8")).hexdigest()
        (self.install / "runtime-manifest.json").write_text(json.dumps({
            "schemaVersion": 1,
            "managedFileInventorySha256": digest,
            "applicationEntrypoint": "application/server/installed_alpha_launch.py",
            "pythonExecutable": "runtime/python/bin/python3.11"
        }), encoding="utf-8")

    def test_shell_prerequisites_are_independent_of_setup_manager(self):
        executable, entry, database, count = inspect_installed_alpha(
            self.install, self.db)
        self.assertEqual(executable.name, "python3.11")
        self.assertEqual(entry, self.worker)
        self.assertEqual(database, self.db)
        self.assertEqual(count, 2)
        status = io.StringIO()
        with contextlib.redirect_stdout(status):
            self.assertEqual(main([
                "--installation", str(self.install), "--database", str(self.db),
                "--verify-only"
            ]), 0)
        self.assertIn("verified_managed_alpha_shell_prerequisites", status.getvalue())
        self.assertNotIn(DB_SECRET, status.getvalue())

    def test_no_implicit_plaintext_or_missing_database(self):
        before = self.db.read_bytes()
        self.db.write_bytes(b"SQLite format 3\x00" + bytes(range(32)))
        with self.assertRaisesRegex(ValueError, "not an encrypted"):
            inspect_installed_alpha(self.install, self.db)
        self.db.unlink()
        with self.assertRaisesRegex(ValueError, "database unavailable"):
            inspect_installed_alpha(self.install, self.db)
        self.db.write_bytes(before)

    def test_tampered_or_extra_application_members_are_rejected(self):
        self.worker.write_bytes(self.worker.read_bytes() + b"# tamper\n")
        with self.assertRaisesRegex(ValueError, "content changed"):
            inspect_installed_alpha(self.install, self.db)
        self.worker.write_text(FAKE_WORKER, encoding="utf-8")
        (self.install / "undeclared.txt").write_text("extra", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "content changed"):
            inspect_installed_alpha(self.install, self.db)

    def test_private_shell_launches_gateway_without_secret_in_arguments(self):
        before = self.db.read_bytes()
        child, port = start_installed_alpha(
            sys.executable, self.worker, self.db, DB_SECRET, timeout=8)
        try:
            self.assertEqual(port, 48215)
            self.assertNotIn(DB_SECRET, " ".join(child.args))
            self.assertEqual(child.args[1:3], ["-I", "-B"])
            self.assertIsNone(child.poll())
        finally:
            child.terminate()
            child.wait(timeout=8)
            child.stdout.close()
        self.assertEqual(self.db.read_bytes(), before)

    def test_wrong_key_never_returns_ready_or_leaks_secret(self):
        with self.assertRaisesRegex(ValueError, "did not report readiness") as error:
            start_installed_alpha(
                sys.executable, self.worker, self.db,
                "WrongCipherPassword456!", timeout=8)
        self.assertNotIn("WrongCipherPassword456!", str(error.exception))
        with self.assertRaisesRegex(ValueError, "invalid SQLCipher key"):
            start_installed_alpha(sys.executable, self.worker, self.db, "")

    def test_no_argument_accepts_a_database_key(self):
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            with self.assertRaises(SystemExit) as exit_status:
                main(["--installation", str(self.install), "--database",
                      str(self.db), "--sqlcipher-key", DB_SECRET])
        self.assertEqual(exit_status.exception.code, 2)
        self.assertNotIn(DB_SECRET, captured.getvalue())


if __name__ == "__main__":
    unittest.main()
