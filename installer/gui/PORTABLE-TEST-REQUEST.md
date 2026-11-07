# M2.10/M2.11 — portable native application handoff acceptance (2026-11-07)

**Scope:** Explicitly requested next user-visible milestone acceptance package for Shadow.
The preceding M2.08 manually rejected Windows artifact remains REJECTED, not retroactively accepted.
This request is for a new disposable acceptance build of the current Tauri Setup Manager
with the independently executable OS-native Minglefield application included in its
inventoried managed Alpha payload. No production release, branch merge or deployment.

**Milestone/subgoal:** M2.10 native application and M2.11 first-run + independent app launch.
**Source branch:** `feat/game-integration-updates`
**Reviewed implementation HEAD before retry marker:** `2cc12264b405b9b49a55f16fa272e03a92932c87`
**Actual packaging SHA:** the marker commit that changes this file; record it from GitHub Actions,
not the preceding implementation SHA.
**Reason for new portable packages:** The currently approved M2.11 runtime handoff has
no downloadable artifact at the new implementation SHA. Earlier portable packaging built
a runtime-only managed Alpha payload and omitted native `Minglefield.exe`.
The packaging workflow now compiles and inventories the OS-native Minglefield executable
on each platform, pins the resulting inventory digest into Tauri, checks the native
program before packaging and independently verifies the re-downloaded Windows artifact.

## Failed first attempt and bounded repair retry

The first requested acceptance build [42409532310](https://github.com/daresan/Minglefield/actions/runs/42409532310)
failed **Windows** during native application packaging, before upload:
`native_minglefield_application_build_rejected`. The native builder intentionally
suppresses arbitrary Cargo stderr, so that outcome alone cannot classify the Windows
compiler/linker cause. The only repair is to expose the **same pinned release Cargo build**
as a separate CI step with ordinary compiler diagnostics before rerunning the unchanged
native runtime builder. No security checks were removed, no binaries replaced, and no
publisher trust relaxed. This marker is explicitly the **failed-build repair retry**
per MDCI T4; it is not an extra feature-acceptance milestone. The retry must still
pass all three OS jobs and Windows upload/re-download integrity verification.
No prior artifact is accepted, and this retry must not be treated as a release.

## Completed required engineering CI (MDCI T1–T3)

- [Installer Rust / Ubuntu 42407238263](https://github.com/daresan/Minglefield/actions/runs/42407238263):
  **success**, real encrypted local Host setup, independent native app process survives CLI exit
  and answers HTTP on loopback.
- [Native Security / Windows + macOS 42407238244](https://github.com/daresan/Minglefield/actions/runs/42407238244):
  **both success**, including real installed SQLCipher/Host startup and bounded runtime checks.
- [Tauri GUI native / Ubuntu 42407324302](https://github.com/daresan/Minglefield/actions/runs/42407324302):
  **success**, Rust backend command, session-bound approved paths and native start guard.
- [Installer GUI frontend 42407196354](https://github.com/daresan/Minglefield/actions/runs/42407196354):
  **success**, current-session and authorization response validation.
- [AGENTS Security Guard 42407835388](https://github.com/daresan/Minglefield/actions/runs/42407835388):
  **success**. The packaging-specific native binary inclusion is the new T4 check,
  not claimed as previously tested.

## Packaging acceptance gate

Trigger **once**, only via the existing `.github/workflows/installer-portable-milestone.yml`
path-scoped marker. The called `installer-tauri-packaging.yml` must produce:
`tauri-portable-windows-exe` (entire portable EXE and sibling `managed-alpha/` tree),
`tauri-portable-linux-appimage`, and `tauri-portable-macos-app`.
The Windows upload and its re-download must preserve hidden, empty and native executable files;
inventory verification cannot be weakened. Missing native Minglefield binary, incomplete
Python/SQLCipher runtime, failed bundle checksum or unavailable OS runner fails acceptance.
Do not trigger an NSIS/DEB, signed production release or automatic upgrade.

## Shadow manual positive cases (disposable testing only)

1. Download the Windows artifact **from this run**, extract the **entire** ZIP including
   all `managed-alpha/` contents beside `minglefield-installer-gui.exe`.
   Do not install Python, Node, Rust, Git or Conda on the test machine.
2. Select a disposable legacy Alpha SQLite/SQLCipher database with a separately verified
   independent backup. Confirm database contents and registered missing-schema changes;
   authorize an encrypted new destination with a strong SQLCipher key. The source,
   verified backup and independent existing applications remain unchanged.
3. Install the checked managed Alpha payload into a new path or allowed data coexistence
   directory, never overwriting existing application files. The destination must
   contain the exact inventory-pinned `Minglefield.exe` plus managed Python/SQLCipher.
4. If the migrated DB already has valid user identities/Host owners, preserve them
   without forcing a new `mingleadmin`, resetting passwords or minting Host authority.
   If identity/Host tables are genuinely empty, separately authorize one local
   `mingleadmin` using a distinct account secret and the original first-run worker.
5. Click the independent **Installierte Minglefield-Anwendung starten** control.
   The installed native application must start over `127.0.0.1`, open a browser
   only after readiness, accept normal existing/new account login and keep running
   after the portable Setup Manager is closed. Account login and Host scope must
   match the encrypted DB, not the installer login assumptions.
6. Record the version/ZIP, visible messages, port and observed results.
   Do not paste real credentials or session tokens into issue logs.

## Manual negative and preservation cases

- Tamper with or remove a required native managed file: installation/start must refuse;
  no silent source-file replacement, fallback to system Python or publisher-trust bypass.
- Wrong SQLCipher key, nonexistent native executable, missing backup or stale current-session
  proof must fail safely. A failed start must not consume an unrelated new Host claim.
- Existing/occupied destination or re-run of first-run must not overwrite/recreate
  existing DBs, owners, login verifiers, token state, remote Host grants or recovery receipts.
- Repeated click while starting must not spawn duplicate processes. Cancellation and
  recovery require explicit operator inspection, not automatic rollback.

**Known limitations and explicit gates:** This remains an unsigned Alpha preview.
Interactive Windows console-free native starter UX, macOS Finder signing/notarization,
Linux desktop integration, fully unified fresh/migrated Standard/Advanced/silent flows,
complete source-build support, and clean end-user release provenance still require
separate M2.10/M2.11/M2.14 acceptance. An engineering CI pass or artifact upload is
not maintainer acceptance. `full_installation_completed=false` remains binding.

**Maintainer acceptance:** PENDING real Windows Shadow results; none inferred from CI.
