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
