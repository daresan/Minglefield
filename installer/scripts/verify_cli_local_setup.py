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


def run_smoke(package, *, require_native=False):
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
            command, encoding="utf-8", errors="replace",
            capture_output=True, timeout=300,
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
# The actual embedded application's login policy must accept only the
# independent account credential, not the SQLCipher encryption key.
from pathlib import Path
sys.path.insert(0, str(Path(message["installed"]) / "application" / "server"))
from private_alpha_auth import AlphaAuthStore
store = AlphaAuthStore(
    message["database"],
    sqlcipher_key_provider=lambda: message["key"],
)
assert store.login("mingleadmin", message["key"]) is None
assert store.login("mingleadmin", "WrongLoginPassword9!") is None
authorization = store.login("mingleadmin", message["login"])
assert authorization is not None
assert store.principal("Bearer " + authorization) is not None
"""
        check = subprocess.run(
            [str(embedded), "-I", "-B", "-c", probe_script],
            input=json.dumps({
                "database": str(database), "key": TEST_DB_KEY, "host": host_id,
                "login": TEST_LOGIN, "installed": str(installed),
            }),
            capture_output=True, encoding="utf-8",
            errors="replace", timeout=120, check=False,
        )
        assert check.returncode == 0, "installed SQLCipher Host/login verification failed"
        has_native = manifest.get("nativeApplicationIncluded") is True
        if require_native:
            assert has_native, "build did not include OS-native Minglefield executable"
        if has_native:
            entry = manifest["nativeApplicationExecutable"]
            assert entry in ("Minglefield", "Minglefield.exe")
            native = installed / entry
            assert native.is_file() and not native.is_symlink()
            # The native binary, not Python or the Setup Manager, is the
            # direct process entrypoint. The gateway is actually started and
            # reached on loopback, then cleanly stopped in probe mode.
            command_native = [
                str(native), "--database", str(database),
                "--db-password", TEST_DB_KEY, "--no-browser", "--probe-exit",
            ]
            launched = subprocess.run(
                command_native, capture_output=True, encoding="utf-8",
                errors="replace", timeout=110, check=False,
            )
            # The runner's Windows cp1252 locale must not corrupt UTF-8
            # native process output. Only print *fixed native error reasons*,
            # never arbitrary stdout, database paths, argv or passwords.
            safe_failure = "unclassified_native_failure"
            if launched.stderr.startswith("minglefield_native_launch_rejected: "):
                safe_failure = launched.stderr.splitlines()[0]
            reference_result = "not_needed"
            if launched.returncode != 0:
                # The established developer-only adapter uses exactly the
                # same embedded interpreter and private Alpha entrypoint.
                # Compare only on native failure; never print raw worker
                # stderr, SQLCipher keys, paths or private startup frames.
                from alpha_application_shell import start_installed_alpha
                reference_result = "reference_worker_failed"
                try:
                    worker, _port = start_installed_alpha(
                        embedded,
                        installed / "application/server/installed_alpha_launch.py",
                        database,
                        TEST_DB_KEY,
                        timeout=35,
                    )
                except (OSError, ValueError, subprocess.SubprocessError):
                    pass
                else:
                    reference_result = "reference_worker_started"
                    worker.terminate()
                    try:
                        worker.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        worker.kill()
                        worker.wait(timeout=15)
                    if worker.stdout is not None:
                        worker.stdout.close()
            assert launched.returncode == 0, (
                "native app failed independent startup: "
                + safe_failure + " " + reference_result
                + " rc=" + str(launched.returncode)
            )
            report = json.loads(launched.stdout)
            assert report["status"] == "native_minglefield_startup_verified"
            assert report["encryptedDatabase"] is True
            assert report["hostClaimBootstrapEnabled"] is False
            assert report["hostProvisioningEnabled"] is False
            assert report["bind"] == "127.0.0.1"

            wrong_key = subprocess.run(
                [str(native), "--database", str(database), "--verify-only",
                 "--db-password", "WrongCipherSecret9!"],
                encoding="utf-8", errors="replace",
                capture_output=True, timeout=30, check=False,
            )
            assert wrong_key.returncode != 0
            assert "WrongCipherSecret9!" not in wrong_key.stdout
            assert "WrongCipherSecret9!" not in wrong_key.stderr

            # A second independent launch uses an *administrator-authored*
            # Bee-style version-3 configuration file next to Minglefield.
            # This is not a default generated secret file.
            config = installed / "minglefield.conf"
            config.write_text(
                "version=3\n"
                "install_optional_conda=false\n"
                "install_optional_comfyui=false\n"
                "explicit_optional_consent=false\n"
                "install_optional_git=false\n"
                "install_optional_gh=false\n"
                "offer_gh_login=false\n"
                "consent_git=false\n"
                "consent_gh=false\n"
                "consent_login=false\n"
                "database_path=" + str(database) + "\n"
                "db_password=" + TEST_DB_KEY + "\n",
                encoding="utf-8",
            )
            restarted = subprocess.run(
                [str(native), "--no-browser", "--probe-exit"],
                encoding="utf-8", errors="replace",
                capture_output=True, timeout=110, check=False,
            )
            assert restarted.returncode == 0, "native app restart using owner config failed"
            assert json.loads(restarted.stdout)["status"] == (
                "native_minglefield_startup_verified"
            )
            config.unlink()

            if platform.system().lower() == "darwin":
                # Package the *already installed* and verified application
                # using the conventional Finder .app layout. The same
                # executable must restart inside Contents/MacOS without
                # Setup Manager, system Python or a source checkout.
                from package_macos_alpha_app import package_macos_app
                bundle = root / "Minglefield.app"
                bundle_result = package_macos_app(installed, bundle)
                assert bundle_result["status"] == "native_macos_app_bundle_created"
                assert bundle_result["codeSigningVerified"] is False
                bundled_app = bundle / "Contents/MacOS/Minglefield"
                bundle_launch = subprocess.run(
                    [
                        str(bundled_app), "--database", str(database),
                        "--db-password", TEST_DB_KEY, "--probe-exit",
                        "--no-browser",
                    ],
                    capture_output=True, encoding="utf-8",
                    errors="replace", timeout=110, check=False,
                )
                safe_bundle_error = "unclassified_macos_bundle_start_failure"
                if bundle_launch.stderr.startswith(
                    "minglefield_native_launch_rejected: "
                ):
                    safe_bundle_error = bundle_launch.stderr.splitlines()[0]
                assert bundle_launch.returncode == 0, (
                    "native macOS .app executable failed to launch: "
                    + safe_bundle_error
                )
                bundle_start = json.loads(bundle_launch.stdout)
                assert bundle_start["status"] == (
                    "native_minglefield_startup_verified"
                )
                assert bundle_start["bind"] == "127.0.0.1"
                assert bundle_start["hostClaimBootstrapEnabled"] is False

        prior_db = fingerprint(database)
        prior_inventory = fingerprint(installed / "managed-file-inventory.json")
        again = subprocess.run(
            command, encoding="utf-8", errors="replace",
            capture_output=True, timeout=120, check=False,
        )
        assert again.returncode != 0, "repeated local first-run setup was accepted"
        assert fingerprint(database) == prior_db
        assert fingerprint(installed / "managed-file-inventory.json") == prior_inventory
        if has_native:
            # The native program must reject tampered managed application
            # content *before* unlocking the DB or opening a gateway.
            application_script = (
                installed / "application" / "server" / "installed_alpha_launch.py"
            )
            application_script.write_bytes(
                application_script.read_bytes() + b"\n# altered after install\n"
            )
            rejected = subprocess.run(
                [str(native), "--database", str(database), "--verify-only",
                 "--db-password", TEST_DB_KEY],
                encoding="utf-8", errors="replace",
                capture_output=True, timeout=30, check=False,
            )
            assert rejected.returncode != 0, (
                "native app accepted modified installed application content"
            )
            assert TEST_DB_KEY not in rejected.stderr
            assert fingerprint(database) == prior_db
    return {
        "status": "cli_local_first_run_verified",
        "native_application_launch": has_native,
        "native_application_restart_verified": has_native,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--require-native", action="store_true")
    args = parser.parse_args()
    print(json.dumps(
        run_smoke(args.package, require_native=args.require_native),
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
