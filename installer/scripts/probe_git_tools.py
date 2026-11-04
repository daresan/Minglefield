"""Read-only, opt-in local Git / GitHub CLI capability probe.

This probes ONLY the machine on which it is invoked. It does not authenticate,
install software, contact GitHub, or inspect stored credentials.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

TOOLS = {"git": ("--version",), "gh": ("--version",)}
MAX_OUTPUT = 512


def probe(tool, *, which=shutil.which, runner=subprocess.run):
    if tool not in TOOLS:
        raise ValueError("unsupported tool")
    executable = which(tool)
    if not executable:
        return {"tool": tool, "state": "missing", "version": None}
    path = Path(executable)
    if not path.is_absolute() or not path.is_file():
        return {"tool": tool, "state": "unverified", "version": None}
    try:
        result = runner(
            [str(path), *TOOLS[tool]],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
            env=os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {"tool": tool, "state": "unverified", "version": None}
    if result.returncode != 0:
        return {"tool": tool, "state": "unverified", "version": None}
    first_line = (result.stdout or "").splitlines()
    version = first_line[0][:MAX_OUTPUT] if first_line else ""
    if not version or not version.lower().startswith(tool + " version"):
        # Git prints 'git version ...'; gh prints 'gh version ...'.
        return {"tool": tool, "state": "unverified", "version": None}
    return {"tool": tool, "state": "available", "version": version}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = {
        "schema_version": 1,
        "scope": "local_machine_only",
        "authentication_checked": False,
        "installation_performed": False,
        "tools": [probe(tool) for tool in ("git", "gh")],
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for item in result["tools"]:
            print(item["tool"] + ": " + item["state"] +
                  (" (" + item["version"] + ")" if item["version"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
