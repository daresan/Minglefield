"""Assemble a Finder-recognizable Minglefield.app from an already verified payload.

This is a build/CI-only packaging step. The bundled native Minglefield binary
remains the application's executable; the Setup Manager is not shipped as an
application runtime dependency. The existing managed-alpha inventory is
reverified without rewriting its signed-for-future-release payload bytes.
"""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import sys
import tempfile

from build_managed_alpha_runtime import (
    MANAGED_FILES_NAME,
    verify_managed_file_inventory,
)


def verify_native_macos_source(source):
    source = Path(source)
    if source.is_symlink() or not source.is_dir():
        raise ValueError("macOS application package source must be a real directory")
    source = source.resolve(strict=True)
    manifest_path = source / "runtime-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("macOS native source manifest missing")
    if manifest_path.stat().st_size > 65536:
        raise ValueError("macOS native manifest too large")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schemaVersion") != 1
        or not str(manifest.get("platform", "")).startswith("macos-")
        or manifest.get("nativeApplicationIncluded") is not True
        or manifest.get("nativeApplicationExecutable") != "Minglefield"
        or manifest.get("applicationEntrypoint")
        != "application/server/installed_alpha_launch.py"
    ):
        raise ValueError("source is not the verified macOS Minglefield application")
    inventory_sha = manifest.get("managedFileInventorySha256")
    if (
        not isinstance(inventory_sha, str)
        or len(inventory_sha) != 64
        or not all(char in "0123456789abcdef" for char in inventory_sha)
    ):
        raise ValueError("macOS source has no recognized inventory digest")
    if verify_managed_file_inventory(source, inventory_sha) < 1:
        raise ValueError("macOS source inventory is empty")
    executable = source / "Minglefield"
    if executable.is_symlink() or not executable.is_file():
        raise ValueError("native macOS application entrypoint absent")
    if not executable.stat().st_mode & 0o111:
        raise ValueError("macOS native executable lacks execution permission")
    return source, inventory_sha


def package_macos_app(source, destination):
    """Atomically publish a new .app with Contents/MacOS as managed Alpha root.

    This preserves every native file, dependency and relative link, so the
    original Minglefield binary can still inspect its own canonical inventory
    when launched from Finder's conventional Contents/MacOS directory.
    """
    source, inventory_sha = verify_native_macos_source(source)
    destination = Path(destination).absolute()
    if (
        destination.name != "Minglefield.app"
        or destination.exists()
        or destination.is_symlink()
        or not destination.parent.is_dir()
        or destination.parent.is_symlink()
        or destination.is_relative_to(source)
        or source.is_relative_to(destination)
    ):
        raise ValueError("macOS application bundle destination must be unused and separate")
    with tempfile.TemporaryDirectory(
        prefix=".minglefield-macos-bundle-", dir=destination.parent
    ) as temporary:
        staged = Path(temporary) / "Minglefield.app"
        contents = staged / "Contents"
        contents.mkdir(parents=True)
        managed = contents / "MacOS"
        # No generated config, login password, database or Host tokens.
        shutil.copytree(source, managed, symlinks=True)
        (contents / "Info.plist").write_bytes(
            plistlib.dumps(
                {
                    "CFBundleDevelopmentRegion": "en",
                    "CFBundleExecutable": "Minglefield",
                    "CFBundleIdentifier": "org.minglefield.alpha",
                    "CFBundleInfoDictionaryVersion": "6.0",
                    "CFBundleName": "Minglefield",
                    "CFBundleDisplayName": "Minglefield",
                    "CFBundlePackageType": "APPL",
                    "CFBundleShortVersionString": "0.1.0",
                    "CFBundleVersion": "1",
                    "NSHighResolutionCapable": True,
                },
                fmt=plistlib.FMT_XML,
                sort_keys=True,
            )
        )
        if verify_managed_file_inventory(managed, inventory_sha) < 1:
            raise ValueError("copied macOS bundle failed its original managed inventory")
        if not (managed / MANAGED_FILES_NAME).is_file():
            raise ValueError("macOS application bundle inventory unavailable")
        # Reserve the new user-visible name EXCLUSIVELY before publication,
        # rather than relying on POSIX rename() (which may replace an existing
        # empty directory). An interrupted, newly reserved destination is
        # retained for explicit review and is NEVER silently removed/reused.
        destination.mkdir(mode=0o700)
        os.rename(contents, destination / "Contents")
        # The TemporaryDirectory owns and cleans ONLY its private staging tree.
    return {
        "status": "native_macos_app_bundle_created",
        "bundle": str(destination),
        "entrypoint": "Contents/MacOS/Minglefield",
        "managedFileInventorySha256": inventory_sha,
        "codeSigningVerified": False,
        "finderUserAcceptanceVerified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = package_macos_app(args.source, args.output)
    except (OSError, ValueError, json.JSONDecodeError):
        print("native_macos_bundle_build_rejected", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
