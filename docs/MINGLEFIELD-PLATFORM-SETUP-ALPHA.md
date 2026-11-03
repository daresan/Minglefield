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

`scripts/minglefield_platform_preflight.py` checks the selected
interpreter, its Python version and declared conformance package constraints. It never installs dependencies, modifies
a database, launches the gateway, or changes Git state.

Run from repository root:

```powershell
$mfPython = $env:MINGLEFIELD_PYTHON
& $mfPython -B scripts/minglefield_platform_preflight.py
```

The user must select the interpreter explicitly. The Python entry point avoids PowerShell script execution-policy restrictions. A failing preflight must not trigger an implicit installation.

## Second deliverable: isolated Python environment bootstrap (alpha)

`scripts/minglefield_environment.py` uses only the Python standard library and
runs on Windows, Linux and macOS. It **requires a deliberately selected Python
3.10+ interpreter** and therefore does not yet solve first-time Python runtime
installation. It refuses unrecognized existing targets and does not modify
Conda base or another selected Python installation.

From the repository root, with the existing confirmed interpreter:

```powershell
$mfPython = $env:MINGLEFIELD_PYTHON
& $mfPython -B scripts/minglefield_environment.py --target "$env:LOCALAPPDATA\\Minglefield\\venv" --install-ci
```

For Linux/macOS, use the selected Python executable and a user-owned target
path (for example `$HOME/.local/share/minglefield/venv`); the target parent
must exist. Without `--install-ci`, the script only creates/reuses the virtual
environment. With it, it installs **conformance dependencies only** and runs
the preflight; it does not claim the gateway runtime is fully provisioned.
It does not install ComfyUI, migrate databases, change Git, or restart services.

## Next implementation slices (not yet delivered)

1. Inventory actual gateway runtime imports and optional integrations;
   distinguish mandatory and optional packages.
2. Define complete runtime dependency declarations and install them into
   the dedicated environment; design a first-install Python acquisition path.
3. Idempotent platform update with preflight, backup of persistent state,
   migration policy, failure reporting and operator-controlled restart.
4. Cross-platform support after Windows alpha behavior is verified.

**No production installer or updater is claimed by this document.**
