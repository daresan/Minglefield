# M2.07 — explicitly requested portable Alpha recovery-inspection testbuild

**Request:** 2026-11-06 — maintainer requested continuation to the next testbuild.
**Source branch:** `feat/game-integration-updates`.
**Verified implementation HEAD before marker update:** `a74b3211e284bfb32e31227bcf930d9a14a28cbb`.
**Packaging source:** the *new commit updating this marker*, not the preceding HEAD.
**User-visible acceptance slice:** independent, strictly read-only recovery inspection on the Tauri Setup Manager Review page after a previously interrupted experimental SQLCipher copy.
**Build scope:** exactly one portable Windows EXE, Linux AppImage, macOS app matrix through the existing `installer-portable-milestone.yml` workflow; no automatic follow-on build or release.

## Relevant passing CI evidence

- [Installer Rust checks #533 (Ubuntu)](https://github.com/daresan/Minglefield/actions/runs/42300421292), implementation commit `8ce760bd801ff3fdfb72f8ac2ddb9a7d9f056b1f`: completed successfully.
- [Installer native security checks #54 (Windows/macOS)](https://github.com/daresan/Minglefield/actions/runs/42300421432), same core implementation: completed successfully.
- [Installer GUI frontend checks #17 (Ubuntu)](https://github.com/daresan/Minglefield/actions/runs/42299832280), recovery UI introduction: completed successfully.
- [Installer Tauri native checks #17 (Ubuntu)](https://github.com/daresan/Minglefield/actions/runs/42300707334), latest `a74b321`: completed successfully.
- [AGENTS security guard #704](https://github.com/daresan/Minglefield/actions/runs/42300707389), latest `a74b321`: completed successfully.

These are developer CI results, not OS desktop GUI acceptance. The packaging run must independently be checked for each OS job and each artifact.

## Manual acceptance: disposable data only

1. Download only the three artifacts from the **new marker-triggered run**; verify its checkout SHA and artifact names. On Shadow first launch the extracted Windows portable executable. Confirm the six wizard pages and already accepted schema/record review remain intact.
2. Use a disposable SQLite/SQLCipher test source, its separate independently verified backup and a previously unused absolute destination filename. Do not share database passwords or real records in logs.
3. Rehearse the migration, verify the temporary encrypted copy and create one explicitly approved encrypted target using the existing exact experimental consent phrase. Record the operation ID without exposing private file paths.
4. Close/relaunch Setup Manager, reselect the same source, backup, destination, keys, staged corrections and optional registered schema additions. On Review choose **Recovery-Zustand prüfen (nur lesen)**. It must report a distinct matching-published state and valid operation ID without writing, deleting, retrying, claiming a Host or installing the app.
5. Exercise negative cases with **separate disposable fixtures**: no recorded operation, occupied destination without receipt, receipt reserved before publication, corrupted or mismatched receipt, modified source/backup, wrong key, and changed schema selection. Outputs must be `unknown`/manual-review/denial as appropriate, never an authorization to retry or delete.
6. Check that recovery inspection itself leaves the source, backup, target, receipt and unrelated sentinel byte-identical. Inspect source/backup and existing Host ownership; none may be changed. No automatic cleanup of interruption staging is permitted.
7. On Linux and macOS validate portable launch and the same read-only recovery status separately; build success alone is not desktop acceptance.

## Strict gates and known limitations

- **General installation enabled:** false. **Host provisioning enabled:** false.
- **Automatic recovery/retry/delete/rollback authorized:** false, regardless of matching receipt.
- **Full M2.07 milestone:** open; this is the *read-only recovery triage GUI subgoal*, not crash-durable or authenticated recovery.
- Receipt digests are not signed/authorized provenance. Adversarial path replacement, Windows directory-entry power-loss durability and complete interruption/recovery state transitions remain unproven.
- Do not test failure injection on production Alpha databases. Original source and backup remain protected; no overwrite of occupied targets.
- Do not merge, publish a release or claim that the Minglefield application is installed.
- Record actual packaging commit SHA, per-OS build/job outcome and user-observed results before accepting this GUI subgoal.
- **Maintainer acceptance:** pending manual portable test.
