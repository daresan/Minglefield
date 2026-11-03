"""Explicit, cross-platform Minglefield alpha environment bootstrap.

Use a chosen Python 3.10+ interpreter; never modify the invoking environment.
This is not a standalone Python installer or a production platform updater.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv


def environment_python(target):
    if os.name == "nt":
        return target / "Scripts" / "python.exe"
    return target / "bin" / "python"


def prepare_target(target):
    """Refuse unknown directories and symlink targets before any mutation."""
    if target.is_symlink():
        raise ValueError("Refusing symlink environment target")
    if target.exists():
        if not target.is_dir():
            raise ValueError("Environment target is not a directory")
        interpreter = environment_python(target)
        if not (target / "pyvenv.cfg").is_file() or not interpreter.is_file():
            raise ValueError("Existing target is not a recognized Python virtual environment")
        return False
    if target.parent != target and not target.parent.is_dir():
        raise ValueError("Parent directory must already exist")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path,
                        help="New or existing dedicated Minglefield virtual environment")
    parser.add_argument("--install-ci", action="store_true",
                        help="Explicitly install only requirements-ci.txt (not full runtime)")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 10):
        parser.error("Python 3.10 or newer is required")
    root = Path(__file__).resolve().parents[1]
    target = args.target.absolute()
    if target == root or target == root.parent or target == Path(target.anchor):
        parser.error("Refusing repository, its parent, or filesystem root as environment")
    try:
        create = prepare_target(target)
    except ValueError as exc:
        parser.error(str(exc))
    if create:
        print("Creating isolated virtual environment:", target, flush=True)
        venv.EnvBuilder(with_pip=True, clear=False, symlinks=False).create(target)
    else:
        print("Using existing virtual environment:", target, flush=True)
    python = environment_python(target)
    if not python.is_file():
        parser.error("Virtual environment interpreter was not created")
    print("Minglefield interpreter:", python, flush=True)
    if args.install_ci:
        requirements = root / "requirements-ci.txt"
        if not requirements.is_file():
            parser.error("requirements-ci.txt not found")
        print("Installing conformance dependencies only:", requirements, flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "-r",
                        str(requirements)], check=True)
        subprocess.run([str(python), "-B",
                        str(root / "scripts" / "minglefield_platform_preflight.py")],
                       check=True)
    else:
        print("No packages installed; pass --install-ci to opt in.")
    print("Host runtimes, user data, databases and Git were not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
