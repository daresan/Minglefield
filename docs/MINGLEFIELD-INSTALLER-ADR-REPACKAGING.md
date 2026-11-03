# ADR: Repackagable Minglefield Alpha distribution contract

Status: **proposed for Gate 2 implementation**, 2026-11-03. No installer technology, release tag or distribution signing key is selected yet.

## Decision context

The first product to install is the **current local Minglefield Alpha**, not a hypothetical production server. Its Python gateway is experimental; first-run onboarding must disclose this. The same installer implementation must accept new releases by repackaging their payloads and metadata, rather than modifying UI/business logic per version. The official Marketplace is not implemented and is outside this repository and distribution; no 5% transaction code is part of the installer. Host job approval rules are outside installer scope.

## Proposed package boundaries

1. **Payload**: OS/architecture-specific app files and isolated Python runtime with complete runtime dependencies. Read-only at runtime; no mutable SQLite state inside payload.
2. **Release manifest**: declarative identity, channel/version, target OS/CPU, entrypoint, hashes, runtime dependency lock reference, data compatibility/migrations, licensing notices, and release provenance. Manifest does not contain credentials or machine-specific paths.
3. **Installer engine**: release-independent detect/verify/stage/activate/rollback/repair/uninstall operations. OS-specific GUI is a frontend; installation semantics live in a tested engine.
4. **Per-user state**: accounts, Host ownership, SQLite, runtime connections, logs, user assets and consent records persist across upgrades; never included in the replaceable payload.
5. **First-run application**: authenticates user and provisions *only* the local Host with a reviewed one-time proof; does not alter job policies.

## Candidate manifest shape (not a signed release yet)

```json
{
  "format_version": 1,
  "product_id": "org.minglefield.app",
  "release": {"version": "0.1.0-alpha.1", "channel": "alpha"},
  "target": {"os": "windows", "arch": "x86_64"},
  "payload": {
    "entrypoint": "Minglefield.exe",
    "files_manifest": "payload-files.sha256",
    "files_manifest_sha256": "<64 lowercase hex characters>"
  },
  "runtime": {
    "kind": "bundled-python",
    "python_version": "<resolved-version>",
    "lockfile": "runtime-lock.json",
    "lockfile_sha256": "<64 lowercase hex characters>"
  },
  "data": {
    "schema_version": "<current-schema-version>",
    "minimum_compatible_schema": "<minimum-supported-version>",
    "migration_manifest": null
  },
  "legal": {
    "license_manifest": "licenses.json",
    "license_manifest_sha256": "<64 lowercase hex characters>"
  },
  "provenance": {
    "source_revision": "<full-commit-sha>",
    "build_id": "<ci-build-identity>",
    "signature": "<verified-signature-or-attestation-reference>"
  }
}
```

The placeholders above are illustrative only. No value is evidence of a real artifact, hash, release, migration or signature. A complete schema and canonical serialization/signature envelope are required before using this manifest for verification. Release signature verification must anchor to trusted publisher keys outside the untrusted downloaded manifest; a self-declared signature is insufficient. The files manifest must cover *every* executable and supporting payload file, and reject path traversal, symlinks escaping the install root and unexpected files.

## Atomic lifecycle contract

1. Detect installed app via verified identity, and source checkout separately via source structure; discovery is non-mutating.
2. Download or select candidate artifact; verify trusted release provenance and full file hashes **before** executing any downloaded code.
3. Stage in a new versioned directory on the same filesystem; validate architecture, bundled runtime and launch readiness without touching live state.
4. Back up persistent data before migrations; perform compatible migration with recovery plan. Never claim rollback if a schema migration is irreversible.
5. Atomically switch active version pointer only after checks; on launch failure restore the previous compatible version, report diagnostics and retain user data.
6. Repair replaces only verified app payload, not user data or Host ownership. Uninstall removes app files only by default; optional user-data removal requires separate explicit consent.

On Windows default to `%LOCALAPPDATA%\\Programs\\Minglefield` and data `%LOCALAPPDATA%\\Minglefield`, without elevation. macOS/Linux paths and legacy migration need an explicit OS design. Port collision and unrelated local process identity must fail closed.

## Gate 2 implementation comparison (pending proof of concept)

| Candidate | Advantages | Risks to test |
| --- | --- | --- |
| Native OS installer + bundled Python app | Familiar OS install experience, no system Python, platform-native update/signing options | Three installer recipes; shared lifecycle logic must remain identical |
| Cross-platform desktop shell + local Python backend | One GUI implementation, window/process integration | Added runtime size, signing complexity, local IPC/security boundary |
| Python GUI + freezing/bundling | Reuses Python stack, possible simpler prototype | OS packaging, macOS notarization, Python dependency/data inclusion, secure update UX |

Evaluate Windows per-user no-elevation, macOS signing/notarization, Linux desktop integration, artifact provenance, dependency closure, upgrade rollback, clean-machine install and accessibility. **Do not select a toolkit by popularity alone.**

## Gate 2 technology direction and Shadow toolchain evidence (2026-11-03)

**Preferred implementation direction, pending packaged proof of concept:** one shared Tauri 2 GUI across Windows, macOS and Linux, backed by a reusable Rust installer engine and Rust CLI for unattended operation. The GUI and CLI must share configuration validation, trust verification, installation lifecycle and security policy. Produce separate OS/architecture-specific installer artifacts; neither end-user GUI nor CLI may require preinstalled Rust, Python, Git or Conda. Qt 6 remains the fallback candidate for comparison and a possible future Minglefield desktop application; no decision to rewrite the current Python Alpha in Rust is implied. The binding functional requirements, including silent/default configuration and local Host authorization, remain in `docs/MINGLEFIELD-INSTALLER-AND-ONBOARDING-PHASE.md`.

**Observed on the developer's Shadow Windows workstation (not a supported-user prerequisite or release build verification):**

- `rustc --version`: `rustc 1.99.1 (58cf8f9c3 2026-10-13)`
- `cargo --version`: `cargo 1.99.1 (5f94df478 2026-08-27)`
- `rustup show`: default host `x86_64-pc-windows-msvc`; active/default toolchain `stable-x86_64-pc-windows-msvc`; installed target `x86_64-pc-windows-msvc`.

This confirms the Rust toolchain is available for local Windows development; it **does not** establish that Tauri's Windows prerequisites, webview, frontend dependencies, linker, macOS/Linux targets, or packaged GUI/CLI builds are ready. Verify those separately. Introduce Rust CI gates for `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test`, and `cargo check --locked`, with per-platform release builds and dependency/license auditing as the implementation matures. macOS runner availability is a separate unresolved CI infrastructure issue.

## Mandatory next deliverables

- Machine-checkable release-manifest schema and fixture tests (positive, missing hash, path traversal, wrong OS/arch, untrusted provenance).
- Exhaustive reachable-runtime import inventory and per-OS resolved dependency locks; clean-room Alpha startup.
- Prototype launcher with structured readiness and failure states, no shell/Python prerequisite.
- Compare two installer candidates on Windows/macOS/Linux in CI and record the evidence.
- Legal/license notice review before public binary redistribution. GPL-3.0-or-later is a proposed Minglefield core direction, not yet applied to all files.

## Out of scope

Third-party game installation, Marketplace/backend billing, Host job scheduling/approval policy, automatic acquisition of ComfyUI models or extensions, and production-grade remote gateway claims.
