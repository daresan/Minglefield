# M2.06 — explicitly approved portable Alpha GUI acceptance build

**Requested:** 2026-11-06 by the maintainer for `feat/game-integration-updates`.
**Implementation baseline:** `b48af02fc8d4e894b976c8d7d7b6a8bd66da0384`.
**Build provenance:** the commit that updates THIS marker (record the
actual GitHub Actions run's checkout SHA, not merely the baseline above).
**Scope:** ONE Windows portable EXE, ONE Linux AppImage and ONE macOS app
artifact matrix through `.github/workflows/installer-portable-milestone.yml`.
No release publication, merge to main, or production installation.
Ordinary implementation commits must not trigger portable packages.

## Purpose

Manually accept the newly wired, **explicitly consented, backup-verified
experimental SQLCipher database-copy action** on the portable Tauri
Setup Manager's final Review page. This is deliberately a narrower
Alpha acceptance than complete durable migration or application install.

## Existing T1–T3 evidence

- [Ubuntu Installer Rust checks](https://github.com/daresan/Minglefield/actions/runs/42164302911)
  — encrypted source rekey, genuinely separate backup, hardlink-alias denial,
  mismatched backup, exact consent, wrong old password and Rust/Python
  published-ciphertext interoperability.
- [Windows/macOS native security checks](https://github.com/daresan/Minglefield/actions/runs/42164302887)
  — same sensitive core path and negative-control tests.
- [Ubuntu Tauri GUI native checks](https://github.com/daresan/Minglefield/actions/runs/42164244929)
  — backend compilation and Tauri command tests, including immediate
  rejection of absent backup or incorrect approval.
- [GUI frontend checks](https://github.com/daresan/Minglefield/actions/runs/42164005361)
  and [subsequent frontend checks](https://github.com/daresan/Minglefield/actions/runs/42164005361)
  — review eligibility and exact confirmation.
- The final source SHA's [AGENTS security guard](https://github.com/daresan/Minglefield/actions/runs/42164302823)
  is green.

These tests are prerequisites, **not** proof that a downloaded portable
GUI behaves correctly on a real Windows/Linux/macOS desktop.

## Strict operator prerequisites

1. For first acceptance use a **disposable representative source** and
   a separately created, independently readable source backup. For any
   later test using real Alpha data, stop the Alpha application, independently
   secure its data and review the explicitly documented Alpha-only risks.
2. Select an unused absolute destination filename, preferably in a new,
   existing test directory. NEVER select the Alpha source file, an existing
   file, a shared/unknown directory, or a SQLite WAL/SHM/journal filename.
3. Do not share old/new SQLCipher passwords, sensitive rows, auth tokens
   or the full content of a real database in GitHub issue comments or logs.
4. This is an **unsigned/non-production** portable Setup Manager. It does
   not install Minglefield, initialize `mingleadmin`, claim a Host,
   or establish a crash-durable/hostile-path-safe release migration.

## Manual M2.06 Alpha test acceptance — Shadow first

1. Download the newly generated `tauri-portable-windows-exe` artifact
   from THIS marker's workflow run, extract it into a fresh directory,
   and launch `minglefield-installer-gui.exe` on Shadow.
   Cross-check the run's source SHA and artifacts; do not use an older ZIP.
2. Confirm all six wizard pages still work and the existing Standard and
   Advanced paths, Login/Hosts/Effects/Jobs/Games database review, staged
   edits, source inspection, and new database-password entry are intact.
3. Select/inspect the **stopped test** Alpha SQLite/SQLCipher source,
   validate the full stored schema and row review. Stage at most one
   harmless test edit, if desired. Preserve all source bytes.
4. Select an existing destination directory and a **new filename**.
   Run the complete in-memory migration rehearsal and then the temporary
   encrypted-copy test using the password already entered in the wizard.
   Verify both succeed with full record/schema equality, wrong-key
   rejection and temporary cleanup; neither should create the destination.
5. On the final Review page choose the **existing, separately copied,
   independently verifiable backup** and type exactly
   `CREATE EXPERIMENTAL ENCRYPTED COPY`. Trigger the new experimental
   database-copy action once. It should truthfully report
   `status=experimental_encrypted_copy_created`,
   `destinationCreated=true`, `encryptedDestinationVerified=true`,
   `backupVerified=true`, and the selected destination path.
   The general application installation and Host provisioning remain false.
6. Verify the encrypted file truly exists at the selected path, can be
   opened with the NEW SQLCipher key, rejects the wrong key, and contains
   expected source values, schema and staged edits. Original Alpha source
   and backup must be unchanged; no private staging files may remain.
7. On a fresh disposable input, explicitly check denial of missing/wrong
   confirmation, missing/nonmatching/hardlinked backup, stale data edits,
   inaccessible destination and already occupied destination names.
   Existing target bytes must remain unchanged. Do not put actual
   personal data in destructive/failure-injection scenarios.
8. Repeat on supported Linux/macOS desktops as available using this same
   commit's `tauri-portable-linux-appimage` and
   `tauri-portable-macos-app` outputs. Build success is not evidence
   of GUI-launch acceptance, and macOS unsigned app trust warnings may
   require normal operator review.

## Explicit limits and next action

- No automatic rollback or complete crash recovery is promised. A failure
  after final-name creation may leave a validated destination file; inspect
  it manually, never overwrite or automatically delete it.
- Concurrent adversarial directory replacement and parent-directory
  durability are still open before general release. This test is not
  a production installer migration guarantee.
- The local Host Admin / `mingleadmin` first-run setup and operational
  Python application payload remain separate pending milestones.
- Record the three GitHub job statuses, actual commit SHA, artifact names,
  exact manual observed outcomes, defects and operator acceptance.
- Do not initiate more portable builds automatically. Any repair build
  requires a documented failure and separate approved milestone request.
