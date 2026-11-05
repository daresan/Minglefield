# Portable GUI milestone — fix source-encryption-aware rehearsal backup

**2026-11-05 / Shadow regression after manual GUI acceptance attempt**

This file is the one explicit marker for a portable preview on Windows,
Linux and macOS. Ordinary commits on the feature branch do not trigger
portable packaging.

## Failure reproduced from the latest Shadow test

The displayed error was:
`Migration rehearsal rejected: Cannot initialize isolated migration backup.`

The initial inspected source snapshot distinguishes actual SQLCipher source
encryption by its on-disk SQLite header, and correctly ignores an optional
existing-source password when the database is *plaintext*. The new second
in-memory-copy path incorrectly treated any nonempty password as evidence of
encryption and initialized the second destination connection with that key,
making the backup incompatible with the plaintext snapshot.

## Corrective implementation and acceptance

- The inspected SQLite snapshot carries a trusted `source_encrypted` flag,
  established during source inspection rather than inferred from user input.
- The secondary memory-only backup uses a SQLCipher key **only when the
  inspected source really is encrypted**.
- A new regression runs the complete Alpha migration rehearsal both with
  an empty password and an optional nonempty password on the same plaintext
  fixture, including supported staged changes. Both must pass with identical
  full-data-copy fidelity and unchanged source bytes.
- Existing SQLCipher tests verify that genuinely encrypted sources still
  require the correct existing key, wrong keys fail, and source bytes remain
  unchanged.
- Source/destination directory policy is unchanged (same folder allowed if
  filename differs); macOS fixture directory naming is made concurrency-safe.

## Manual test on Shadow

1. Run the new portable EXE and select the same real Alpha source database.
2. If `alpha.sqlite3` is ordinary SQLite, the *existing source password*
   can be blank, and an optional filled password must no longer break
   the second in-memory backup.
3. Run **Migration rehearsal** without staged changes.
4. Check the JSON for `fullDataCopyVerified: true` and the
   `verifiedRowCount`, `verifiedTableCount`, `verifiedSchemaEntryCount`
   and `verifiedInternalTableCount` fields. In the final Review plan,
   find `database.verifiedMigrationRehearsal.fullDataCopyVerified`.
5. Rehearse one harmless staged metadata change. The source remains
   unchanged and the destination file is **not** created.
6. `encryptedDestinationVerified`, `destinationCreated` and
   `executionEnabled` **must remain false**. This is still not an
   executable SQLCipher migration.

Do not confuse the *existing database unlock password* with the separate,
mandatory strong *new destination database password*. The latter remains
required for every new installation, and no migration execution is enabled.

These artifacts are temporary test previews, not release installers.
