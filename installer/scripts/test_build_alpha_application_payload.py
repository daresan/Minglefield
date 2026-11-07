"""Real Alpha application module-closure ZIP construction and verification."""
import hashlib
import http.client
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
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
            self.assertIn("server/installed_alpha_first_run.py", manifest["modules"])
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

    def test_packaged_application_opens_real_cipher_database_and_hosts(self):
        """Use the extracted bundle, not the checkout, for authenticated HTTP."""
        from importlib.util import find_spec
        if find_spec("sqlcipher3") is None:
            self.skipTest("SQLCipher driver unavailable outside pinned CI")
        sys.path.insert(0, str(ROOT / "server"))
        try:
            from alpha_sqlcipher_runtime import sqlcipher_driver
            from private_alpha_auth import AlphaAuthStore
            from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
            from sec01_host_commit_policy_sim import HostCommitPolicy
        finally:
            sys.path.pop(0)
        with TemporaryDirectory(prefix="minglefield-packaged-alpha-") as temp:
            root = Path(temp).resolve()
            archive_path = root / "application.zip"
            build_payload(ROOT / "server", archive_path)
            inspect_payload(archive_path)
            installed = root / "installed-application"
            with ZipFile(archive_path) as archive:
                archive.extractall(installed)
            script = installed / "server" / "installed_alpha_launch.py"
            self.assertTrue(script.is_file())
            database = root / "data" / "alpha.sqlite3"
            database.parent.mkdir()
            db_key = "Packaged-Alpha-Database-Password123!"
            login_key = "Independent-Alpha-Login-Password123!"
            with sqlcipher_driver().connect(str(database)) as db:
                db.execute("PRAGMA key = '" + db_key + "'")
                db.execute("CREATE TABLE protected_marker(value TEXT)")
                db.execute("INSERT INTO protected_marker VALUES('source remains intact')")
            store = AlphaAuthStore(database, sqlcipher_key_provider=lambda: db_key)
            policy = HostCommitPolicy(IntegratedAlphaAdmission(store))
            self.assertEqual(
                policy.provision_first_run_local_host_admin_trusted(
                    "host.alpha", login_key).state, "created")
            proc = subprocess.Popen(
                [sys.executable, "-I", "-B", str(script)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, bufsize=0)
            try:
                startup = {
                    "version": 1, "databasePath": str(database),
                    "sqlcipherKey": db_key, "port": 0}
                proc.stdin.write(json.dumps(startup).encode("utf-8"))
                proc.stdin.close()
                ready_lines = queue.Queue(maxsize=1)
                reader = threading.Thread(
                    target=lambda: ready_lines.put(proc.stdout.readline()),
                    daemon=True)
                reader.start()
                try:
                    ready_bytes = ready_lines.get(timeout=90)
                except queue.Empty:
                    self.fail("packaged Alpha did not start before deadline")
                self.assertTrue(ready_bytes, "packaged Alpha exited before ready")
                ready = json.loads(ready_bytes)
                self.assertEqual(ready["status"], "ready")
                self.assertEqual(ready["bind"], "127.0.0.1")
                port = ready["port"]

                def call(method, endpoint, data=None, token=None):
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                    headers = {"Host": "127.0.0.1:" + str(port)}
                    if data is not None:
                        headers["Content-Type"] = "application/json"
                    if token is not None:
                        headers["Authorization"] = "Bearer " + token
                    try:
                        conn.request(method, endpoint,
                                     body=json.dumps(data) if data is not None else None,
                                     headers=headers)
                        resp = conn.getresponse()
                        return resp.status, json.loads(resp.read())
                    finally:
                        conn.close()

                status, login = call("POST", "/api/login", {
                    "user_id": "mingleadmin", "password": login_key})
                self.assertEqual(status, 200)
                token = login["session_token"]
                status, hosts = call("GET", "/api/hosts", token=token)
                self.assertEqual(status, 200)
                self.assertEqual([h["host_id"] for h in hosts["hosts"]], ["host.alpha"])
                project_dir = str(root / "game")
                created, data = call("POST", "/api/game/projects", {
                    "host_id": "host.alpha", "project_id": "game.alpha",
                    "name": "Packaged Game", "repository_root": project_dir,
                    "job_attachments_root": project_dir, "output_root": project_dir
                }, token=token)
                self.assertEqual(created, 201, data)
                blocked, _ = call("GET", "/api/game/projects?host_id=host.other",
                                  token=token)
                self.assertEqual(blocked, 403)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=15)
                proc.stdout.close()
                proc.stderr.close()
            with store._tx() as db:
                self.assertEqual(db.execute(
                    "SELECT value FROM protected_marker").fetchone()[0],
                    "source remains intact")
                self.assertEqual(db.execute(
                    "SELECT name FROM alpha_game_projects WHERE project_id=?",
                    ("game.alpha",)).fetchone()[0], "Packaged Game")

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
            chain = [
                ("installed_alpha_launch", "private_alpha_gateway"),
                ("installed_alpha_first_run", "private_alpha_auth"),
                ("private_alpha_gateway", "private_alpha_auth"),
                ("private_alpha_auth", "alpha_sqlcipher_runtime"),
                ("alpha_sqlcipher_runtime", "sec01_integrated_alpha_admission"),
                ("sec01_integrated_alpha_admission", "sec01_host_commit_policy_sim"),
                ("sec01_host_commit_policy_sim", "pathlib"),
            ]
            for name, imported in chain:
                (directory / (name + ".py")).write_text(
                    "import " + imported + "\n", encoding="utf-8")
            (directory / "unrelated.py").write_text(
                "raise RuntimeError('not part of application')\n", encoding="utf-8")
            manifest, modules = _source_inventory(directory)
            self.assertEqual(set(modules), {
                "server/" + name + ".py" for name, _ in chain
            })
            self.assertEqual(len(manifest["modules"]), 7)
            (directory / "private_alpha_gateway.py").unlink()
            with self.assertRaises(ValueError):
                _source_inventory(directory)

    def test_platform_checkout_line_endings_produce_same_source_bundle(self):
        """Windows CRLF checkout must not change application package identity."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_names = (
                "installed_alpha_launch", "installed_alpha_first_run",
                "private_alpha_gateway", "private_alpha_auth", "alpha_sqlcipher_runtime",
                "sec01_integrated_alpha_admission", "sec01_host_commit_policy_sim"
            )
            for ending, dirname in ((b"\n", "unix"), (b"\r\n", "windows")):
                directory = root / dirname
                directory.mkdir()
                for name in source_names:
                    dependencies = (
                        "import " + "\nimport ".join(
                            x for x in source_names if x != name
                        ) + "\n"
                    ).encode("utf-8").replace(b"\n", ending)
                    (directory / (name + ".py")).write_bytes(dependencies)
                build_payload(directory, root / (dirname + ".zip"))
            self.assertEqual(
                (root / "unix.zip").read_bytes(),
                (root / "windows.zip").read_bytes())

    def test_symlink_module_is_rejected(self):
        with TemporaryDirectory() as temp:
            directory = Path(temp) / "server"
            directory.mkdir()
            (directory / "installed_alpha_launch.py").write_text(
                "import dependency\n", encoding="utf-8")
            (directory / "installed_alpha_first_run.py").write_text(
                "import private_alpha_auth\n", encoding="utf-8")
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
