# Portable GUI milestone — complete registered Alpha SQLite schema-object audit

**2026-11-05 — one-time portable Shadow acceptance build explicitly authorized**
on `feat/game-integration-updates`. This remains the designated
portable packaging trigger: ordinary code commits do not package.

## Tested functional scope

- Keep the five approved owner-facing database editor areas:
  **Anmeldung**, **Hosts**, **Effekte**, **Jobs**, **Games**.
  Unrecognized extension tables remain accessible in the fallback.
  Comfy-Workflow JSON is stored as SQLite TEXT, never as an invented
  external workflow path.
- The existing registered column-signature preflight continues to
  recognize the known unversioned Alpha database (27 tables / 111
  columns) without authorizing migration.
- New separate read-only `database.schemaObjectAssessment` report:
  `verified`, `reason`, expected/matched SQLite schema entry
  counts, expected index count and names of missing, extra or
  incompatible objects. No schema SQL, record values, passwords or
  session secrets are copied into the installation plan.
- The registered reference schema is independently constructed from
  the server's actual `CREATE TABLE` and named `CREATE UNIQUE INDEX`
  statements on a private in-memory connection. Every source
  `sqlite_schema` table/index/view/trigger entry must match the
  reference, including automatically generated primary/unique indexes,
  CHECK and DEFAULT constraints, the game-installation foreign key,
  and the partial active-game-installation unique index.
- Positive object verification is **not** permission to create or
  publish a durable encrypted SQLCipher destination or execute an
  installer. All `migrationEnabled`, `executionEnabled`,
  `destinationCreated`, `encryptedDestinationVerified` remain
  **false**. A structural mismatch explicitly blocks this gate.
- Historic DDL variants not yet registered may be structurally
  different despite preserving all 27/111 known columns. The audit
  fails closed and identifies only object names for review. Do not
  turn an unknown variation into a silent schema conversion.
- The existing memory rehearsal and temporary on-disk encrypted copy
  continue to preserve the original source and cleanup temporary
  files, while never creating the final target.
- Source and new SQLCipher credentials are entered on Step 3 only,
  never again on Step 4. Do not copy credentials into feedback.

## Required CI

- Windows/Linux/macOS: installer-core rustfmt, cargo check, clippy
  and cargo test, including new reference DDL/constraint regression
  tests (partial index, unique, check, FK, default, trigger/view
  extensions and legacy SQLite identifier quoting).
- Windows/Linux/macOS: frontend Node tests for read-only schema-object
  assessment, frontend build and Tauri backend checks/lints/tests.
- Publish only the marker commit's Windows EXE, Linux AppImage and
  macOS app when the actual packaging jobs succeed.

## Shadow acceptance

1. Launch the *new* `tauri-portable-windows-exe` from this GitHub run.
2. Inspect your current `alpha.sqlite3` in Step 3. Confirm the
   existing `schemaAssessment` still shows 27 recognized tables
   and 111 columns, with `migrationEnabled:false`.
3. Look in the installation plan for
   `database.schemaObjectAssessment`. A matching, currently
   registered schema returns:
   `verified:true`,
   `reason:"registered_alpha_schema_objects_verified"`,
   matching expected/matched schema-entry counts and
   `migrationEnabled:false`.
   If it instead reports `verified:false`, provide only the
   `reason` and `missingObjects`/`extraObjects`/
   `incompatibleObjects` names so we can review the precise
   historical variant. This is an actionable test result, not
   permission to ignore differences.
4. Verify Comfy workflows still load under Effekte, host rules under
   Hosts and stage one reversible, nonsensitive edit.
5. Rerun in-memory rehearsal and encrypted temporary-copy check:
   both report the staged change, ciphertext verifies, wrong-key is
   rejected, temporary files are removed, original and final target
   remain untouched, and every execution flag stays false.

The final durable migration needs operational SQLCipher runtime
integration, exclusive/atomic destination publication,
failure/recovery tests and explicit owner consent. It is not part
of this build.
