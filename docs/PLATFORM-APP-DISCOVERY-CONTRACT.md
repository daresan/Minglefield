# Platform app discovery — next implementation contract

Scope: **Minglefield application itself**, never third-party community games. Read [binding boundary](PLATFORM-VS-GAME-INSTALLATION-BOUNDARY.md).

## Existing behavior

The shared Rust installer core recognizes an explicitly selected Minglefield **source checkout** using conservative project structure and README markers. The Tauri GUI offers a manual directory inspection. The result is read-only, with `provenance_verified=false` and `launch_ready=false`. No installation or automatic scanning is implemented.

## Next increment: installed application recognition

Recognize a **packaged Minglefield application** independently from a source checkout. A directory with a plausible executable name alone must **not** be considered a verified installation. Before enabling automatic reuse, update or repair, define and ship a versioned *application-owned installation receipt* (distinct from a game manifest and distinct from a GitHub Actions package artifact). The receipt should bind the application product identifier, version, platform/architecture, installation scope, installed entrypoint, and installation ownership to a verified release or explicit user-approved fork. Validate receipt parsing and supported versions; verify entrypoint containment and the expected on-disk identity. A locally editable receipt by itself is not cryptographic provenance.

Provide distinct states: `source_checkout`, `packaged_app_candidate`, `verified_installed_app` (only after actual verification), `unrecognized`, and `conflict`. Never conflate an installed **Tauri Setup Manager** (product identifier `org.minglefield.installer`) with the **Minglefield application**.

## Discovery order

1. Check the selected install destination and known application registration/receipt paths for the current OS, without modifying them.
2. Inspect per-user OS locations; consider system-wide locations for **existing** installs, but never require administrator rights merely to inspect.
3. Support explicit manual selection when the installation is elsewhere.
4. Keep source checkout and packaged app results separate if both exist; require user choice before any action.
5. Preserve persistent data separately from program files. Detection must not overwrite or delete either.

## Required tests before activation

- Windows per-user and existing system-wide locations, macOS app bundles, Linux user/system package layouts.
- Source checkout without `.git` or executable; packaged app without repository; both in the same area; unrelated files and fake executable names.
- Missing, malformed, unsupported, spoofed or tampered receipt; symlinks/path escapes; cross-platform architecture mismatch.
- Setup Manager installed but Minglefield application absent: report **not installed**, not a successful application detection.
- Read-only behavior, no Host claims, no optional runtime installations and no game integration policy dependencies.
- CI Rust tests on all three operating systems, plus packaged end-to-end installation/recognition tests before claiming production readiness.

**No permission to enable execution:** this document is a contract for the next increment, not evidence that packaged application recognition or verified provenance already exists.
