# Read-only Minglefield platform environment preflight.
# Never selects PATH Python or installs packages.
[CmdletBinding()]
param(
    [string]$Python = $env:MINGLEFIELD_PYTHON
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if ([string]::IsNullOrWhiteSpace($Python)) {
    throw 'Set MINGLEFIELD_PYTHON to the explicit Minglefield project interpreter.'
}
if (-not [System.IO.Path]::IsPathRooted($Python)) {
    throw 'MINGLEFIELD_PYTHON must be an absolute interpreter path.'
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Minglefield interpreter not found: $Python"
}
$requirements = Join-Path $repoRoot 'requirements-ci.txt'
if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) {
    throw 'Missing requirements-ci.txt in repository root.'
}
$code = @'
import importlib.metadata as metadata
import pathlib
import sys

print("Interpreter:", sys.executable)
print("Python:", sys.version.split()[0])
if sys.version_info < (3, 10):
    sys.exit("ERROR: Minglefield requires Python 3.10 or newer.")
try:
    from packaging.requirements import Requirement
except ImportError:
    sys.exit("ERROR: packaging is missing; no packages were installed.")
requirements = pathlib.Path(sys.argv[1])
failed = False
for raw in requirements.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    try:
        req = Requirement(line)
        if req.marker and not req.marker.evaluate():
            continue
        version = metadata.version(req.name)
        ok = version in req.specifier
        print(("OK" if ok else "FAIL") + ": " + str(req) + " (installed " + version + ")")
        failed |= not ok
    except (metadata.PackageNotFoundError, ValueError) as exc:
        print("FAIL: " + line + " (" + str(exc) + ")")
        failed = True
if failed:
    sys.exit("ERROR: declared conformance dependencies are missing or incompatible.")
'@
& $Python -B -c $code $requirements
if ($LASTEXITCODE -ne 0) {
    throw "Minglefield platform preflight failed (exit $LASTEXITCODE)."
}
Write-Host 'Minglefield platform preflight OK (read-only; runtime dependencies not yet fully inventoried).'
