"""Build a pinned, self-contained CPython + SQLCipher runtime for Minglefield Alpha.

Build-time command only (not an end-user Python prerequisite). Pins the 2026-10-26
python-build-standalone install-only stripped distributions and the exact 0.6.4
SQLCipher CPython 3.11 wheel per OS/architecture. Verifies their published
SHA-256 checksums before extraction. The output is a testable runtime directory,
NOT a signed release, native installer, or permission to provision a Host.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import Request, urlopen
from zipfile import ZipFile

PYTHON_RELEASE = "20261026"
PYTHON_VERSION = "3.11.18"
SQLCIPHER_VERSION = "0.6.4"
MAX_DOWNLOAD = 90 * 1024 * 1024
MAX_UNPACKED = 900 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[2]

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
            probe = subprocess.run(
                [str(executable), "-I", "-B", "-c",
                 "import sys,sqlcipher3;"
                 "assert sys.version_info[:2]==(3,11);"
                 "c=sqlcipher3.connect(':memory:');"
                 "assert c.execute('PRAGMA cipher_version').fetchone()[0];"
                 "c.close()"],
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
            manifest = {
                "schemaVersion": 1,
                "platform": variant[0] + "-" + variant[1],
                "standaloneRelease": PYTHON_RELEASE,
                "pythonVersion": PYTHON_VERSION,
                "pythonArchive": python_name,
                "pythonArchiveSha256": python_sha,
                "sqlcipherWheel": wheel_name,
                "sqlcipherWheelSha256": wheel_sha,
                "pythonExecutable": executable.relative_to(staged).as_posix(),
                "runtimeSmokeVerified": True,
                "applicationSourceIncluded": True,
                "applicationEntrypoint": application_entrypoint.relative_to(staged).as_posix(),
                "applicationArchiveSha256": sha256_file(application_archive),
                "applicationModuleCount": len(application_manifest["modules"]),
                "managedApplicationStartupVerified": True,
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
