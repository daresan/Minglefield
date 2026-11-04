# Shadow portable Setup Manager acceptance findings — 2026-11-04

Scope: **Minglefield platform application setup**, never community game installation. Observed on Windows Shadow using the portable preview executable. The user confirms the manager opens and the preview is promising, but the following are not accepted as complete.

## Immediate defects

1. Windows portable GUI first opens an unwanted black console window and the Tauri window appears behind it. Release build should use the Windows GUI subsystem, and the installer window must be foreground/focused on startup. Test the actual built EXE, not only Rust compile success. Check Linux/macOS startup behavior independently.
2. Bundled README still claimed `License selection is pending` despite the adopted GPL-3.0-or-later framework license. Fix the **canonical README**, not a GUI-specific string; add an embedded README regression assertion. License and README remain available offline on all setup pages.

## Required wizard and installation capability

3. Replace single-page plan preview with a real multi-step wizard with Back/Next, validation, state preservation and clear summary. Suggested sequence: Welcome + README/license; existing installation detection; Standard/Advanced + paths; required and optional components; local Host setup; review/consent; install/progress; result/launch. Do not require GPL acceptance or marketplace terms for GPL redistribution.
4. Show interactive optional component choices, not just a raw key=value editor. Detect/reuse existing Git, GitHub CLI (`gh`), Python, optional Conda, optional ComfyUI and optional **Blender**. Support explicit custom executable/runtime paths and per-host configuration; never hardcode ComfyUI to the setup machine. Offer install only after explicit user consent. Blender is an additional requested optional integration. No silent downloads or installations.
5. **Main blocking feature:** the Setup Manager must actually install the separate Minglefield application. Current `executionEnabled=false` means preview only; do not claim a working installer. Implement installation through the shared Rust core with verified selected application payload, staging, rollback/repair, persisted receipt, safe data handling, and first-run local Host provisioning. Never mistake the manager executable for an installed Minglefield application.
6. Preserve portable manager distribution on Windows, Linux, macOS; separate Linux terminal/CLI/Bash and native application package options remain planned. Apple signing/notarization explicitly out of scope until the maintainer asks.

## Order and acceptance gates

**A. Immediate:** README correction, Windows console suppression, embedded README regression test; CI formatting/build tests, then manual Shadow startup/foreground test.

**B. Wizard shell:** Back/Next step state, validation, accessible offline documents, separate Standard/Advanced modes, review screen. Unit tests and manual navigation test.

**C. Component selection:** existing installations and manual paths; Git/gh/Python/Conda/ComfyUI/Blender; explicit opt-in and shared core plan; tests for no hidden or silent provisioning.

**D. Real app install:** verified source/release payload, install/update/repair and Host setup with rollback and lifecycle tests on each OS. Remain preview-only until execution is actually safe and tested.

Never treat a green package smoke build as proof of startup focus or real installation. Maintain separate CI for platform installer and community games.
