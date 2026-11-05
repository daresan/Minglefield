# Registered Alpha SQLite schema — read-only recognition gate

Status: implemented for the 2026-11-05 installer milestone; **not a
migration-execution gate**.

## Exact scope

The current unversioned local Alpha SQLite family is defined in
`server/private_alpha_auth.py`,
`server/sec01_integrated_alpha_admission.py` and
`server/sec01_host_commit_policy_sim.py`.
The installer now records an **explicit and static** contract for its 27
known tables and 111 columns in
`installer/crates/installer-core/src/legacy_alpha_mapping.rs`.

This contract identifies the known layout by verifying **on an inspected,
integrity-checked in-memory snapshot**, rather than trusting table-name
presence or creating a version number for an unregistered database:

- the legacy `application_id=0` and `user_version=0` headers;
- the required 27 table names, with no duplicate table entries;
- the exact expected column names, order and SQLite declared types;
- `NOT NULL` flags, primary-key positions and hidden/generated-column flags;
- a consistent source snapshot, successful SQLite integrity check and no
  foreign-key violations;
- no unknown extra tables or unreviewed triggers for positive structural
  recognition. Unknown tables still appear in the installer fallback editor.

A **recognized** result means the registered column contract matched.
It does **not** mean that a new encrypted operational database can be
published or that the current application runtime can open it.

## Observable installer result

After Step 3 inspects a matching existing Alpha database, the displayed
installation-plan `database.schemaAssessment` contains:

```json
{
  "recognized": true,
  "reason": "registered_alpha_column_signatures_verified",
  "matchedTableCount": 27,
  "matchedColumnCount": 111,
  "migrationEnabled": false
}
```

The Rust backend reports the source of the recognition evidence.
The frontend does not infer matching signatures from names.
Missing or modified tables, unregistered extensions, wrong schema
headers or damaged source integrity remain blocked. No password,
row contents or hashes are included in the mapping report.

**Important:** `migrationEnabled`, `executionEnabled`,
`destinationCreated` and `encryptedDestinationVerified`
must remain false until the separate execution gates are implemented.

## Remaining mandatory gates before durable migration

1. **Structural schema-object audit implemented; Shadow acceptance pending.**
   The installer reconstructs the authoritative Alpha reference DDL in a
   separate in-memory SQLite database and compares every resulting
   `sqlite_schema` entry (tables, generated/explicit indexes, SQL text)
   against the inspected read-only source snapshot. This covers the
   actual `UNIQUE`, `CHECK`, `FOREIGN KEY`, `DEFAULT`, and partial
   index declarations; unknown indexes, triggers, views and extensions
   cause an explicit failure of the new proof. A changed SQL statement,
   not merely a changed row count, is detected.
   The new `database.schemaObjectAssessment` is a distinct, read-only
   proof with `verified`, `reason`, object counts and *only* affected
   object names for diagnostics, never row values or credentials.
   It does not promote the older column-only `schemaAssessment` or enable
   execution. The first real Alpha source must be checked on Shadow,
   including any historical DDL variants that deserve explicit review.
   Retain independent source-integrity and full-row/schema equality
   proofs for any reviewed extensions; never silently transform schema.
2. Establish the actual SQLCipher-compatible **operational application
   database runtime**. Merely creating a SQLCipher copy is not sufficient:
   the installed Minglefield application must be able to open and use it.
3. Implement exclusive, non-overwriting destination creation; verified
   encrypted export and source-preserving atomic publication with robust
   interruption/concurrency/recovery tests across supported filesystems.
4. Add an explicit owner-facing, one-time execution confirmation in the
   established GUI wizard and a safe unattended equivalent.
5. Integrate with installer application payload staging, first-run
   configuration and the authenticated local Host onboarding boundary.
6. Complete cross-platform CI, independent migration integrity tests
   and a real Shadow acceptance build before calling installation ready.

No part of this milestone authorizes writing to the original Alpha
database, creating an operational destination or claiming a local Host.

## Test responsibilities

- Rust: complete 27-table/111-column fixture recognition; rejection of
  altered/missing/extended layouts and unregistered headers.
- JS: recognized only when accompanied by verified backend evidence;
  name-only matching never authorizes migration.
- Tauri: read-only schema audit on the same verified snapshot as the
  main SQLite inspection. Report only structural metadata.
- Cross-platform: Rust core, Tauri GUI, Node, and final Vite build.

The five domain tabs are unchanged; imported Comfy workflow JSON remains
in `sec01_host_comfy_workflows.workflow` within SQLite, not on a
separate file-system path.

## Independently registered full-schema-object preflight (2026-11-05)

Implementation: `installer/crates/installer-core/src/legacy_alpha_constraints.rs`
and `installer/gui/schema-object-assessment.js`.

- A private `Connection::open_in_memory()` constructs the expected 27-table
  schema, plus the named partial unique index
  `uq_game_install_one_active_project`, using the actual, reviewed
  `CREATE TABLE` and `CREATE UNIQUE INDEX` declarations from the
  local Alpha server sources.
- The inspector opens **one** read-only verified source snapshot and audits
  the reference and source `sqlite_schema` entries independently.
  SQL comparisons ignore formatting and ordinary identifier quoting but
  preserve the case of SQL string literals: this matters for the
  partial index filtering committed/cancelled installation operations.
- Every entry (including automatically generated unique/primary-key
  indexes) must match by object name, type, owning table and normalized
  CREATE statement. Unregistered objects are reported by name and block
  full object verification. No source paths, row values or credentials are
  copied into the diagnostic.
- The preflight does not write a destination or change installation flags.
  It is **not** a compatibility promise for arbitrary historical Alpha
  variants: semantically equivalent, but unregistered DDL may be rejected
  pending individual review. Such mismatch is safer than silently dropping
  an index or constraint during migration.
- Focused test cases deliberately omit or change the unique partial index,
  `UNIQUE` constraint, `CHECK` constraint, foreign key and default, and
  introduce unregistered triggers, indexes and views. They also exercise
  SQLite's harmless identifier quoting after an accepted legacy rename.

The final SQLCipher runtime, exclusive/atomic publication,
installation consent, durable execution and rollback/recovery remain
blocked separate gates. Any eventual execution command **must re-inspect**
the actual source in its own transaction/snapshot immediately before
publication; it must not trust an earlier UI preview.
