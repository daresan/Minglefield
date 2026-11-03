"""Fail-closed, read-only readiness checks for a first Minglefield Alpha release.

This is NOT a package builder, license approval, or installer. It is safe to run
before the release license and product packaging are finalized.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MAX_DOCUMENT_BYTES = 1024 * 1024


def check_release_tree(root):
    root = Path(root)
    checks = []

    def record(name, ok, reason):
        checks.append({"check": name, "passed": bool(ok), "detail": reason})

    for filename in ("README.md", "LICENSE"):
        path = root / filename
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError("missing or symlinked document")
            if path.stat().st_size > MAX_DOCUMENT_BYTES:
                raise ValueError("document exceeds size limit")
            text = path.read_text(encoding="utf-8")
            if not text.strip():
                raise ValueError("empty document")
            if filename == "LICENSE" and "license selection is pending" in text.lower():
                raise ValueError("license still marked pending")
            record(filename, True, "present and readable")
        except (OSError, UnicodeError, ValueError) as error:
            record(filename, False, str(error))

    readme = root / "README.md"
    try:
        text = readme.read_text(encoding="utf-8")
        if "license selection is pending" in text.lower():
            record("license_status", False, "README still states that license selection is pending")
        else:
            record("license_status", True, "README no longer declares license pending")
    except (OSError, UnicodeError):
        record("license_status", False, "README not readable")

    # A conformance requirements file is not a product runtime lock.
    runtime_lock = root / "release" / "runtime-dependencies.lock"
    record(
        "runtime_dependency_lock",
        runtime_lock.is_file() and not runtime_lock.is_symlink() and runtime_lock.stat().st_size > 0,
        "product runtime lock must be present (CI requirements do not qualify)",
    )

    # Require an actual declared packaged product entrypoint, not a source checkout.
    launcher = root / "release" / "alpha-launch-contract.json"
    record(
        "packaged_launch_contract",
        launcher.is_file() and not launcher.is_symlink() and launcher.stat().st_size > 0,
        "versioned packaged launch contract required for Windows/macOS/Linux",
    )

    # No installable artifact is asserted by a successful source check.
    return {
        "schema_version": 1,
        "release_ready": all(check["passed"] for check in checks),
        "execution_enabled": False,
        "checks": checks,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = check_release_tree(args.root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        for check in result["checks"]:
            print(("[OK] " if check["passed"] else "[BLOCKED] ") + check["check"] + ": " + check["detail"])
        print("Release prerequisites: " + ("PASS" if result["release_ready"] else "NOT READY"))
    return 0 if result["release_ready"] else 3


if __name__ == "__main__":
    sys.exit(main())
