"""Static import-closure audit for the local Minglefield Alpha gateway.

Read-only, standard-library-only. A source import graph is NOT a verified runtime
dependency lock: conditional/dynamic imports and binary wheels need separate tests.
"""
import argparse
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = "private_alpha_gateway"


def audit(server_dir, entrypoint=ENTRYPOINT):
    server_dir = Path(server_dir)
    modules = {path.stem: path for path in server_dir.glob("*.py") if path.is_file()}
    if entrypoint not in modules:
        raise ValueError("entrypoint not found: " + entrypoint)
    visited = set()
    pending = [entrypoint]
    external = {}
    local_edges = {}
    errors = []
    dynamic_sites = []
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        path = modules[name]
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        except (OSError, UnicodeError, SyntaxError) as error:
            errors.append({"module": name, "error": str(error)})
            continue
        local = set()
        for node in ast.walk(tree):
            candidates = []
            if isinstance(node, ast.Import):
                candidates = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    errors.append({"module": name, "error": "relative import requires manual review"})
                    continue
                if node.module:
                    candidates = [node.module.split(".", 1)[0]]
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in (
                "__import__", "eval", "exec"
            ):
                dynamic_sites.append({"module": name, "line": node.lineno, "call": node.func.id})
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in (
                "import_module", "exec_module"
            ):
                dynamic_sites.append({"module": name, "line": node.lineno, "call": node.func.attr})
            for imported in candidates:
                if imported in modules:
                    local.add(imported)
                elif imported not in sys.stdlib_module_names and imported != "__future__":
                    external.setdefault(imported, set()).add(name)
        local_edges[name] = sorted(local)
        pending.extend(sorted(local - visited))
    return {
        "schema_version": 1,
        "entrypoint": entrypoint,
        "scanned_modules": sorted(visited),
        "local_edges": dict(sorted(local_edges.items())),
        "external_imports": {k: sorted(v) for k, v in sorted(external.items())},
        "dynamic_import_sites": sorted(dynamic_sites, key=lambda x: (x["module"], x["line"])),
        "errors": errors,
        "runtime_lock_verified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-dir", type=Path, default=ROOT / "server")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = audit(args.server_dir)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("Reachable local modules:", len(result["scanned_modules"]))
        for name, users in result["external_imports"].items():
            print("External import:", name, "(via " + ", ".join(users) + ")")
        print("Dynamic import sites:", len(result["dynamic_import_sites"]))
        print("Static import audit only; runtime lock is NOT verified.")
    return 3 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
