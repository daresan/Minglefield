# Portable GUI milestone — five-domain full SQLite review

**2026-11-05 — owner-requested one-time portable milestone test build** on
`feat/game-integration-updates`. This file is the existing, explicitly
authorized packaging trigger. Ordinary code commits must not package
portable installers automatically.

## Scope and invariant

- Step 4 uses five owner-facing tab areas: **Anmeldung**, **Hosts**,
  **Effekte**, **Jobs**, **Games**. All 27 currently known Alpha SQLite
  tables are mapped to exactly one area, including the two persisted Comfy
  tables (`sec01_host_comfy_workflows` and
  `sec01_host_effect_definitions`) under **Effekte** and
  `sec01_host_rules`, `sec01_host_settings`,
  `sec01_host_runtimes` under **Hosts**.
- **Sonstige DB-Tabellen** is visible only when the inspected database
  contains tables not included in the known Alpha table-family map.
  Every such table remains accessible. No stored column is silently
  omitted on the basis of its name or sensitivity.
- A single typed, full-row correction path serves every domain tab.
  The obsolete partial-field editors are not used in the live UI,
  avoiding duplicate independent edits to one record.
- The existing Comfy workflow JSON is stored in the SQLite
  `sec01_host_comfy_workflows.workflow` TEXT column, not as an inferred
  or separately located workflow file. No workflow file is created.
  The `metadata` TEXT column contains persisted import bindings.
- The schema-aware editor supports SQLite NULL, signed 64-bit INTEGER,
  REAL, TEXT (including JSON) and hexadecimal BLOB values.
  Changes to identities/keys may be staged by the owner. Database-level
  constraints, foreign keys, schema consistency, stale-row rejection
  and snapshot fidelity must still pass for a migration rehearsal.
- The installation-plan JSON reports only table, original rowid and
  changed column names for these typed corrections, without copying
  sensitive cell contents into the plan or a diagnostic log.
- The source database is never modified. The migration rehearsal is
  in-memory, and the temporary SQLCipher copy is verified and
  destroyed. No final encrypted destination is created.
  `destinationCreated`, `encryptedDestinationVerified`,
  `migrationEnabled` and `executionEnabled` remain **false**.
- Step 3 is the only credential-entry page: both the existing source
  key (if any) and new destination SQLCipher key are reused on Step 4.
  Neither value is included in the plan. The existing source-key
  re-entry regression remains covered.
- Import limits remain: at most 5000 rows per table, 32 MiB of
  reviewed cell content, and typed value limits. Larger databases
  are rejected explicitly until paginated review is implemented.
- Sensitive account, session and credential fields may now be viewed
  and staged, so do not capture these values in logs/screenshots
  or use the production database to test dangerous identity changes.

## Required CI evidence

- Installer Rust `fmt`, `cargo check`, `cargo clippy -D warnings`,
  and `cargo test` on Windows, Linux and macOS.
- GUI Node suite on all three OSes including domain mapping and
  type-editor tests, frontend Vite build and Tauri Rust backend checks.
- AGENTS guard passes. Game-install security CI is distinct from
  platform-installer CI.
- Portable Windows EXE, Linux AppImage and macOS application bundles
  are uploaded as separate workflow artifacts. Unavailable runners
  must not be described as passing.

## Shadow manual acceptance

1. Download the **new** `tauri-portable-windows-exe` artifact for
   this marker commit, unpack and launch the EXE (no setup-manager install).
2. Use Step 3 to inspect the existing `alpha.sqlite3` database
   and enter the destination key once. No second password on Step 4.
3. Check Step 4: all 27 verified tables should be selectable inside
   the **five** domain tabs. In **Effekte**, select
   `sec01_host_comfy_workflows`, confirm the actual `workflow` API-JSON
   and `metadata` values appear. In **Hosts**, select
   `sec01_host_rules`, `sec01_host_settings` and
   `sec01_host_runtimes`. When there are no unknown tables,
   **Sonstige DB-Tabellen** must remain hidden.
4. Stage one reversible, nonsensitive TEXT/JSON change in Hosts or
   Effekte. Navigate away and back to verify the edited value is
   preserved. The plan should show the table/rowid/column, without
   embedding its old/new contents or passwords.
5. Run the in-memory migration rehearsal and the temporary encrypted
   SQLCipher copy test. Verify `verifiedChanges` equals
   `verifiedStagedChanges`, `stagedValuesMatchCiphertext` is true,
   `wrongKeyRejected` is true and `temporaryFilesRemoved` is true.
6. Edit another field or change the credentials: the previous
   verification must be invalidated. The source file and final
   destination remain untouched and all execution flags false.
7. If an unknown extension table exists, verify the **Sonstige**
   fallback shows that table, without duplicating it in the five tabs.
   Avoid sharing sensitive data in screenshots or pasted plan output.

These are temporary portable **test** builds. This milestone does not
authorize durable destination publication, source deletion, installer
execution, or an authenticated local Host claim. Those steps require
their own reviewed implementation, CI and owner acceptance.
