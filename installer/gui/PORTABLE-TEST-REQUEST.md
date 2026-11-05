# Portable GUI milestone — full typed SQLite review (all Alpha tables)

**2026-11-05 — explicitly requested next one-time test build** on
`feat/game-integration-updates`. Only changes to this marker trigger portable
packaging on the feature branch. Routine installer commits do not.

## What this milestone adds

- The user enters and confirms the **new SQLCipher database password only
  once on Step 3**. Step 4 has **no second new/test password fields**.
  The temporary encrypted-copy test reuses those existing in-memory inputs.
  Passwords are never added to installation-plan JSON or persisted.
- The existing Alpha source unlock password remains separate and optional
  for unencrypted SQLite. The Step-3 source key is reused for both Step-4
  verification actions after successful inspection; there is no second
  source-key input. The key is kept only in the running GUI session, never
  written to the installation plan or to disk. Switching databases or
  changing the source key invalidates the prior inspection and proof.
- The existing **in-memory migration rehearsal** applies corrections and
  rolls back; the original source is still never modified.
- The new encrypted-copy rehearsal verifies all the same staged corrections
  against their original values and owner/host identities, commits them
  **only in an isolated, verified RAM copy**, encrypts that copy into a
  randomized private temporary SQLCipher file, tests wrong-key rejection,
  reopens with the Step-3 key, compares all data/schema against the corrected
  RAM copy, closes handles and deletes the temporary directory.
- The original 7 typed correction kinds remain supported: user disabled, agent
  disabled, effect description, effect enabled, Game name, Game path, Git
  profile text. Stale, duplicate and trigger-dependent corrections fail closed.
- Response: `verifiedStagedChanges` equals the current memory rehearsal's
  `verifiedChanges`; `stagedValuesMatchCiphertext: true` proves those
  changes survived the temporary SQLCipher round trip.
- No final destination is created or written. `destinationCreated`,
  `encryptedDestinationVerified`, `migrationEnabled` and
  `executionEnabled` remain **false**; no Minglefield install or Host claim.

- The Data Review step displays the vetted Alpha application records as
  horizontally scrollable tables in five domain tabs: Anmeldung, Hosts, Effekte,
  Jobs and Games. The sixth tab exposes all database tables and values. Each field returned by the existing verified readers
  has a separate column; the seven existing correction kinds are represented
  by directly editable controls. Protected identity/ownership/job-state,
  authentication and other sensitive fields remain read-only and are not
  given a generic SQL writer. Full-table schema coverage is still reported
  by the migration rehearsal.
- Table editors stage changes in memory and apply the existing correction
  validators; rejected values return to their last accepted state, and
  changing a value invalidates the previous rehearsal.

## New scope: complete typed table values (not only the legacy allowlist)

- Step 4 contains a sixth tab, **Alle DB-Tabellen**. It lists every
  table and stored column from the inspected SQLite database, with the
  existing source values, rather than inferring paths or inventing fields.
  In particular, select `sec01_host_comfy_workflows`, `sec01_host_rules`,
  `sec01_host_settings`, and `sec01_host_runtimes` to inspect the actual
  Comfy workflow records, host rules and runtime JSON settings.
- Editing uses SQLite storage classes (NULL, signed 64-bit INTEGER,
  REAL, TEXT, hexadecimal BLOB), including identity and config values,
  through typed full-row staged corrections rather than a hardcoded
  list of approved application fields. Changes are compared against
  the exact original row and applied only to an isolated verified copy.
- Every value is visible in the local WebView after explicit database
  inspection. Password hashes and session hashes are sensitive; do
  not include these or other private record contents in feedback logs
  or screenshots.
- The installation-plan JSON reports table names, original rowids,
  changed column names for full-table edits, not their values.
- SQLite constraints, ambiguous row identity, changed schema, stale
  source values, unexpected triggers, and incomplete validation cause
  a safe rejection. No source file or final destination is written.
- Current bounded review supports up to 5000 rows per table and
  32 MiB of displayed cell data; it explicitly rejects larger imports
  until pagination is implemented. SQLite-generated columns remain
  constrained by SQLite itself.
- Avoid staging changes to the same row through both the legacy
  category editor and the full-table editor during this milestone;
  cross-editor consolidation is not yet implemented.

## Shadow acceptance for the new scope

1. Inspect the existing Alpha database on Step 3 and enter a new
   destination SQLCipher key once. Step 4 has no password input.
2. Open **Alle DB-Tabellen**. Verify 27 source tables and that
   the `sec01_host_comfy_workflows` and `sec01_host_rules` entries
   are selectable with all stored columns and row contents. If a path
   is held inside JSON, review the actual JSON; do not expect an
   invented standalone path column.
3. Stage one reversible TEXT/JSON edit in a host rule or Comfy
   workflow row, avoiding duplicate edits in the older category
   tab. Confirm the install plan lists that table, row and changed
   column without exposing the original/new cell contents.
4. Run the in-memory rehearsal and temporary encrypted SQLCipher
   copy check. `verifiedChanges` and `verifiedStagedChanges` must
   reflect the staged row count and `stagedValuesMatchCiphertext`
   must be true. The original and final destination remain untouched.
5. Optionally test a BLOB/INTEGER/NULL cell on a disposable fixture.
   Do not modify security credentials or ownership identifiers in
   the real Alpha database solely for acceptance testing.

## Manual acceptance on Shadow

1. Run the portable Windows executable. Inspect the same existing Alpha
   database (previously 27 application tables, 111 columns, 143 rows).
2. On **Step 3**, enter an existing database unlock key only if needed,
   inspect the database and set/confirm a strong **new** SQLCipher key.
   Neither password is included in the displayed plan JSON. Step 4 must
   contain no source or destination password input.
3. On Step 4, inspect the five tabs: all loaded fields should be visible
   as table columns, with controls for only approved corrections. Run the
   memory rehearsal with zero changes and then the temporary encrypted-disk-
   copy test **without reentering either database key**.
   Check `verifiedStagedChanges: 0`, `stagedValuesMatchCiphertext: true`,
   `temporaryFilesRemoved: true` and unchanged source/final destination.
4. Stage one or more table-cell changes (e.g. Git label, effect description,
   enabled status or Game name); rerun the memory rehearsal, then the disk test
   using the still-confirmed Step-3 password. Its `verifiedStagedChanges`
   should exactly equal the staged correction count, with full ciphertext
   value equality and temporary cleanup.
5. Edit any staged field or either password afterwards: the previous proof
   must be invalidated until reverified.
6. Check Step 6 / Review contains the independent proof count but still
   reports no final encrypted destination and all execution flags false.

These are temporary test builds, not Minglefield installation packages.
The next planned phase remains a properly reviewed *durable* destination
migration with exclusive creation, atomic publication, verified recovery,
complete schema mapping, confirmed destination key and authenticated
local Host onboarding. Do not interpret a successful temporary copy as
authorization to run that phase.
