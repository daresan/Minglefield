
# Portable GUI milestone — complete in-memory data fidelity, 2026-11-05

A single explicit portable build for Windows, Linux and macOS is requested
by updating this file. Ordinary development commits **must not** trigger
portable packaging automatically.

## Implementation being accepted

- The verified SQLCipher/SQLite snapshot is copied to a *second*
  isolated, memory-only database via SQLite's backup API.
- Rust compares **all row values** across all tables and all schema
  objects, including duplicate rows, exact BLOB bytes, internal tables,
  indexes, views and triggers. No record value or per-row digest is exposed.
- SQLCipher sources are unlocked with the supplied existing source password;
  the second memory-only connection uses matching key initialization.
  Correct-key and wrong-key regression cases are covered in CI.
- Supported edits are simulated only in the second copy; the transaction
  is rolled back. The same complete comparison is run again afterwards.
- The rehearsal and final preview expose `fullDataCopyVerified: true`,
  `verifiedRowCount`, `verifiedTableCount`,
  `verifiedSchemaEntryCount`, `verifiedInternalTableCount`.
- `destinationCreated: false`,
  `encryptedDestinationVerified: false`,
  `migrationEnabled: false` and `executionEnabled: false` remain mandatory.

## Manual Windows/Shadow acceptance (when available)

1. Launch the portable executable directly; no setup-manager installation
   or dependency preinstallation should be required.
2. Select the existing Alpha database. Check the existing five data
   categories and complete column coverage.
3. Run rehearsal with no edits. It must report full data copy verified;
   all 27 known application tables and 111 known columns should still be
   represented if the source has not changed. Extra internal tables are
   checked but do not alter the source's reported application-table list.
4. Stage an allowed Git profile label, effect description or Game path
   correction, and repeat. The changed-field count should increase,
   the copied database should pass full rollback verification, and the
   original Alpha file must remain unchanged.
5. Use a distinct unused target filename in the same directory; confirm
   that identical filenames, existing files and SQLite sidecar names are
   rejected. No destination database must actually appear.
6. Check the final review makes **clear that encryption of a destination
   database has not yet been verified** and migration/installation remain
   unavailable. If the source is a *genuinely encrypted* SQLCipher DB,
   test correct and incorrect source-password handling separately.

This is a non-executing migration fidelity milestone, **not** acceptance
of a real SQLCipher output, application installation, or Host onboarding.
The next executor milestone requires an independent encrypted destination
write/reopen/check and rollback design, after explicit GUI review acceptance.
