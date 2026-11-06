# Portable GUI milestone — temporary atomic SQLCipher publication rehearsal

**2026-11-06 — one-time next Shadow test build** on
`feat/game-integration-updates`. This file update is the explicit
portable packaging trigger. Ordinary implementation commits do not
package Windows EXE, Linux AppImage or macOS app bundles.

## Changes under test

- The previously verified data review remains values-only:
  27 registered local Alpha tables, 111 columns, no type-edit dropdown,
  all five database tabs and unknown-table fallback preserved.
- The full registered 58-entry schema audit, existing migrated row
  corrections, in-memory rehearsal, SQLCipher ciphertext verification
  and wrong-key rejection are unchanged.
- **New native publication rehearsal:** after writing and independently
  verifying the private temporary SQLCipher file, the Rust installer
  attempts an atomic, exclusive `hard_link` promotion **within the
  same private temporary test directory**. It proves the staged file
  can be opened under the new name with the required key and that all
  preserved rows and schema entries match.
- A second link attempt to the occupied new name must fail with an
  AlreadyExists error. A separate preexisting non-SQLite file must not
  be overwritten or modified. All temporary data, including both hard
  links, must be removed.
- A new `atomicTemporaryPublicationVerified` boolean is mandatory
  in `database.verifiedTemporaryEncryptedCopy` before this revised
  temporary-copy proof can pass. The new status is never permission
  to write the actual user-selected destination.
- The **selected final destination must remain absent**:
  `destinationCreated:false`,
  `encryptedDestinationVerified:false`,
  `migrationEnabled:false`, `executionEnabled:false`.
  The original Alpha database must remain unchanged.
- The trusted offline `mingleadmin` transaction is covered by
  existing real SQLCipher Python conformance. The separate cross-language
  Rust-export → Python runtime integration test exists but remains
  **opt-in and not yet CI-verified**. This milestone does not claim
  cross-language acceptance, first-run owner authorization, installed
  application package or durable final publish.

## CI

- All three operating systems: `cargo fmt --check`, `cargo check`,
  `cargo clippy -D warnings`, and `cargo test` in the installer core,
  including native atomic-link and no-overwrite checks.
- All three operating systems: Tauri GUI Node tests, frontend build,
  Rust check, clippy and Tauri Rust tests, including the UI's
  `atomicTemporaryPublicationVerified` acceptance gate.
- Only artifacts from the explicit marker's successful platform
  packaging jobs are eligible for Shadow acceptance.

## Targeted Shadow acceptance

1. Download the *new* `tauri-portable-windows-exe` ZIP from this
   marker's GitHub Actions run, extract to a new folder and run
   `minglefield-installer-gui.exe`.
2. Select the existing Alpha database, inspect and validate as usual.
   Keep the same expected schema counts (27 tables, 111 columns,
   31 non-table objects, 58 total schema entries) without needing to
   repeat all previous domain-editor scenarios.
3. Run the in-memory migration rehearsal and the **temporary
   encrypted copy** with at most one harmless staged value change.
   In the validated plan, confirm
   `database.verifiedTemporaryEncryptedCopy.atomicTemporaryPublicationVerified`
   is **true**, together with wrong-key rejection, full record/schema
   equality, and `temporaryFilesRemoved:true`.
4. Confirm the real destination remains uncreated, no migration
   execution is enabled and the Alpha source remains unchanged.
   Do not share passwords, raw rows or workflow secrets.

**Important limitation:** the native hard-link proof currently uses
the OS temporary filesystem. It does not establish atomic publication
or path-handle safety on the user's selected destination filesystem,
nor crash durability or authenticated first-run handoff. Those remain
mandatory gates before any permanent SQLCipher migration is enabled.
