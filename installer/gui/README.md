# Tauri 2 installer GUI — non-installing proof of concept

This GUI calls the existing Rust `minglefield-installer-core::plan` function, the same one used by `installer-cli`. It only previews plans. It does not copy files, download dependencies, verify release provenance, install runtimes, authenticate, or claim Hosts. Do not distribute as a functional installer.

On a trusted developer workstation with Node.js/npm, Rust and Tauri OS prerequisites:

```powershell
cd installer/gui
npm.cmd ci
npm.cmd run dev
```

This is a development command, **not** an end-user prerequisite. Do not commit `node_modules` or `src-tauri/target`. On Shadow PowerShell use `npm.cmd` to avoid the blocked `npm.ps1` shim without changing execution policy. Before release, establish a fully offline verified asset/build pipeline and test the packaged entrypoints on supported operating systems. The npm and Cargo lockfiles are already tracked and native preview packaging is now exercised in CI. The workspace root `installer/Cargo.toml` deliberately excludes this separate Tauri crate for now, so existing Rust CI remains independent of Tauri OS prerequisites.

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

Both `package-lock.json` and `src-tauri/Cargo.lock` are tracked. CI installs frontend dependencies with `npm ci` and checks, lints and tests the Tauri Rust backend using Cargo `--locked`. This fixes dependency resolution, but does **not** establish bit-for-bit reproducible binaries or verified artifact provenance. This job checks compilation, **not** native installation or GUI interaction. The separate `Tauri native package smoke builds` workflow produces unsigned, non-released `.exe` (NSIS), `.deb`, and `.dmg` preview packages on Windows, Ubuntu and macOS. These packages are not yet a functional Minglefield installer; creating a bundle does not verify install, launch, upgrade, removal or OS trust prompts.

## Bundled framework license preview

The setup-manager GUI now exposes the complete root `LICENSE` text as a read-only, accessible panel. The Tauri Rust backend embeds that file at compile time and returns it via `framework_license`; a Rust regression test checks its identity and completeness. The preview does not require a network request or assert acceptance, and it does not grant consent for marketplace services or installation writes. The GUI is still plan-only. When building the GUI outside the repository layout, the root `LICENSE` file must be available at the expected relative path; packaged binaries embed the text and do not need that source file at runtime.

## Standard and Advanced setup preview

The **Standard** view is selected by default and submits the Rust backend's per-user OS defaults to the shared `preview_install_plan` command. The **Advanced** view exposes custom install/data directories or the existing versioned `key=value` configuration editor (v1/v2). Switching back to Standard ignores hidden advanced values; it does not authorize optional components. Both routes remain strictly plan-only (`executionEnabled: false`). GUI acceptance of a preview does not constitute an installation or license/marketplace consent. Native packaged GUI smoke tests and a manual switch-mode test remain necessary after this change.
