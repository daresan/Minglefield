# M2.08 — corrected portable Alpha setup acceptance, failed-build repair retest

**Reason for explicit repeat:** The previous M2.08 portable build
[42321392311](https://github.com/daresan/Minglefield/actions/runs/42321392311)
passed packaging but **FAILED** the real Windows Shadow operator acceptance
on 2026-11-07. This marker authorizes precisely ONE corrected repeat of that
failed user-visible subgoal, under the existing MDCI policy; do not interpret
prior packaging as user acceptance or trigger other portable workflows.

**Branch:** `feat/game-integration-updates`.
**Implementation HEAD accepted by development CI:** `d8cbf16d670cf09289867e9e575cc41480941db5`.
**Final reviewed documentation HEAD before marker:** `b952dcdba13d48ad1f1f619ac24ce80ceb900df1`.
**Actual portable build source:** this marker commit, with no further
implementation changes between code-gate verification and packaging.

## Completed required engineering gates

- [Ubuntu Installer Rust 42329523542](https://github.com/daresan/Minglefield/actions/runs/42329523542): success, including actual non-overwriting encrypted migration of an older Alpha DB missing a registered table, implicit SQLite index restoration, a preserved legacy extension row, an initially absent nested destination directory, and unchanged source plus independent backup.
- [Windows/macOS native security 42329523531](https://github.com/daresan/Minglefield/actions/runs/42329523531): both success for the same critical migration/path/SQLCipher code.
- [Ubuntu Tauri backend 42328609249](https://github.com/daresan/Minglefield/actions/runs/42328609249): success for the real embedded database-password check, one-time per-operation Host setup, verified bundled resource lookup (including sibling folder), and installing app files beside existing user database / in a new destination directory.
- [Frontend 42329309473](https://github.com/daresan/Minglefield/actions/runs/42329309473): success for the revised wizard; SQLCipher destination selection is accessible while the earlier rehearsal and temporary cipher tests are hidden behind optional developer diagnostics, not required to create the real destination.
- [AGENTS guard 42329892440](https://github.com/daresan/Minglefield/actions/runs/42329892440): success for the documented rejected manual test and corrective acceptance scope.

## Required portable artifacts and checks

Use only the existing `.github/workflows/installer-portable-milestone.yml`,
which calls `installer-tauri-packaging.yml` and builds **Windows,
Linux, macOS** without installing the portable manager. Confirm all three
jobs succeed and GitHub uploads all three non-expired artifacts, including
the Windows executable with its fully extracted sibling `managed-alpha/`,
Linux AppImage and macOS application archive. The actual operator test has
not passed until it is performed on Shadow; do not mark M2.08 done merely
because the build and uploads succeed.

## Focused M2.08 operator retest on disposable fixtures (no production data)

1. Download the **new** Windows artifact, extract the whole ZIP, start the
   Setup Manager with its sibling `managed-alpha/` folder. No developer
   Python, Git checkout, Conda, Cargo or earlier test databases required.
2. Select a disposable legacy Alpha SQLite database and independently
   verified separate backup; review staged changes. A new SQLCipher
   destination may have a yet-nonexistent nested parent directory and may
   use the *same basename* as its source if in a different directory.
3. Select any **registered missing schema objects** that actually apply to
   the disposable legacy DB. Set/confirm a strong destination SQLCipher
   password, select the fresh unoccupied target and explicitly authorize
   the real copy. Do **NOT** run either memory rehearsal or temporary
   SQLCipher test first. Source/backup bytes must remain unchanged.
4. Select an app install destination which either (a) does not exist yet,
   or (b) is the same existing data directory containing the **new**
   encrypted target DB, with no existing managed application files. The
   real app files must install without overwriting the DB or other files.
5. Choose default or another safe local administrator ID, use a separate
   confirmed sign-in password and explicit local Host consent. A wrong
   SQLCipher DB key must fail **before consuming** the permit. The correct
   key must allow the local-only owner account without a console invite,
   remote host claim or global admin rights.
6. Negative/retry case: a prior attempt in another occupied directory or
   an already-consumed operation must never overwrite that output; a
   **different fresh target and operation ID** can be tried in the **same
   manager process** without restarting it or deleting previous receipts.
7. On Linux/macOS verify that the same usable GUI paths and bundled
   managed runtime are present; packaging success is not GUI manual
   interaction acceptance.

**Security boundaries retained:** native source/backup integrity; explicit
consent for encrypted copy, separately verified app files and local Host
activation; independent SQLCipher and sign-in passwords; each operation
single-use; never automatically overwrite existing destinations, receipts,
source, backup or application files. No automatic crash recovery, general
repair/update, or installed application launch is claimed in this milestone.

**Known uncertainty:** the exact original Shadow text for the missing
schema/source-files error was not captured. The repaired embedded registered
schema and fallback to the verified packaged `managed-alpha` directory now
have code+CI coverage, but only a real Shadow retest can confirm the symptom
is gone. M2.08 acceptance remains **FAILED / pending owner retest**.
