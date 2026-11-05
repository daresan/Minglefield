# Setup Manager: existing configuration and database adoption

Status: accepted product requirement (2026-11-04). This document describes required behavior, **not** an implemented migration.

## Separate application code from user data

The setup manager installs application code from the selected official distribution channel. An existing user-selected Minglefield repository or directory is **only** a candidate source of settings, state, and databases. Never execute, import as Python, or install code from that directory as a side effect of discovery or migration. Do not require Git provenance, a pristine repository layout, AGENTS.md, or a matching README to inspect user data.

The existing `inspect_source_path` command is a narrow source-checkout classifier, not a data-discovery or migration result. `provenanceVerified: false` and `launchReady: false` must not gate data adoption.

## Required discovery

- Scan an explicitly selected directory, and later approved known per-user locations, read-only for recognized configuration formats and database formats. Do not recursively scan arbitrary trees without bounded scope.
- Report each candidate separately: location, detected format, readable/unsupported/corrupt status, known keys/tables, schema/version, and any warnings. A modified or incomplete repository may contain perfectly valid migratable data.
- Classify outcomes as fully compatible, partially compatible, requires conversion, unsupported, or unreadable. Never report simply 'nothing found' because repository markers are absent.
- Distinguish application config, per-host runtime settings, credentials/secrets, operational SQLite databases, and transient caches. Secrets require separate opt-in and safe handling; caches are not automatically migrated.

## Required migration

- Present a preview and allow explicit per-category selection; explain destination, conflicts, transformations, unsupported fields and omissions.
- Parse only allowlisted keys and recognized schema versions. Preserve unrecognized fields in a separate report/backup where possible; never silently discard them or interpret them as executable configuration.
- For SQLite, obtain a consistent snapshot using SQLite's backup API (or equivalent) rather than copying a live DB file alone; inspect integrity and schema in an isolated working copy. Never mutate the source DB.
- Stage all output outside live application directories; maintain a backup, audit/receipt and recoverable rollback for destination changes. Do not overwrite existing data without explicit conflict resolution.
- Validate and migrate data using versioned, tested transformations. No dynamic code execution, untrusted SQL scripts, or automatic credential import.
- On failure, leave originals intact and report partial progress clearly.

## Acceptance tests

1. A directory with valid Minglefield config/DB but no README/AGENTS.md is offered for adoption.
2. A modified config yields recognized fields plus explicit warnings for unknown fields.
3. A live SQLite DB is snapshotted consistently; original bytes/state remain unchanged.
4. An incompatible/corrupt DB is not migrated and does not block adoption of valid independent settings.
5. Source code in the selected directory is never run or copied into the application payload.
6. A clean laptop without existing data installs using defaults, without a misleading migration warning.
7. Re-running migration is idempotent or requires explicit conflict handling; failed staging can recover safely.

## Binding implementation order (confirmed 2026-11-05)

**Immediate priority: finish the existing GUI database-data review and editable fields before implementing executable migration or application installation.** Do not switch to migration/installation execution merely because read-only inspection and preview are available.

1. **Reuse existing discovery and inspection:** The selected repository/data directory and known per-user data locations already have read-only candidate inventory; retain their bounded search and repository-independent data detection. Extend coverage only for demonstrated missing actual data paths.
2. **Complete the existing wizard data-review UI:** Load verified, recognized application records from the inspected database into the existing Login, Hosts, Effects, Jobs and Games review tabs. Distinguish available records, unsupported schemas and missing categories; do not invent placeholder records or silently omit data.
3. **Finish editable review fields:** Show original values, permit only supported corrections, validate types and relationships, and keep proposed changes in review state without writing to the source database. Credentials and secrets must not be exposed or implicitly migrated.
4. **Complete the final review:** Present original versus proposed values, selections, validation errors, exclusions and destination/conflict implications; require explicit confirmation before any later mutation. Provide focused regression tests and a build with visible, usable review functionality for maintainer acceptance.
5. **Only after the GUI review is complete and accepted:** Implement tested consistent SQLite snapshot/staging, versioned migration transformations, destination backups/rollback and real Minglefield application installation. Integrate authenticated local Host first-run provisioning through the existing Hosts architecture, not a parallel Host system.

Until executable paths are implemented and verified, `migration_enabled` and `execution_enabled` must remain false. Their values are safety gates, not an indication that the read-only discovery or review work must be restarted. Do not change these flags merely to make the wizard appear complete.

## Next safety checkpoint: full in-memory row fidelity (implemented 2026-11-05)

The staged Alpha migration rehearsal now makes a **second SQLite backup to
memory**, rather than applying corrections to the first verified source
snapshot. Before changes, a full equality checker confirms:

- every original schema record, index, trigger, view, internal table and
  application/user-version metadata is present in the in-memory copy;
- every table's complete row multiset matches, not just the row count.
  Values are encoded by SQLite type, including exact BLOB bytes, length
  boundaries, NULLs and duplicate rows. Per-row SHA-256 fingerprints and
  sensitive values remain inside the Rust process;
- both databases pass quick_check and foreign-key validation;
- corrections use the existing allowlisted expected-original-value checks
  against the second in-memory copy, with transaction rollback;
- all schema objects and values are compared **again after rollback**.

An encrypted SQLCipher *source* is supported by initializing the second
memory connection with the same existing unlock key. The cross-platform
regression suite now tests a genuinely encrypted Alpha source, wrong-key
rejection, unchanged source bytes, BLOB corruption, duplicate-row loss,
schema/metadata differences and rollback recovery.

The report adds `fullDataCopyVerified`, `verifiedRowCount`,
`verifiedTableCount`, `verifiedSchemaEntryCount`,
`verifiedInternalTableCount` and `encryptedDestinationVerified=false`.
Limits are explicit and fail closed: currently one million rows per table,
1024 columns per table, and 128 MiB per encoded record. No SQLCipher
destination is created, no files are published, and the original Alpha
database is not modified.

**Binding remaining blockers for actual migration:** (1) manual acceptance
of the existing GUI data-review on Shadow; (2) a recognized/versioned
source-to-target transformation/preservation contract covering all data
and schema objects; (3) safe staging of a *real encrypted SQLCipher
destination*, encrypted-file reopening and independent complete-content
verification, using a **mandatory strong new password for every installation**
(including fresh installs); (4) exclusive target creation and atomic publication,
existing-target conflict handling, backups and recoverable rollback;
(5) consented Minglefield application installation and authenticated
local Host provisioning through Hosts, without weakening the bootstrap
secret boundary. No migration or application execution is enabled by the
current checkpoint.

Do not interpret row-copy fidelity as a proof of future encrypted-file
persistence or a completed migration.

## Ephemeral SQLCipher export / reopen proof — execution still disabled

A distinct, user-invoked *temporary disk proof* is implemented in the Rust
installer core and GUI. This uses SQLCipher's supported
`ATTACH ... KEY ?` / `sqlcipher_export` path, not the incompatible
plaintext-to-encrypted `sqlite3_backup` path. It exports the already
integrity-verified snapshot into an OS-temporary private directory with a
strong one-use test key, rejects an unrelated key, reopens under the intended
key, compares all row multisets and schema including app/user version
metadata and deletes the temporary directory. Failure paths are
non-publishing and attempt cleanup. No user's actual final destination,
installation directory or existing Alpha records are written.

This proof handles **zero staged changes only**. User-staged corrections
remain in the memory-only rehearsal and cannot yet be applied to the
encrypted output. The result must not be marketed as an executed migration,
installed Minglefield application, validated data adoption or completed Host
claim. Binding decisions for a durable destination still include validated
source schema mapping, backup/recovery plan, exclusive target publication,
preflight race safeguards, durable reopening, a strongly validated confirmed
new password for *every* install and authenticated local Host provisioning
through existing Hosts. `encryptedDestinationVerified` and
`executionEnabled` stay false.
