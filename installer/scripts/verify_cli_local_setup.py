"""CI-only real CLI first-run smoke with a disposable *managed* Alpha build.

The bundled Python worker is the application's original Alpha admission and
HostCommitPolicy implementation. Never use a real user database or run this
against a machine's existing installed Minglefield directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import tempfile

FILE_CONFIRM = "INSTALL MINGLEFIELD ALPHA FILES"
DB_CONFIRM = "CREATE NEW ENCRYPTED DATABASE"
HOST_CONFIRM = "ACTIVATE LOCAL HOST ADMIN"
TEST_DB_KEY = "DisposableCipherKey9!"
TEST_LOGIN = "DisposableLoginKey8!"


def executable_name():
    return "python.exe" if platform.system().lower() == "windows" else "bin/python3.11"


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_smoke(package):
    package = package.resolve(strict=True)
    manifest = json.loads((package / "runtime-manifest.json").read_text(encoding="utf-8"))
    digest = manifest["managedFileInventorySha256"]
    assert digest == fingerprint(package / "managed-file-inventory.json")
    with tempfile.TemporaryDirectory(prefix="minglefield-cli-first-run-") as directory:
        root = Path(directory)
        installed = root / "installed-minglefield"
        database = root / "private-data" / "minglefield.sqlite3"
        database.parent.mkdir()
        command = [
            "cargo", "run", "--quiet", "-p", "minglefield-installer-cli",
            "--", "--silent", "--defaults", "--json",
            "--install-alpha-files",
            "--package-dir", str(package),
            "--inventory-sha256", digest,
            "--install-dir", str(installed),
            "--confirm-install", FILE_CONFIRM,
            "--create-new-encrypted-db",
            "--database", str(database),
            "--new-db-password", TEST_DB_KEY,
            "--confirm-new-db", DB_CONFIRM,
            "--setup-local-host",
            "--login-user-id", "mingleadmin",
            "--login-password", TEST_LOGIN,
            "--confirm-local-admin", HOST_CONFIRM,
        ]
        completed = subprocess.run(
            command, text=True, capture_output=True, timeout=300,
            check=False,
        )
        assert completed.returncode == 0, "local setup CLI did not complete"
        receipt = json.loads(completed.stdout)
        assert receipt["status"] == "local_host_admin_created"
        assert receipt["encrypted_database_created"] is True
        assert receipt["application_files_installed"] is True
        assert receipt["remote_host_authority_granted"] is False
        assert receipt["native_application_launch_enabled"] is False
        assert receipt["full_installation_completed"] is False
        assert receipt["login_user_id"] == "mingleadmin"
        host_id = receipt["local_host_id"]
        assert host_id.startswith("local.") and len(host_id) > 20
        assert database.exists()
        assert database.read_bytes()[:16] != b"SQLite format 3\x00"

        # Open the SQLCipher DB using the *installed* runtime, not the
        # workflow runner's Python interpreter or plaintext sqlite3.
        embedded = installed / "runtime" / "python" / executable_name()
        probe_script = r"""
import json, sys, sqlcipher3
message = json.loads(sys.stdin.buffer.read())
connection = sqlcipher3.connect(message["database"])
key = message["key"].replace("'", "''")
connection.execute("PRAGMA key = '" + key + "'")
assert connection.execute("SELECT count(*) FROM alpha_users").fetchone()[0] == 1
assert connection.execute(
    "SELECT count(*) FROM alpha_passwords WHERE user_id='mingleadmin'"
).fetchone()[0] == 1
assert connection.execute(
    "SELECT count(*) FROM sec01_host_owners WHERE host_id=? AND owner_id='mingleadmin'",
    (message["host"],)
).fetchone()[0] == 1
assert connection.execute(
    "SELECT count(*) FROM alpha_executor_hosts WHERE host_id=? AND operator_id='mingleadmin'",
    (message["host"],)
).fetchone()[0] == 1
assert connection.execute("SELECT count(*) FROM alpha_sessions").fetchone()[0] == 0
connection.close()
"""
        check = subprocess.run(
            [str(embedded), "-I", "-B", "-c", probe_script],
            input=json.dumps({"database": str(database), "key": TEST_DB_KEY, "host": host_id}),
            capture_output=True, text=True, timeout=120, check=False,
        )
        assert check.returncode == 0, "installed SQLCipher Host/login verification failed"
        prior_db = fingerprint(database)
        prior_inventory = fingerprint(installed / "managed-file-inventory.json")
        again = subprocess.run(
            command, text=True, capture_output=True, timeout=120, check=False,
        )
        assert again.returncode != 0, "repeated local first-run setup was accepted"
        assert fingerprint(database) == prior_db
        assert fingerprint(installed / "managed-file-inventory.json") == prior_inventory
    return {"status": "cli_local_first_run_verified", "native_application_launch": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_smoke(args.package), sort_keys=True))


if __name__ == "__main__":
    main()
