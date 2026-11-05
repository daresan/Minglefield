# Portable GUI milestone — registered unversioned Alpha schema audit

**2026-11-05 — next explicitly requested one-time test build** on
`feat/game-integration-updates`. This marker is the designated
portable-packaging trigger; routine commits do not package.

## Changes to verify

- The installer identifies the current unversioned local Alpha schema
  with a **registered Rust contract** for all 27 known tables and 111
  columns. The contract is grounded in the actual server CREATE TABLE
  declarations. It verifies exact column order, SQLite declared type,
  NOT NULL, primary-key position and absence of hidden/generated columns.
- The Rust inspector evaluates the contract on the same
  integrity-checked, read-only in-memory SQLite snapshot used for the
  rest of the inspection. Unknown or modified known tables,
  unregistered extensions, unexpected source headers and triggers
  remain structurally **unrecognized**.
- The plan's `database.schemaAssessment` now distinguishes
  name-only Alpha discovery from a verified matching structure.
  For a compatible 27-table/111-column Alpha database, expect:

```json
{
  "recognized": true,
  "reason": "registered_alpha_column_signatures_verified",
  "matchedTableCount": 27,
  "matchedColumnCount": 111,
  "migrationEnabled": false
}
```

- This is a **structural recognition** milestone, not the final
  durable-encrypted destination migration or operational runtime.
  `migrationEnabled`, `executionEnabled`,
  `destinationCreated` and `encryptedDestinationVerified`
  must all remain **false**.
- The five existing full-value database domains remain **Anmeldung**,
  **Hosts**, **Effekte**, **Jobs** and **Games**. Unknown source tables,
  if any, remain in the Sonstige fallback, not silently ignored.
  Comfy workflows continue to be saved as JSON text in SQLite.
- Step 3 remains the only password-entry page. No copied password,
  record body, token, BLOB or hash appears in mapping diagnostics or
  installation-plan output. The source database is never modified.

## Required CI

- Windows/Linux/macOS: core Rust format, check, Clippy and tests.
- Windows/Linux/macOS: Tauri GUI Node suite, Vite frontend build,
  Tauri Rust check/lint/test.
- Dedicated Rust tests for correct 27/111 recognition and for
  missing, extra, changed, or unregistered schemas and source headers.
- Dedicated JS tests ensure table-name-only discovery never promotes
  the backend mapping and that migration execution remains disabled.
- Only the portable Windows EXE, Linux AppImage and macOS app
  artifacts from **this marker commit** are eligible for acceptance.

## Manual Shadow test

1. Download the portable `tauri-portable-windows-exe` ZIP, unpack it
   and launch the EXE without installing the setup manager.
2. Select the existing `alpha.sqlite3` on Step 3 and run **Inspect**
   once. Confirm there is no Step-4 password re-entry.
3. Preview the installation plan and inspect
   `database.schemaAssessment`. If the database has the known
   27-table/111-column layout, the expected output is
   `recognized: true`, reason
   `registered_alpha_column_signatures_verified`, the two matching
   counts, and `migrationEnabled: false`. If it fails, report
   **only** the structural assessment and any reported table names,
   not sensitive database values.
4. Confirm that the five domain-tab editors still load the real
   records; in Effekte inspect `sec01_host_comfy_workflows.workflow`,
   and in Hosts inspect `sec01_host_rules.config`.
5. Stage one reversible nonsensitive edit. Rerun memory rehearsal
   and temporary encrypted copy. Verify equal edit counts, all
   row/schema proofs, wrong-key rejection and temporary cleanup.
6. Ensure the source is unchanged, no durable destination is created,
   and every execution flag is false.

These are pre-release portable **test builds**. The additional
preconditions for durable publication and first-run Host onboarding
are documented in `installer/REGISTERED-ALPHA-SCHEMA.md`.
