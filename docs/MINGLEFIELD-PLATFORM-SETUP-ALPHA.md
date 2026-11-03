# Minglefield platform setup — alpha scope

This work concerns **Minglefield itself**, not the future game integration installer.

## Verified starting point

- The reference server uses Python 3.10+.
- `requirements-ci.txt` declares `jsonschema>=4.18,<5` and
  `packaging>=24,<27`; these are the conformance dependencies, **not**
  a proven exhaustive runtime dependency manifest.
- The local gateway can be launched with
  `<selected-python> -B server/private_alpha_gateway.py --auth-db <db> --port 8767`.
- A machine-specific `DEVELOPMENT.local.md` and `MINGLEFIELD_PYTHON` may
  identify the existing project interpreter. Do not silently use PATH Python,
  Conda base, or another project's environment.
- Host runtimes (such as ComfyUI) are independently configured per host.
  Do not install, move or overwrite them as an implicit platform dependency.

## First deliverable: non-mutating environment preflight

`scripts/minglefield-platform-preflight.ps1` checks the explicitly selected
interpreter, its Python version, declared conformance package constraints,
and pip dependency consistency. It never installs dependencies, modifies
a database, launches the gateway, or changes Git state.

Run from repository root:

```powershell
$env:MINGLEFIELD_PYTHON = "C:\\path\\to\\minglefield\\python.exe"
.\\scripts\\minglefield-platform-preflight.ps1
```

A failing preflight must not trigger an implicit installation.

## Next implementation slices (not yet delivered)

1. Inventory actual gateway runtime imports and optional integrations;
   distinguish mandatory and optional packages.
2. Explicit opt-in installation/update of Python dependencies into a
   dedicated Minglefield environment, never into an unselected interpreter.
3. Idempotent platform update with preflight, backup of persistent state,
   migration policy, failure reporting and operator-controlled restart.
4. Cross-platform support after Windows alpha behavior is verified.

**No production installer or updater is claimed by this document.**
