"""Static import-closure inventory for the local Minglefield Alpha gateway.

Conservative audit aid, NOT proof that all dynamic/runtime dependencies are
bundled. Invoke: python -B scripts/platform_runtime_import_audit.py
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
ENTRY = SERVER / "private_alpha_gateway.py"


def audit(entry: Path, module_root: Path) -> dict:
    # Normalize both sides once: Windows CI temp roots may use 8.3 aliases.
    module_root = module_root.resolve(strict=True)
    pending = [entry.resolve()]
    visited = set()
    external = set()
    missing = set()
    dynamic = []
    edges = []
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        if not path.is_file() or not path.is_relative_to(module_root):
            raise ValueError("module outside audited source tree")
        visited.add(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    names = [node.module or ""]
                    dynamic.append({"file": path.name, "line": node.lineno,
                                    "kind": "relative-import-needs-review"})
                else:
                    names = [node.module] if node.module else []
            else:
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("__import__", "eval", "exec"):
                    dynamic.append({"file": path.name, "line": node.lineno,
                                    "kind": node.func.id})
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                    dynamic.append({"file": path.name, "line": node.lineno,
                                    "kind": "import_module"})
                continue
            for name in names:
                top = name.split(".")[0]
                candidate = module_root / (top + ".py")
                if candidate.is_file():
                    pending.append(candidate.resolve())
                    edges.append({"from": path.name, "to": candidate.name})
                elif (module_root / top / "__init__.py").is_file():
                    candidate = module_root / top / "__init__.py"
                    pending.append(candidate.resolve())
                    edges.append({"from": path.name, "to": candidate.relative_to(module_root).as_posix()})
                elif top in sys.stdlib_module_names or top == "__future__":
                    continue
                else:
                    external.add(top)
    return {
        "entry": entry.name,
        "local_modules": sorted(p.relative_to(module_root).as_posix() for p in visited),
        "third_party_candidates": sorted(external),
        "dynamic_import_review": sorted(dynamic, key=lambda d: (d["file"], d["line"], d["kind"])),
        "local_edges": sorted(edges, key=lambda d: (d["from"], d["to"])),
        "limitations": [
            "AST analysis does not prove optional runtime branches or plugin loading",
            "Third-party candidates must be mapped to distributions and per-OS locks",
            "Clean-room packaged startup and runtime instrumentation remain mandatory",
        ],
    }


def main() -> None:
    print(json.dumps(audit(ENTRY, SERVER), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
