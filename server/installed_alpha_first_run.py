"""Private first-run database transaction worker for the native Tauri Setup Manager.

NOT an authorization API. The *native* installer must separately establish
installation identity, operator consent and the exact approved encrypted target
before starting this worker. No endpoint, token claim or network listener here.
All secrets enter through one bounded anonymous stdin payload, never arguments,
environment, logs or persistent configuration.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alpha_sqlcipher_runtime import open_alpha_database
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy

MAX_FRAME = 8192
FIELDS = frozenset({
    "version", "databasePath", "sqlcipherKey", "loginUserId",
    "loginPassword", "localHostId"
})


def main():
    try:
        frame = sys.stdin.buffer.read(MAX_FRAME + 1)
        if not frame or len(frame) > MAX_FRAME:
            raise ValueError("invalid first-run frame length")
        message = json.loads(frame)
        if (type(message) is not dict or set(message) != FIELDS
                or type(message["version"]) is not int or message["version"] != 1
                or any(type(message[key]) is not str for key in FIELDS - {"version"})):
            raise ValueError("invalid first-run request")
        db = Path(message["databasePath"])
        if not db.is_absolute() or db.is_symlink() or not db.is_file():
            raise ValueError("first-run target must be an existing encrypted database")
        secret = message["sqlcipherKey"]
        login_password = message["loginPassword"]
        if (not secret or len(secret) > 4096 or "\x00" in secret
                or not login_password or len(login_password) > 256):
            raise ValueError("invalid first-run credentials")
        # Fail before the existing Alpha store can create any table for an
        # invalid key/plaintext source. The native launcher authorizes this
        # particular installed database; this worker does not decide trust.
        opened = open_alpha_database(db, key_provider=lambda: secret)
        try:
            opened.execute("SELECT count(*) FROM sqlite_schema").fetchone()
        finally:
            opened.close()
        store = AlphaAuthStore(db, sqlcipher_key_provider=lambda: secret)
        result = HostCommitPolicy(IntegratedAlphaAdmission(store)).provision_first_run_local_host_admin_trusted(
            message["localHostId"], login_password,
            login_user_id=message["loginUserId"])
        if result.state != "created":
            # Denial reasons are fixed internal enums, never user inputs.
            print(json.dumps({"status": "denied", "reason": result.reason}), flush=True)
            return 3
        print(json.dumps({
            "status": "local_host_admin_created",
            "loginUserId": message["loginUserId"],
            "localHostId": message["localHostId"],
            "remoteHostAuthorityGranted": False,
        }, sort_keys=True), flush=True)
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, KeyError):
        # Do not print raw exceptions or Python tracebacks: SQLCipher messages
        # might embed keys or paths. A generic error is intentional.
        print("installed_alpha_first_run_rejected", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
