"""Private installed-Alpha subprocess entrypoint for a native owner-controlled launcher.

Only the verified local installer/application launcher may supply the *one*
bounded stdin payload. No database path or password is read from argv,
environment, disk configuration, the gateway or the public Alpha HTTP API.
This module does not authorize a Host claim or provision an administrator.
"""
import json
from pathlib import Path
import sys

# Python -I excludes PYTHONPATH and site-user customizations; import our
# reviewed application modules from the directory containing this script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from private_alpha_gateway import create_installed_local_alpha_server

MAX_STARTUP_BYTES = 8192
STARTUP_FIELDS = frozenset({
    "version", "databasePath", "sqlcipherKey", "port"
})


def main():
    try:
        payload = sys.stdin.buffer.read(MAX_STARTUP_BYTES + 1)
        if not payload or len(payload) > MAX_STARTUP_BYTES:
            raise ValueError("invalid startup length")
        message = json.loads(payload)
        if (type(message) is not dict or set(message) != STARTUP_FIELDS
                or type(message["version"]) is not int or message["version"] != 1
                or type(message["databasePath"]) is not str
                or type(message["sqlcipherKey"]) is not str
                or type(message["port"]) is not int):
            raise ValueError("invalid startup envelope")
        # Do not hold a second copy of the secret in the request mapping.
        secret = message.pop("sqlcipherKey")
        server = create_installed_local_alpha_server(
            message["databasePath"], key_provider=lambda: secret,
            port=message["port"])
    except (ValueError, TypeError, OSError, RuntimeError):
        # Never include exception details, candidate passwords, supplied
        # paths, tokens or complete request fields in process diagnostics.
        print("installed_alpha_start_rejected", file=sys.stderr, flush=True)
        return 2

    try:
        # The native launcher needs only the ephemeral loopback address to
        # connect its window, not an admin token or database unlock secret.
        print(json.dumps({
            "version": 1, "status": "ready",
            "bind": "127.0.0.1", "port": server.server_port,
            "encryptedDatabase": True, "hostClaimBootstrapEnabled": False
        }, sort_keys=True), flush=True)
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
