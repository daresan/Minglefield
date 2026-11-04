"""Read-only source audit of external executable invocation sites.

This scans syntax; it never executes application code, git, gh, or subprocesses.
Matches are candidates for review, not proof of runtime dependency.
"""
import argparse
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
EXECUTABLES = frozenset(("git", "gh"))
CALL_NAMES = frozenset(("run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput", "system", "execv", "execve", "spawnv", "spawnve", "which"))


def scan(root):
    root = Path(root)
    findings = []
    errors = []
    for path in sorted((root / "server").glob("*.py")) + sorted((root / "scripts").glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append({"file": path.relative_to(root).as_posix(), "error": str(exc)})
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                node.func.id if isinstance(node.func, ast.Name) else None
            )
            if name not in CALL_NAMES:
                continue
            strings = []
            for arg in node.args:
                for part in ast.walk(arg):
                    if isinstance(part, ast.Constant) and isinstance(part.value, str):
                        strings.append(part.value)
            tools = sorted({tool for tool in EXECUTABLES if any(
                value == tool or value.startswith(tool + " ") or
                value.endswith("/" + tool) or value.endswith("\\" + tool)
                for value in strings
            )})
            if tools:
                findings.append({
                    "file": path.relative_to(root).as_posix(),
                    "line": node.lineno,
                    "call": name,
                    "tools": tools,
                })
    return {
        "schema_version": 1,
        "findings": findings,
        "errors": errors,
        "executable_dependencies_verified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = scan(args.root)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for item in result["findings"]:
            print("{file}:{line} {call} -> {tools}".format(**item))
        print("Source audit only; executable dependencies are NOT verified.")
    return 3 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
