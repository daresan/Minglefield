# Alpha runtime dependency discovery

The initial packaging target is the local Python-backed Alpha gateway. This is a **source-level discovery step**, not a product dependency lock or a finished standalone executable.

Run:

```powershell
python -B installer/scripts/audit_alpha_runtime_imports.py --json
```

The auditor walks the transitive static import graph starting from `server/private_alpha_gateway.py`, follows imports resolved to local `server/*.py` modules, classifies imports against the running interpreter's standard library, records external top-level imports with their importing modules, and flags obvious dynamic import sites for review. It is side-effect-free and uses only the Python standard library. It neither imports nor executes application code.

Known external imports from the earlier source inventory include `jsonschema` and `packaging`; the graph may discover additional dependencies. The existing `requirements-ci.txt` ranges (`jsonschema>=4.18,<5`, `packaging>=24,<27`) are not a runtime lock.

**Important limitations:** AST scanning does not prove a module is executed, does not resolve optional import paths, namespace packages, platform-specific native modules, indirect imports from third-party wheels, runtime import hooks or all string-based dynamic loading. It does not establish transitive wheel hashes or Python interpreter provenance. The JSON field `runtime_lock_verified=false` is always false.

Next acceptance gates: review dynamic/optional import sites; classify required versus feature-optional packages; resolve and pin transitive runtime dependencies for each supported platform/Python version; build a self-contained Python runtime/package without requiring Python on the user's machine; perform clean-machine startup and representative feature tests. The final LICENSE and release provenance gates remain separate and mandatory.
