"""Read-only preflight for the Minglefield platform Python environment.

Run with the explicitly selected interpreter:
    <minglefield-python> -B scripts/minglefield_platform_preflight.py

This does not install packages, change databases or start services.
"""
import importlib.metadata
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    requirements = root / "requirements-ci.txt"
    print("Interpreter:", sys.executable)
    print("Python:", sys.version.split()[0])
    if sys.version_info < (3, 10):
        print("FAIL: Python 3.10+ is required.", file=sys.stderr)
        return 1
    if not requirements.is_file():
        print("FAIL: requirements-ci.txt is missing.", file=sys.stderr)
        return 1
    try:
        from packaging.requirements import Requirement
    except ImportError:
        print("FAIL: packaging is missing; no changes made.", file=sys.stderr)
        return 1
    failed = False
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            requirement = Requirement(line)
            if requirement.marker and not requirement.marker.evaluate():
                continue
            version = importlib.metadata.version(requirement.name)
            valid = version in requirement.specifier
            print(f"{'OK' if valid else 'FAIL'}: {requirement} (installed {version})")
            failed |= not valid
        except (importlib.metadata.PackageNotFoundError, ValueError) as exc:
            print(f"FAIL: {line} ({exc})")
            failed = True
    if failed:
        print("FAIL: conformance dependencies missing or incompatible; no changes made.")
        return 1
    print("OK: conformance dependency preflight (runtime inventory still pending).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
