# Tauri 2 installer GUI — non-installing proof of concept

This GUI calls the existing Rust `minglefield-installer-core::plan` function, the same one used by `installer-cli`. It only previews plans. It does not copy files, download dependencies, verify release provenance, install runtimes, authenticate, or claim Hosts. Do not distribute as a functional installer.

On a trusted developer workstation with Node.js/npm, Rust and Tauri OS prerequisites:

```powershell
cd installer/gui
npm.cmd install
npm.cmd run dev
```

This is a development command, **not** an end-user prerequisite. Do not commit `node_modules` or `src-tauri/target`. On Shadow PowerShell use `npm.cmd` to avoid the blocked `npm.ps1` shim without changing execution policy. Before release, pin dependencies with a lockfile, establish a fully offline verified asset/build pipeline, add platform packaging, and test the packaged entrypoints. The workspace root `installer/Cargo.toml` deliberately excludes this separate Tauri crate for now, so existing Rust CI remains independent of Tauri OS prerequisites.

Both GUI and CLI use the same Rust planning function, but this does not yet establish a common packaged executable or silent installation. Those are still required by the phase specification.

## Shared configuration preview

Both the GUI and unattended CLI validate the same Rust `InstallerConfig` (version 1). The GUI accepts either separate install/data paths or a versioned UTF-8 `key=value` preview. The CLI accepts `--silent --defaults` or `--silent --config FILE`, optionally with `--install-dir ABSOLUTE_PATH` as an explicit override. A portable config contains no machine-specific paths:

```text
version=1
install_optional_conda=false
install_optional_comfyui=false
explicit_optional_consent=false
```

`install_dir` and `data_dir` are optional; omitted paths are resolved from the current operating system's per-user defaults. Unknown/duplicate keys, unsupported versions, malformed booleans and unconsented optional installs are rejected. This is still a **non-installing plan preview**; do not confuse explicit optional consent with actual installation authorization. The format is intentionally a strict line-based configuration, not JSON. Future schema changes require a new version.

### Machine-readable unattended preview

Use `minglefield-installer-cli --silent --defaults --json` or `--silent --config FILE --json`. The CLI prints one JSON object to stdout on successful planning (`status=plan_only`, `exit_code=0`) or on argument/configuration failure (`status=error`, `exit_code=2` or `3`). The JSON schema is version 1, and `execution_enabled` is always false at this stage. Code 2 means invalid arguments; code 3 means unreadable/invalid configuration or rejected plan. No installation, Host claim, or application-data mutation occurs. Without `--json`, human-readable output remains available. This preview is not an installer execution API.

### Argument validation hardening

The unattended preview rejects repeated `--silent`, `--defaults`, `--json`, `--config`, or `--install-dir` flags with exit code 2. A value-taking option cannot silently consume a following `--flag` as its value. A deliberately malformed invocation fails before file access or planning. The `--json` output remains a read-only preview; this is not an installation execution entrypoint.

### Minglefield release provenance (no paid certificates)

This section concerns **installing Minglefield itself**, not the independent, stricter game-installation security rules.

- Official distribution: the public `daresan/Minglefield` repository and a release based on its protected `main` branch.
- Forks: a fork maintainer is the publisher of their own distribution; no approval or certificate from the original maintainer is required.
- No paid publisher certificates, commercial signing services, or platform code-signing subscriptions are required by Minglefield's own trust policy.
- An artifact manifest with SHA-256 checks file integrity, but not the connection to a GitHub commit. A trusted GitHub release and a reproducible or independently attested build provenance should connect the artifact to the chosen repository and commit using free mechanisms where practical.
- The `publisher::PublisherPolicy` placeholder currently rejects even checksum-valid artifacts with `RepositoryProvenanceUnavailable`, until repository/release provenance verification is implemented. This is **not** a demand for a paid signing certificate. No installation execution is enabled.

Platform packaging and OS security prompts must be documented honestly; Minglefield's own policy must not misrepresent operating-system trust requirements.

## Cross-platform GUI CI (initial smoke gate)

The `tauri-gui` job in `.github/workflows/installer-rust.yml` now runs on Windows, Ubuntu and macOS. It checks Tauri Rust formatting, compiles and lints the separate `src-tauri` crate, runs its Rust tests and builds the Vite frontend. Linux runners install the WebKitGTK 4.1 and related development libraries.

Both `package-lock.json` and `src-tauri/Cargo.lock` are tracked. CI installs frontend dependencies with `npm ci` and checks, lints and tests the Tauri Rust backend using Cargo `--locked`. This fixes dependency resolution, but does **not** establish bit-for-bit reproducible binaries or verified artifact provenance. The job checks compilation, **not** native bundles, installation or GUI interaction.
