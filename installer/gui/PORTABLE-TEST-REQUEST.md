# M2.08 — specifically corrected portable Alpha setup acceptance after rejected Windows artifact

**Scope:** Exactly one M2.08 failed-build repair retest, not a new M2 under-goal or a restart of deferred M2.07 crash recovery. The [previous corrected-build attempt 42329947124](https://github.com/daresan/Minglefield/actions/runs/42329947124) packaged successfully but failed on Shadow: the uploaded Windows artifact lacked two hidden zero-byte members declared in the build-pinned managed-runtime inventory (`setuptools/_vendor/.lock`, `Scripts/.empty`). Previous [42321392311](https://github.com/daresan/Minglefield/actions/runs/42321392311) was already manually rejected. Neither is accepted. The fix includes hidden files and checks a freshly downloaded, extracted artifact against the unchanged SHA-256 inventory; it does not disable or relax integrity verification.

**Branch:** `feat/game-integration-updates`
**Reviewed implementation HEAD before marker:** `d6d7f7e003205327fd04a1a67f2c2168796b45f2`
**Actual portable source SHA:** the new marker commit (no implementation changes between the verified implementation HEAD and packaging). Record that actual SHA/run rather than claiming the previous HEAD was packaged.
**Packaging path:** Only the existing `.github/workflows/installer-portable-milestone.yml` -> `installer-tauri-packaging.yml` on this feature branch. Windows EXE + sibling `managed-alpha/`, Linux AppImage, macOS app archive. No NSIS/DEB installation of the portable Setup Manager.

## Completed, relevant Minglefield Development CI v1.0.0 engineering gates

- [Installer Rust / Ubuntu #569](https://github.com/daresan/Minglefield/actions/runs/42342101858): **success**, including existing installed Alpha runtime and encrypted login/Host regression tests.
- [Native security / Windows + macOS #83](https://github.com/daresan/Minglefield/actions/runs/42342101861): **both success**, covering the current source/runtime/authorization change set.
- [MAP v0.1 draft conformance #770](https://github.com/daresan/Minglefield/actions/runs/42342101859): **success**, including the added existing bearer-session continuity check.
- [Installer GUI frontend #37](https://github.com/daresan/Minglefield/actions/runs/42342217557): **success**, covering pre-existing users/Hosts and older verified DBs without auth tables.
- [AGENTS security guard #799](https://github.com/daresan/Minglefield/actions/runs/42342217435): **success**.
- Earlier unchanged Tauri backend [#42328609249](https://github.com/daresan/Minglefield/actions/runs/42328609249): **success**, no intervening Tauri backend code change; the packaging modification is exercised by **this** acceptance build, not claimed previously verified.

## New portable artifact checks (CI, not user acceptance)

1. Upload the Windows portable EXE with the entire bundled `managed-alpha/` tree, **including hidden and zero-byte runtime files**; retain the pinned inventory/hash in the compiled binary.
2. **Download the uploaded Windows artifact back into a fresh extraction path within the same packaging job** and verify that the complete managed-runtime inventory matches size, SHA-256 and required names; missing, extra or modified files must fail packaging.
3. Require all Windows/Linux/macOS packaging jobs to succeed with actual downloadable non-expired artifacts. Report the exact packaging run and source SHA. Compilation/upload alone never establishes that the installed Minglefield application launches.

## Focused real Windows operator retest (disposable fixtures; no production data)

1. Download and extract the **entire corrected Windows artifact**, keeping `managed-alpha/` next to its portable EXE. Run without Python/Conda/Git/Cargo/Node developer prerequisites.
2. Select a disposable legacy Alpha database and independently verified backup. Review records and any supported registered missing-schema additions. Authorize one real SQLCipher copy to a **new unused destination** with a separate strong database password; optional rehearsal/temporary-copy diagnostics are not required. Original source and separate backup remain unchanged.
3. Install the verified Alpha application payload into a new application directory or beside the newly created encrypted DB without overwriting either database or unrelated files. Missing parent folders may be created only for an explicitly approved write.
4. **Existing users/Hosts:** If the reviewed DB contains existing identities and Host ownership, the GUI must **not** require a new `mingleadmin`, Host ID, first-run claim, password reset or token regeneration. Preserve existing password verifiers, session token hashes and expiry/revocation state and local/remote Host grants. A client-held valid, unexpired session remains usable; passwords provide normal new login sessions later in the application. The installer must not claim active remote Hosts. A separate M2.09 application launch remains pending.
5. **Genuinely empty local identity/Host:** A verified older DB that has no users or Host bindings (even if it predates current auth tables) may use the existing separately authorized, once-only local first-run path with a login password independent of SQLCipher, without a console invitation.
6. Negative/retry: wrong SQLCipher password does not consume first-run permission; existing/reserved destinations and receipts are never overwritten/deleted; a different fresh target/operation can be used without restarting the manager. Any missing/tampered managed file must fail before installation.

**Out of scope:** M2.09 standalone application shell startup, M2.10 freshly created empty database and general app launch, M2.11 installer CLI, active Remote Host claim/client-only modes, M2.13 repair/update, M2.07 automated crash recovery. The original source/backup and stored remote Host records must still be preserved.

**Maintainer acceptance:** **FAILED / pending actual corrected-build Shadow retest**. Green engineering tests and three-OS packaging are not a substitute for the maintainer's interactive result.
