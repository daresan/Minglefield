"""Read-only import-to-distribution inventory, not a release lock."""
import argparse
import importlib.metadata
import json
from pathlib import Path


def inventory(report, package_map):
    candidates = report.get("third_party_candidates")
    if not isinstance(candidates, list) or any(not isinstance(n, str) or not n for n in candidates):
        raise ValueError("invalid third_party_candidates")
    if len(candidates) != len(set(candidates)):
        raise ValueError("duplicate third_party_candidates")
    rows = []
    for name in sorted(candidates):
        distributions = sorted(set(package_map.get(name, [])))
        rows.append({"import": name, "distributions": distributions,
                     "status": "unresolved" if not distributions else
                               "ambiguous" if len(distributions) > 1 else "mapped"})
    return {"mapping_scope": "current_interpreter_only",
            "release_dependency_closure_verified": False,
            "imports": rows,
            "dynamic_import_review": report.get("dynamic_import_review", []),
            "limitations": [
                "Installed metadata is not a release dependency declaration",
                "Namespace packages and optional imports may be ambiguous",
                "Dynamic imports require separate review",
                "Per-platform locks and clean-room packaged startup remain required",
            ]}


def read_audit_json(path):
    """Accept UTF-8 and BOM-marked UTF-16 PowerShell redirection output."""
    raw = path.read_bytes()
    if raw.startswith((bytes((0xFF, 0xFE)), bytes((0xFE, 0xFF)))):
        return json.loads(raw.decode("utf-16"))
    return json.loads(raw.decode("utf-8-sig"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_json", type=Path)
    args = parser.parse_args(argv)
    report = read_audit_json(args.audit_json)
    print(json.dumps(inventory(report, importlib.metadata.packages_distributions()),
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
