"""Build a pinned, self-contained CPython + SQLCipher runtime for Minglefield Alpha.

Build-time command only (not an end-user Python prerequisite). Pins the 2026-10-26
python-build-standalone install-only stripped distributions and the exact 0.6.4
SQLCipher CPython 3.11 wheel per OS/architecture. Verifies their published
SHA-256 checksums before extraction. The output is a testable runtime directory,
NOT a signed release, native installer, or permission to provision a Host.
"""
import argparse
import hashlib
import http.client
import json
import os
import queue
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import threading
import tempfile
from urllib.request import Request, urlopen
from zipfile import ZipFile

PYTHON_RELEASE = "20261026"
PYTHON_VERSION = "3.11.18"
SQLCIPHER_VERSION = "0.6.4"
MAX_DOWNLOAD = 90 * 1024 * 1024
MAX_UNPACKED = 900 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[2]
# Fixed binary-wheel versions for every external import in the current
# Alpha application closure. No user needs pip, Conda or system Python.
# Every wheel's exact platform filename and SHA-256 are recorded in the
# generated manifest; publisher provenance is still a separate release gate.
RUNTIME_REQUIREMENTS = (
    ("attrs", "25.4.0"),
    ("jsonschema", "4.26.0"),
    ("jsonschema_specifications", "2025.9.1"),
    ("packaging", "25.0"),
    ("referencing", "0.36.2"),
    ("rpds_py", "0.27.1"),
    ("typing_extensions", "4.15.0"),
)

# Exact build-time supply-chain inputs, not only version constraints.
# Universal Python wheels have identical hashes on every operating system.
# The rpds native wheel differs by platform and requires an exact match.
PINNED_APPLICATION_WHEELS = {
    "attrs-25.4.0-py3-none-any.whl":
        "adcf7e2a1fb3b36ac48d97835bb6d8ade15b8dcce26aba8bf1d14847b57a3373",
    "jsonschema-4.26.0-py3-none-any.whl":
        "d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce",
    "jsonschema_specifications-2025.9.1-py3-none-any.whl":
        "98802fee3a11ee76ecaca44429fda8a41bff98b00a0f2838151b113f210cc6fe",
    "packaging-25.0-py3-none-any.whl":
        "29572ef2b1f17581046b3a2227d5c611fb25ec70ca1ba8554b24b0e69331a484",
    "referencing-0.36.2-py3-none-any.whl":
        "e8699adbbf8b5c7de96d8ffa0eb5c158b3beafce084968e2ea8bb08c6794dcd0",
    "typing_extensions-4.15.0-py3-none-any.whl":
        "f0fa19c6845758ab08074a0cfa8b7aecb71c999ca73d62883bc25cc018c4e548",
    "rpds_py-0.27.1-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl":
        "cb56c6210ef77caa58e16e8c17d35c63fe3f5b60fd9ba9d424470c3400bcf9ed",
    "rpds_py-0.27.1-cp311-cp311-win_amd64.whl":
        "b4938466c6b257b2f5c4ff98acd8128ec36b5059e5c8f8372d79316b1c36bb15",
    "rpds_py-0.27.1-cp311-cp311-macosx_11_0_arm64.whl":
        "62ac3d4e3e07b58ee0ddecd71d6ce3b1637de2d373501412df395a0ec5f9beb5",
    "rpds_py-0.27.1-cp311-cp311-macosx_10_12_x86_64.whl":
        "be898f271f851f68b318872ce6ebebbc62f303b654e43bf72683dbdc25b7c881",
}

# These release-digest values are source-pinned and deliberately platform exact.
# macOS has separate arm64 and Intel builds; other unsupported machines fail.
BUNDLES = {
    ("windows", "x86_64"): (
        "x86_64-pc-windows-msvc",
        "67215a7bf1643e33d01b17ee3f1e91a8b0b39163746855ee02594bf0608f68b4",
        "sqlcipher3-0.6.4-cp311-cp311-win_amd64.whl",
        "23f867c0d14c9f0274fea62425c1b02fb812a56e766ea3e6e0c7d5e4e3a90cd3",
    ),
    ("linux", "x86_64"): (
        "x86_64-unknown-linux-gnu",
        "17c4978a36c496dc53c08899ef8dad1ad2734f6325f08d6033a1e66419e0af26",
        "sqlcipher3-0.6.4-cp311-cp311-manylinux_2_28_x86_64.whl",
        "8168f8799b3d63c36ace6aeec3bc78818a52af85a0e756e1b5963673ccb7af29",
    ),
    ("darwin", "aarch64"): (
        "aarch64-apple-darwin",
        "f3e1cd83a7f1d70e58b0d69102c18bd6867d2f973068dc5cbfd5822e445c66df",
        "sqlcipher3-0.6.4-cp311-cp311-macosx_11_0_arm64.whl",
        "c33225299e329931c1e492d3dee4c51b3f38d909d1d0dbcd03b503aa17a0327a",
    ),
    ("darwin", "x86_64"): (
        "x86_64-apple-darwin",
        "d38edc2df25e7e7f886c802bf2fa552422b097c509dbdcbae828827470356095",
        "sqlcipher3-0.6.4-cp311-cp311-macosx_10_9_x86_64.whl",
        "99e193635a6ca6503669853a2ba5733d73c98ae29bf810d64564474c8b41676f",
    ),
}


def current_variant():
    machine = platform.machine().lower()
    if machine in ("amd64", "x64"):
        machine = "x86_64"
    if machine in ("arm64", "aarch64"):
        machine = "aarch64"
    variant = (platform.system().lower(), machine)
    if variant not in BUNDLES:
        raise ValueError("managed Alpha runtime does not support this platform")
    return variant


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_pinned_file(path, expected):
    if not Path(path).is_file() or sha256_file(path) != expected:
        raise ValueError("managed runtime source hash mismatch")


def _download_pinned(url, destination, digest):
    """Stream only a bounded body; erase a mismatch before extraction."""
    destination = Path(destination)
    request = Request(url, headers={"User-Agent": "Minglefield-Alpha-Build/1"})
    total = 0
    with urlopen(request, timeout=90) as response, destination.open("xb") as output:
        hasher = hashlib.sha256()
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > MAX_DOWNLOAD:
                raise ValueError("managed runtime archive exceeds bound")
            output.write(block)
            hasher.update(block)
    if hasher.hexdigest() != digest:
        destination.unlink(missing_ok=True)
        raise ValueError("managed runtime archive digest mismatch")


def _safe_relative(name):
    """Archive member must be a single relative POSIX path, not a drive/escape."""
    if (type(name) is not str or not name or name.startswith("/")
            or "\\" in name or ":" in name or "\x00" in name):
        raise ValueError("unsafe managed runtime archive path")
    parts = PurePosixPath(name).parts
    if not parts or ".." in parts or any(x in ("", ".") for x in parts):
        raise ValueError("unsafe managed runtime archive traversal")
    return parts


def extract_standalone(archive_path, target):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        total = 0
        for item in members:
            parts = _safe_relative(item.name)
            if parts[0] != "python" or not (item.isfile() or item.isdir() or item.issym()):
                raise ValueError("unexpected standalone archive member")
            total += item.size
            if item.size > MAX_DOWNLOAD or total > MAX_UNPACKED:
                raise ValueError("standalone expansion exceeds size bound")
            if item.issym():
                link = item.linkname
                if (not link or link.startswith("/") or "\\" in link
                        or ":" in link or "\x00" in link):
                    raise ValueError("unsafe standalone symlink")
                # Validate the resolved target under staging root. No links
                # into a parent installation, checkout, or arbitrary user files.
                dest = target.joinpath(*parts)
                resolved = (dest.parent / link).resolve(strict=False)
                if not resolved.is_relative_to(target.resolve()):
                    raise ValueError("standalone symlink escapes staging")
        # Python 3.11.18 supports the data extraction filter. It rejects
        # absolute links, special devices, and other unsafe tar metadata.
        archive.extractall(target, filter="data")


def extract_sqlcipher_wheel(wheel_path, site_packages):
    site_packages = Path(site_packages)
    site_packages.mkdir(parents=True, exist_ok=True)
    total = 0
    with ZipFile(wheel_path) as wheel:
        entries = wheel.infolist()
        names = [item.filename for item in entries]
        if len(names) != len(set(names)):
            raise ValueError("duplicate SQLCipher wheel member")
        for info in entries:
            parts = _safe_relative(info.filename)
            if info.is_dir():
                continue
            total += info.file_size
            mode = (info.external_attr >> 16) & 0o170000
            if (info.file_size > MAX_DOWNLOAD or total > MAX_DOWNLOAD
                    or mode not in (0, stat.S_IFREG)):
                raise ValueError("untrusted SQLCipher wheel member")
            dest = site_packages.joinpath(*parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with wheel.open(info) as inp, dest.open("xb") as out:
                shutil.copyfileobj(inp, out)


def find_embedded_python(python_root, variant):
    if variant[0] == "windows":
        paths = ("python.exe", "python3.11.exe", "bin/python.exe")
    else:
        paths = ("bin/python3.11", "bin/python3", "bin/python")
    for relative in paths:
        candidate = python_root / relative
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    raise ValueError("embedded Python executable missing from pinned archive")


def smoke_managed_application(executable, application_entrypoint):
    """Exercise real login and Host/Game APIs with the bundled interpreter.

    Creates only disposable local fixture DB state. The first-run account is
    seeded by the already tested *trusted* storage primitive for this test;
    it is not a production provisioning API or a GUI authorization bypass.
    """
    with tempfile.TemporaryDirectory(prefix="minglefield-packaged-alpha-http-") as temp:
        work = Path(temp)
        database = work / "isolated-fixture.sqlite3"
        fixture = {
            "database": str(database),
            "moduleDir": str(application_entrypoint.parent),
            "cipherKey": "Ephemeral-Build-Test-Cipher-Key-123!",
            "loginKey": "Independent-Build-Test-Login-Key-456!",
        }
        initialization = """
import json,sys
a=json.loads(sys.stdin.read())
sys.path.insert(0,a["moduleDir"])
from alpha_sqlcipher_runtime import sqlcipher_driver
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy
db=sqlcipher_driver().connect(a["database"])
try:
    db.execute("PRAGMA key = '" + a["cipherKey"].replace("'", "''") + "'")
    db.execute("CREATE TABLE existing_marker(value TEXT)")
    db.execute("INSERT INTO existing_marker VALUES('intact')")
    db.commit()
finally:
    db.close()
store=AlphaAuthStore(a["database"],sqlcipher_key_provider=lambda:a["cipherKey"])
result=HostCommitPolicy(IntegratedAlphaAdmission(store)).provision_first_run_local_host_admin_trusted(
    "host.alpha",a["loginKey"])
assert result.state=="created", "failed to seed local test Host"
"""
        init = subprocess.run(
            [str(executable), "-I", "-B", "-c", initialization],
            input=json.dumps(fixture).encode("utf-8"),
            capture_output=True, timeout=120, check=False)
        if init.returncode != 0:
            raise ValueError("embedded Alpha fixture initialization failed")
        if not database.is_file():
            raise ValueError("embedded Alpha fixture not created")

        process = subprocess.Popen(
            [str(executable), "-I", "-B", str(application_entrypoint)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0)
        try:
            startup = {
                "version": 1, "databasePath": str(database),
                "sqlcipherKey": fixture["cipherKey"], "port": 0,
            }
            process.stdin.write(json.dumps(startup).encode("utf-8"))
            process.stdin.close()
            ready_lines = queue.Queue(maxsize=1)
            threading.Thread(
                target=lambda: ready_lines.put(process.stdout.readline()),
                daemon=True).start()
            try:
                line = ready_lines.get(timeout=140)
            except queue.Empty:
                raise ValueError("embedded Alpha service start timeout") from None
            if not line:
                raise ValueError("embedded Alpha service terminated before readiness")
            status = json.loads(line)
            if (type(status) is not dict or status.get("status") != "ready"
                    or status.get("bind") != "127.0.0.1"
                    or type(status.get("port")) is not int
                    or not 0 < status["port"] <= 65535):
                raise ValueError("invalid embedded Alpha readiness response")
            port = status["port"]

            def call(method, endpoint, body=None, session=None):
                connection = http.client.HTTPConnection(
                    "127.0.0.1", port, timeout=12)
                headers = {"Host": "127.0.0.1:" + str(port)}
                if body is not None:
                    headers["Content-Type"] = "application/json"
                if session is not None:
                    headers["Authorization"] = "Bearer " + session
                try:
                    connection.request(
                        method, endpoint,
                        body=json.dumps(body) if body is not None else None,
                        headers=headers)
                    result = connection.getresponse()
                    return result.status, json.loads(result.read(64 * 1024))
                finally:
                    connection.close()

            denied, _ = call("POST", "/api/login", {
                "user_id": "mingleadmin", "password": fixture["cipherKey"]})
            if denied != 401:
                raise ValueError("database key must not authenticate an Alpha user")
            success, login = call("POST", "/api/login", {
                "user_id": "mingleadmin", "password": fixture["loginKey"]})
            if success != 200 or type(login.get("session_token")) is not str:
                raise ValueError("embedded Alpha login failed")
            session = login["session_token"]
            owner, hosts = call("GET", "/api/hosts", session=session)
            if owner != 200 or [h["host_id"] for h in hosts["hosts"]] != ["host.alpha"]:
                raise ValueError("embedded Alpha Host ownership mismatch")
            p = str(work / "game")
            created, _ = call("POST", "/api/game/projects", {
                "host_id": "host.alpha", "project_id": "game.alpha",
                "name": "Managed Alpha", "repository_root": p,
                "job_attachments_root": p, "output_root": p,
            }, session=session)
            if created != 201:
                raise ValueError("embedded Alpha Game project creation failed")
            forbidden, _ = call(
                "GET", "/api/game/projects?host_id=host.remote",
                session=session)
            if forbidden != 403:
                raise ValueError("embedded Alpha foreign Host authorization failed")
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)
            process.stdout.close()
            process.stderr.close()
    return True


MANAGED_FILES_NAME = "managed-file-inventory.json"
MAX_MANAGED_ENTRIES = 40000
MAX_MANAGED_BYTES = 2 * 1024 * 1024 * 1024


def managed_file_inventory(root):
    """Enumerate the exact reusable payload for native install verification.

    Source/backup databases and the temporary first-run test fixture are not
    part of this folder. Every regular file is hashed; symlinks remain relative
    and are allowed only when they resolve inside the managed payload.
    """
    root = Path(root).resolve(strict=True)
    records = {}
    total = 0
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root).as_posix()
        if relative in ("runtime-manifest.json", MANAGED_FILES_NAME):
            continue
        parts = _safe_relative(relative)
        if not parts or len(records) > MAX_MANAGED_ENTRIES:
            raise ValueError("invalid managed bundle inventory")
        if item.is_symlink():
            target = os.readlink(item)
            if Path(target).is_absolute() or not item.resolve(strict=True).is_relative_to(root):
                raise ValueError("managed runtime symlink escapes bundle")
            records[relative] = {"type": "symlink", "target": target}
        elif item.is_dir():
            continue
        elif item.is_file():
            size = item.stat().st_size
            total += size
            if size > MAX_DOWNLOAD or total > MAX_MANAGED_BYTES:
                raise ValueError("managed runtime exceeds bounded inventory")
            records[relative] = {
                "type": "file", "size": size,
                "sha256": sha256_file(item)
            }
        else:
            raise ValueError("managed runtime contains an unsupported file")
        if len(records) > MAX_MANAGED_ENTRIES:
            raise ValueError("managed runtime inventory is too large")
    return {"schemaVersion": 1, "files": records}


def verify_managed_file_inventory(root, expected_sha256):
    """Recheck every file and link after preparation, without executing them."""
    root = Path(root).resolve(strict=True)
    record = root / MANAGED_FILES_NAME
    if not record.is_file() or record.is_symlink():
        raise ValueError("managed runtime inventory is missing")
    if sha256_file(record) != expected_sha256:
        raise ValueError("managed runtime inventory digest mismatch")
    expected = json.loads(record.read_text(encoding="utf-8"))
    actual = managed_file_inventory(root)
    if expected != actual:
        raise ValueError("managed runtime content changed after verification")
    return len(actual["files"])


def build_runtime(output):
    """Prepare a reusable runtime; never modify an existing output directory."""
    variant = current_variant()
    triple, python_sha, wheel_name, wheel_sha = BUNDLES[variant]
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("runtime output must be absent within existing directory")
    python_name = (
        "cpython-" + PYTHON_VERSION + "+" + PYTHON_RELEASE
        + "-" + triple + "-install_only_stripped.tar.gz"
    )
    url = (
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        + PYTHON_RELEASE + "/" + python_name.replace("+", "%2B")
    )
    with tempfile.TemporaryDirectory(prefix="minglefield-managed-download-") as tmp:
        temp = Path(tmp)
        archive_path = temp / python_name
        _download_pinned(url, archive_path, python_sha)
        wheel_dir = temp / "wheels"
        wheel_dir.mkdir()
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "download", "--no-deps",
             "--only-binary=:all:", "--disable-pip-version-check",
             "--dest", str(wheel_dir), "sqlcipher3==" + SQLCIPHER_VERSION],
            capture_output=True, timeout=180, check=False)
        if proc.returncode != 0:
            raise ValueError("cannot download pinned SQLCipher driver wheel")
        wheels = list(wheel_dir.iterdir())
        if len(wheels) != 1 or wheels[0].name != wheel_name:
            raise ValueError("SQLCipher driver wheel platform mismatch")
        verify_pinned_file(wheels[0], wheel_sha)
        dependencies_dir = temp / "application-wheels"
        dependencies_dir.mkdir()
        # --no-deps is deliberate: the complete declared closure is pinned
        # here. Do not silently accept pip's mutable dependency resolution.
        other = subprocess.run(
            [sys.executable, "-m", "pip", "download", "--no-deps",
             "--only-binary=:all:", "--disable-pip-version-check",
             "--dest", str(dependencies_dir),
             *(name.replace("_", "-") + "==" + version
               for name, version in RUNTIME_REQUIREMENTS)],
            capture_output=True, timeout=180, check=False)
        if other.returncode != 0:
            raise ValueError("cannot download complete pinned Alpha runtime wheels")
        files = sorted(dependencies_dir.iterdir())
        if len(files) != len(RUNTIME_REQUIREMENTS):
            raise ValueError("incomplete or unexpected Alpha runtime wheels")
        required = {name: version for name, version in RUNTIME_REQUIREMENTS}
        found = set()
        for wheel in files:
            parts = wheel.name.split("-", 2)
            if len(parts) != 3 or not wheel.name.endswith(".whl"):
                raise ValueError("unrecognized Alpha wheel name")
            package, version = parts[:2]
            if required.get(package) != version or package in found:
                raise ValueError("unexpected Alpha dependency wheel or version")
            if wheel.name not in PINNED_APPLICATION_WHEELS:
                raise ValueError("unapproved Alpha dependency wheel filename")
            verify_pinned_file(wheel, PINNED_APPLICATION_WHEELS[wheel.name])
            found.add(package)
        if found != set(required):
            raise ValueError("missing Alpha application wheel")
        wheel_inventory = [
            {"filename": wheel.name, "sha256": sha256_file(wheel)}
            for wheel in files
        ]
        with tempfile.TemporaryDirectory(
                prefix="minglefield-managed-stage-", dir=output.parent) as staging:
            staged = Path(staging)
            extract_standalone(archive_path, staged / "runtime")
            python_root = staged / "runtime" / "python"
            executable = find_embedded_python(python_root, variant)
            site_packages = python_root / (
                "Lib/site-packages" if variant[0] == "windows"
                else "lib/python3.11/site-packages"
            )
            extract_sqlcipher_wheel(wheels[0], site_packages)
            for wheel in files:
                extract_sqlcipher_wheel(wheel, site_packages)
            probe = subprocess.run(
                [str(executable), "-I", "-B", "-c",
                 "import sys,sqlcipher3;"
                 "assert sys.version_info[:2]==(3,11);"
                 "c=sqlcipher3.connect(':memory:');"
                 "assert c.execute('PRAGMA cipher_version').fetchone()[0];"
                 "c.close();"
                 "from packaging.version import Version;"
                 "assert Version('1.2') < Version('2.0');"
                 "from jsonschema import Draft202012Validator;"
                 "Draft202012Validator({'type':'object'}).validate({})"],
                capture_output=True, timeout=60, check=False)
            if probe.returncode != 0:
                raise ValueError("embedded Python/SQLCipher runtime self-test failed")

            # Bring the actual application with its managed runtime, not just
            # an interpreter. Reuse the reviewed module-closure ZIP/manifest.
            from build_alpha_application_payload import build_payload, inspect_payload
            application_archive = staged / "alpha-application.zip"
            build_payload(ROOT / "server", application_archive)
            application_manifest = inspect_payload(application_archive)
            with ZipFile(application_archive, "r") as source_zip:
                for filename in sorted(application_manifest["modules"]):
                    target_file = staged / "application" / filename
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    with source_zip.open(filename) as src, target_file.open("xb") as dst:
                        shutil.copyfileobj(src, dst)
            application_entrypoint = (
                staged / "application" / application_manifest["entrypoint"])
            application_probe = subprocess.run(
                [str(executable), "-I", "-B", str(application_entrypoint)],
                input=b'{"invalid":true}', capture_output=True,
                timeout=90, check=False)
            if (application_probe.returncode != 2 or application_probe.stdout
                    or b"installed_alpha_start_rejected" not in application_probe.stderr):
                raise ValueError("managed Alpha application import/startup self-test failed")
            smoke_managed_application(executable, application_entrypoint)
            inventory = managed_file_inventory(staged)
            inventory_bytes = (json.dumps(
                inventory, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            inventory_file = staged / MANAGED_FILES_NAME
            inventory_file.write_bytes(inventory_bytes)
            inventory_digest = sha256_file(inventory_file)
            if verify_managed_file_inventory(staged, inventory_digest) != len(
                    inventory["files"]):
                raise ValueError("managed runtime inventory roundtrip failed")

            manifest = {
                "schemaVersion": 1,
                "platform": variant[0] + "-" + variant[1],
                "standaloneRelease": PYTHON_RELEASE,
                "pythonVersion": PYTHON_VERSION,
                "pythonArchive": python_name,
                "pythonArchiveSha256": python_sha,
                "sqlcipherWheel": wheel_name,
                "sqlcipherWheelSha256": wheel_sha,
                "applicationRuntimeWheels": wheel_inventory,
                "externalRuntimeImportsVerified": True,
                "pythonExecutable": executable.relative_to(staged).as_posix(),
                "runtimeSmokeVerified": True,
                "applicationSourceIncluded": True,
                "applicationEntrypoint": application_entrypoint.relative_to(staged).as_posix(),
                "applicationArchiveSha256": sha256_file(application_archive),
                "applicationModuleCount": len(application_manifest["modules"]),
                "managedApplicationStartupVerified": True,
                "managedApplicationHttpLoginVerified": True,
                "managedHostAndGameApisVerified": True,
                "managedFileInventory": MANAGED_FILES_NAME,
                "managedFileInventorySha256": inventory_digest,
                "managedFileCount": len(inventory["files"]),
                "fullRuntimeDependencyClosureVerified": False,
                "publisherSignatureVerified": False,
                "completeProductInstallation": False,
            }
            (staged / "runtime-manifest.json").write_text(
                json.dumps(manifest, sort_keys=True, indent=2) + "\n",
                encoding="utf-8")
            # Stage in a private sibling, then publish only to a previously
            # absent development output. This is NOT the end-user installer
            # transaction, whose native authorization is a separate gate.
            os.rename(staged, output)
            return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_runtime(args.output)
    except (OSError, ValueError, tarfile.TarError, subprocess.TimeoutExpired):
        print("managed_alpha_runtime_build_rejected", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
