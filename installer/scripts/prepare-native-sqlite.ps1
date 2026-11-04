# Prepare native SQLite dependency in both installer Cargo lockfiles.
# Run from any directory on a workstation with Rust/Cargo installed.
# This script changes Cargo manifests/lockfiles only. It never opens user databases.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workspace = Join-Path $root "Cargo.toml"
$gui = Join-Path $root "gui/src-tauri/Cargo.toml"
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "Rust Cargo is required. Install the Rust toolchain before running this script."
}
Push-Location $root
try {
    cargo add --manifest-path "crates/installer-core/Cargo.toml" "rusqlite@0.32" --features bundled,backup
    if ($LASTEXITCODE -ne 0) { throw "cargo add failed" }
    cargo generate-lockfile --manifest-path $workspace
    if ($LASTEXITCODE -ne 0) { throw "workspace lockfile generation failed" }
    cargo generate-lockfile --manifest-path $gui
    if ($LASTEXITCODE -ne 0) { throw "GUI lockfile generation failed" }
    cargo check --manifest-path $workspace --workspace --locked
    if ($LASTEXITCODE -ne 0) { throw "workspace cargo check failed" }
    cargo check --manifest-path $gui --locked
    if ($LASTEXITCODE -ne 0) { throw "GUI cargo check failed" }
    Write-Host "SQLite dependency and both lockfiles prepared; no user database accessed."
    git status --short
}
finally {
    Pop-Location
}
