"""Developer/CI shell entrypoint for an already built *managed* Alpha application.

This is a testable M2.09 shell/CLI development adapter, NOT the final native
Minglefield.exe/Minglefield.app user entrypoint and NOT an installer CLI.
It reuses the installed application's existing SQLCipher gateway rather than
building a parallel authorization or database layer. Native app launch later
uses the same private startup frame without depending on this Python script.
"""
import argparse
import getpass
import json
from pathlib import Path
import queue
import stat
import subprocess
import sys
import threading
import webbrowser


HEADER = b"SQLite format 3\x00"
MAX_MANIFEST = 64 * 1024
MAX_REQUEST = 8192


def _real_file(path):
    try:
        metadata = path.lstat()
        return stat.S_ISREG(metadata.st_mode) and not path.is_symlink()
    except OSError:
        return False


def inspect_installed_alpha(install_dir, database_path):
    """Validate paths and the complete source inventory; do not change DB.

    The bundle manifest is self-declared, not evidence of trusted publishing.
    Release/native installers independently bind it to a trusted digest.
    """
    install = Path(install_dir)
    database = Path(database_path)
    if not install.is_absolute() or install.is_symlink() or not install.is_dir():
        raise ValueError("installed Alpha directory invalid")
    if not database.is_absolute() or not _real_file(database):
        raise ValueError("encrypted Alpha database unavailable")
    with database.open("rb") as handle:
        header = handle.read(16)
    if len(header) != 16 or header == HEADER:
        raise ValueError("selected database is not an encrypted SQLCipher file")
    install = install.resolve(strict=True)
    database = database.resolve(strict=True)
    manifest_path = install / "runtime-manifest.json"
    if not _real_file(manifest_path) or manifest_path.stat().st_size > MAX_MANIFEST:
        raise ValueError("installed runtime manifest missing or oversized")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if type(manifest) is not dict or manifest.get("schemaVersion") != 1:
        raise ValueError("installed runtime manifest format invalid")
    digest = manifest.get("managedFileInventorySha256")
    if type(digest) is not str or len(digest) != 64 or any(
            byte not in "0123456789abcdef" for byte in digest):
        raise ValueError("installed runtime inventory digest invalid")
    if manifest.get("applicationEntrypoint") != "application/server/installed_alpha_launch.py":
        raise ValueError("unexpected installed Alpha entrypoint")
    def member(name):
        value = manifest.get(name)
        if type(value) is not str or not value or "\\" in value or ":" in value:
            raise ValueError("invalid managed runtime path")
        relative = Path(value)
        if relative.is_absolute() or any(part in (".", "..") for part in value.split("/")):
            raise ValueError("unsafe managed runtime path")
        file = install / relative
        if not _real_file(file) or not file.resolve(strict=True).is_relative_to(install):
            raise ValueError("managed runtime member missing")
        return file
    interpreter = member("pythonExecutable")
    entrypoint = member("applicationEntrypoint")
    # Import lazily: the build-time runtime smoke test also reuses this
    # launcher without introducing a cyclic build/launch import.
    from build_managed_alpha_runtime import verify_managed_file_inventory
    count = verify_managed_file_inventory(install, digest)
    return interpreter, entrypoint, database, count


def start_installed_alpha(interpreter, entrypoint, database, secret, *, timeout=90):
    """Spawn the existing installed Alpha; deliver the DB key only over stdin."""
    if type(secret) is not str or not 1 <= len(secret) <= 4096 or "\x00" in secret:
        raise ValueError("invalid SQLCipher key")
    frame = json.dumps({
        "version": 1, "databasePath": str(database),
        "sqlcipherKey": secret, "port": 0
    }, separators=(",", ":")).encode("utf-8")
    if len(frame) > MAX_REQUEST:
        raise ValueError("SQLCipher startup request too large")
    child = subprocess.Popen(
        [str(interpreter), "-I", "-B", str(entrypoint)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, cwd=str(entrypoint.parent),
        bufsize=0
    )
    try:
        try:
            child.stdin.write(frame)
            child.stdin.close()
        except OSError:
            raise ValueError("installed Alpha worker input unavailable") from None
        response = queue.Queue(maxsize=1)
        def await_readiness():
            try:
                response.put(child.stdout.readline(MAX_REQUEST + 1))
            except OSError:
                response.put(b"")
        threading.Thread(target=await_readiness, daemon=True).start()
        try:
            line = response.get(timeout=timeout)
        except queue.Empty:
            raise ValueError("installed Alpha startup timed out") from None
        if not line or len(line) > MAX_REQUEST:
            raise ValueError("installed Alpha did not report readiness")
        try:
            ready = json.loads(line)
        except (ValueError, UnicodeError):
            raise ValueError("invalid installed Alpha readiness frame") from None
        if (type(ready) is not dict or ready.get("status") != "ready"
                or ready.get("bind") != "127.0.0.1"
                or type(ready.get("port")) is not int
                or not 1 <= ready["port"] <= 65535
                or ready.get("encryptedDatabase") is not True
                or ready.get("hostClaimBootstrapEnabled") is not False):
            raise ValueError("installed Alpha readiness does not meet local security contract")
        return child, ready["port"]
    except (ValueError, OSError):
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)
        child.stdout.close()
        raise


class QuietArgumentParser(argparse.ArgumentParser):
    def error(self, _message):
        # argparse otherwise echoes unknown option values, possibly secrets.
        self.exit(2, "minglefield_managed_alpha_shell_arguments_rejected\\n")


def main(argv=None):
    parser = QuietArgumentParser(description=__doc__)
    parser.add_argument("--installation", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    try:
        interpreter, entrypoint, database, count = inspect_installed_alpha(
            args.installation, args.database)
        if args.verify_only:
            print(json.dumps({"status": "verified_managed_alpha_shell_prerequisites",
                              "managedEntries": count}, sort_keys=True))
            return 0
        # A terminal is only a development/CI adapter. The native Minglefield
        # executable will use an app-owned GUI key prompt, not a console.
        if not sys.stdin.isatty():
            raise ValueError("interactive SQLCipher password prompt required")
        secret = getpass.getpass("SQLCipher-Datenbankpasswort: ")
        child, port = start_installed_alpha(interpreter, entrypoint, database, secret)
        url = f"http://127.0.0.1:{port}/"
        print("Minglefield Alpha started on local loopback: " + url, flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            return child.wait()
        except KeyboardInterrupt:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            return 0
        finally:
            child.stdout.close()
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
        # Secrets, DB locations and raw child tracebacks must not appear here.
        print("minglefield_managed_alpha_shell_rejected", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
