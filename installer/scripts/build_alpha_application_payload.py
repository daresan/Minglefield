"""Create an inspectable Alpha application-source payload from the actual entrypoint.

This is a *real ZIP of launchable application modules* for a later native
installer to place alongside its own verified Python/SQLCipher runtime. It is
NOT a complete signed Minglefield release, installer, dependency lock or a
substitute for authorization of local Host onboarding.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import sys
from zipfile import ZipFile, ZipInfo, ZIP_STORED, BadZipFile

from audit_alpha_runtime_imports import audit

ENTRYPOINT = "installed_alpha_launch"
MANIFEST_NAME = "alpha-payload-manifest.json"
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_MANIFEST_BYTES = 512 * 1024
ROOT = Path(__file__).resolve().parents[2]


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _source_inventory(server_dir):
    server_dir = Path(server_dir)
    report = audit(server_dir, entrypoint=ENTRYPOINT)
    if report["errors"]:
        raise ValueError("unresolved Alpha application import graph")
    # A missing local import can be classified as external by the generic
    # auditor. The fixed gateway/auth/Host application modules are mandatory.
    required = {
        "installed_alpha_launch", "private_alpha_gateway",
        "private_alpha_auth", "alpha_sqlcipher_runtime",
        "sec01_integrated_alpha_admission", "sec01_host_commit_policy_sim"
    }
    if not required.issubset(report["scanned_modules"]):
        raise ValueError("required installed Alpha module missing from import closure")
    blobs = {}
    for name in report["scanned_modules"]:
        # An imported name comes only from the audited, top-level .py inventory.
        source = server_dir / (name + ".py")
        metadata = source.lstat()
        if not stat.S_ISREG(metadata.st_mode) or source.is_symlink():
            raise ValueError("nonregular or linked Alpha source module")
        if not 1 <= metadata.st_size <= MAX_SOURCE_BYTES:
            raise ValueError("invalid Alpha source module size")
        raw = source.read_bytes()
        if len(raw) != metadata.st_size or len(raw) > MAX_SOURCE_BYTES:
            raise ValueError("Alpha source changed during packaging")
        # actions/checkout uses platform-specific text checkout settings.
        # Runtime Python modules are Git text: canonicalize CRLF back to LF
        # so Windows and Unix builds carry byte-identical application code.
        data = raw.replace(b"\r\n", b"\n")
        blobs["server/" + source.name] = data
    if "server/installed_alpha_launch.py" not in blobs:
        raise ValueError("missing installed Alpha launch entrypoint")
    manifest = {
        "schemaVersion": 1,
        "kind": "minglefield-alpha-application-sources",
        "entrypoint": "server/installed_alpha_launch.py",
        "pythonRuntimeIncluded": False,
        "runtimeDependencyLockVerified": False,
        "publisherSignatureVerified": False,
        "modules": {name: {"sha256": _sha(data), "size": len(data)}
                    for name, data in sorted(blobs.items())},
        "externalImports": report["external_imports"],
        "dynamicImportSites": report["dynamic_import_sites"],
    }
    return manifest, blobs


def build_payload(server_dir, output):
    """Package the exact audited module closure to one previously absent ZIP."""
    output = Path(output)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("payload output must be a new file in an existing directory")
    manifest, blobs = _source_inventory(server_dir)
    metadata = (json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")) + "\n").encode("utf-8")
    if len(metadata) > MAX_MANIFEST_BYTES:
        raise ValueError("Alpha payload manifest too large")
    with output.open("xb") as handle:
        with ZipFile(handle, "w") as archive:
            for name, content in sorted({MANIFEST_NAME: metadata, **blobs}.items()):
                info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = ZIP_STORED
                archive.writestr(info, content)
    return {
        "file": str(output),
        "size": output.stat().st_size,
        "sha256": _sha(output.read_bytes()),
        "includedModules": len(blobs),
        "runtimeDependencyLockVerified": False,
        "installable": False,
    }


def inspect_payload(path):
    """Verify every member against its manifest; never extract arbitrary ZIPs."""
    with ZipFile(path, "r") as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or MANIFEST_NAME not in names:
            raise ValueError("payload has duplicate or missing entries")
        manifest_entry = archive.getinfo(MANIFEST_NAME)
        if not 0 < manifest_entry.file_size <= MAX_MANIFEST_BYTES:
            raise ValueError("invalid payload manifest size")
        manifest = json.loads(archive.read(MANIFEST_NAME))
        if (type(manifest) is not dict or manifest.get("schemaVersion") != 1
                or manifest.get("kind") != "minglefield-alpha-application-sources"
                or manifest.get("entrypoint") != "server/installed_alpha_launch.py"
                or manifest.get("pythonRuntimeIncluded") is not False
                or manifest.get("runtimeDependencyLockVerified") is not False
                or type(manifest.get("modules")) is not dict):
            raise ValueError("invalid Alpha payload manifest")
        modules = manifest["modules"]
        if set(names) != set(modules) | {MANIFEST_NAME}:
            raise ValueError("payload content differs from declared module inventory")
        for name, record in modules.items():
            if (type(name) is not str or not name.startswith("server/")
                    or name.count("/") != 1 or not name.endswith(".py")
                    or name.split("/")[-1] in ("", ".", "..")
                    or type(record) is not dict or set(record) != {"sha256", "size"}
                    or type(record["size"]) is not int
                    or not 1 <= record["size"] <= MAX_SOURCE_BYTES
                    or type(record["sha256"]) is not str
                    or len(record["sha256"]) != 64):
                raise ValueError("unreviewed payload module entry")
            if archive.getinfo(name).file_size != record["size"]:
                raise ValueError("payload file size mismatch")
            data = archive.read(name)
            if len(data) != record["size"] or _sha(data) != record["sha256"]:
                raise ValueError("payload file digest mismatch")
        return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-dir", type=Path, default=ROOT / "server")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = build_payload(args.server_dir, args.output)
        inspect_payload(args.output)
    except (OSError, ValueError, BadZipFile, json.JSONDecodeError):
        print("Alpha application payload generation rejected", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
