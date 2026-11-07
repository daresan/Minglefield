"""Build the independently executable OS-native Minglefield Alpha payload.

This is the *developer/CI* build pipeline for M2.09/M2.10. A clean user's
machine never needs Cargo, Python, Conda, or the Setup Manager to launch the
resulting compiled Minglefield(.exe) with its managed runtime.
No source selection or third-party fork execution happens in this pipeline.
"""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

from build_managed_alpha_runtime import build_runtime

HERE = Path(__file__).resolve().parents[1]
TARGET = HERE / "target" / "release"


def native_executable_name():
    return "Minglefield.exe" if platform.system().lower() == "windows" else "Minglefield"


def build_native(output):
    executable = TARGET / native_executable_name()
    command = [
        "cargo", "build", "--release", "--locked",
        "-p", "minglefield-installer-cli",
        "--bin", "Minglefield",
    ]
    result = subprocess.run(
        command, cwd=HERE, capture_output=True, timeout=900, check=False,
    )
    if result.returncode != 0:
        # Do not forward arbitrary compiler diagnostics to end-user installer
        # surfaces. GitHub's normal compile step will show compiler diagnostics.
        raise ValueError("native Minglefield executable build rejected")
    if executable.is_symlink() or not executable.is_file():
        raise ValueError("OS-native Minglefield binary not produced")
    return build_runtime(output, native_app_executable=executable)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_native(args.output)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        print("native_minglefield_application_build_rejected", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
