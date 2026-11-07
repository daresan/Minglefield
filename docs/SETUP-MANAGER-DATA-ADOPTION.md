# Setup Manager: existing configuration and database adoption

Status: accepted data-adoption contract (2026-11-04), with **bounded executable Alpha SQLCipher copy already implemented/accepted for its earlier scope**, and M2.08 full application/operator acceptance still failed/pending (updated 2026-11-07). Historical proof-stage sections below describe their dated scope, not current overall implementation status.

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
- Use isolated staging, independent source backup and receipt/audit for mutations; never overwrite existing data. **Current experimental Alpha exception:** interruption/failure can be retried at a different, fresh unoccupied destination while source and independently verified backup remain unchanged; automatic rollback and crash-durable recovery are deferred to M2.13–M2.15.
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

## Historical binding implementation order (confirmed 2026-11-05; superseded in execution by later accepted Alpha milestones)

**At that checkpoint,** the immediate priority was the GUI database-data review before executable migration. The subsequent M2.06 controlled non-overwriting SQLCipher destination copy and M2.08 application/Host slices are now implemented at limited experimental scope; the earlier sequencing is preserved as history, not as a demand to repeat completed checkpoints.

1. **Reuse existing discovery and inspection:** The selected repository/data directory and known per-user data locations already have read-only candidate inventory; retain their bounded search and repository-independent data detection. Extend coverage only for demonstrated missing actual data paths.
2. **Complete the existing wizard data-review UI:** Load verified, recognized application records from the inspected database into the existing Login, Hosts, Effects, Jobs and Games review tabs. Distinguish available records, unsupported schemas and missing categories; do not invent placeholder records or silently omit data.
3. **Finish editable review fields:** Show original values, permit only supported corrections, validate types and relationships, and keep proposed changes in review state without writing to the source database. Credentials and secrets must not be exposed or implicitly migrated.
4. **Complete the final review:** Present original versus proposed values, selections, validation errors, exclusions and destination/conflict implications; require explicit confirmation before any later mutation. Provide focused regression tests and a build with visible, usable review functionality for maintainer acceptance.
5. **Only after the GUI review is complete and accepted:** Implement tested consistent SQLite snapshot/staging, versioned migration transformations, destination backups/rollback and real Minglefield application installation. Integrate authenticated local Host first-run provisioning through the existing Hosts architecture, not a parallel Host system.

**Rehearsal API invariant:** `migration_enabled` and `execution_enabled` remain false in *read-only and non-publishing preview responses*. Actual separately authorized execution APIs report their own results truthfully. Do not recast an old rehearsal response as the overall installer execution state.

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

**Historical remaining blockers at the 2026-11-05 proof checkpoint (subsequent Alpha copy satisfies a bounded subset):** (1) manual acceptance
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

## Ephemeral SQLCipher export and corrected-record read-back

The non-publishing, user-initiated SQLCipher disk-copy proof now takes the
**exact allowlisted staged corrections** from the Data Review, first checks
them in a separate in-memory rollback rehearsal and then applies them to
a second verified RAM copy. The original user-selected database is never
written. The corrected copy is exported via `sqlcipher_export` into a
protected randomized temporary directory, rekeyed with the **existing
new-database password from Step 3**, reopened independently and compared
byte-for-byte at the typed cell level with the corrected RAM source.

The operator is not asked for a second destination password. The password
confirmation and strength checks apply at both the GUI and Rust boundaries;
the key is not serialized into the installer plan. The final destination file
is not created; the encrypted file used for the proof is removed (cleanup
on failure is best-effort). Field counts, corrected row values, schema
objects and the exact staged correction count must match. Authentication,
owner binding, stale-value rejection and trigger checks reuse the existing
migration_dry_run Rust policy instead of duplicating mutable rules.

**At the date of this ephemeral proof only,** no persistent SQLCipher output, Minglefield installation, recovery checkpoint, or local Host claim was performed, and the rehearsal execution flags remained false. **Later status (2026-11-07):** the separately authorized Alpha copy creates and verifies a real non-overwriting encrypted destination, and experimental native application-file/first-run setup exists; their combined GUI operator acceptance is still failed/pending. Complete automatic rollback/crash-durable recovery remains deferred, without weakening current source/backup preservation and fresh-target retry.

## Current adopted-data and ownership invariant (approved 2026-11-07)

The first Alpha installs application code only from the bundled, verified official package. The selected source checkout or data directory may supply **data** but must not become an executable application source. Source-based application installation is a separate, deferred Advanced/Developer capability.

An imported SQLCipher/SQLite Alpha database retains the actual existing users and salted login verifiers, `alpha_sessions` rows (token **hashes**, expiry/revocation), operator/owner/admin associations, persisted Host IDs and recorded local/remote grants, delegated agents, Host settings/runtimes, Effects, Jobs, Games and compatible schema/extensions. **No new `mingleadmin`, Host ID, claim token, password or session issuance is required just because this database was migrated.** Reuse existing login and Host authorization after opening the encrypted database. An already issued bearer token can continue to authenticate only while its client possesses it and it remains unexpired/unrevoked; the stored hash cannot regenerate a lost/expired token. Existing password login issues a fresh session through normal application code, not the installer. A new, conflicting Host ownership assignment may be denied without denying data import or normal application startup. The current first-run *creation* worker incorrectly rejects existing IDs when invoked for this case; the installer must **skip new identity/Host creation** for already provisioned imports rather than add a new exception-driven recovery protocol. Retain the original `host_id` instead of generating a new identity from the copy's operation ID.

**Current Alpha retry:** An interruption may leave the earlier destination/receipt occupied; retry only with a separately authorized operation at another unused destination. No automatic cleanup/recovery, no source mutation, and no assertion that a previously reserved output is safe to reuse. New encrypted DB creation without import is due in M2.10, after independent M2.09 application shell/runtime verification. Remote-Host online claiming and client-only installation are outside these data-adoption acceptance gates; existing remote rows are nevertheless preserved and checked for fidelity.
