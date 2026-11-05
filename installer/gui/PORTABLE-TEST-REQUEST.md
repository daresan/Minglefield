# Portable GUI milestone — verified temporary SQLCipher disk copy

**2026-11-05 — single explicit milestone request.** This marker alone triggers
portable packaging on the feature branch. Routine commits do not.

## New capability

- The source Alpha SQLite/SQLCipher database remains read-only.
- After an independently verified **zero-change** memory rehearsal,
  a user must explicitly press **Test encrypted temporary disk copy
  (create, verify, delete)** on Data Review.
- A strong *test-only* SQLCipher password is required and independently
  checked in Rust. It is not stored, and is separate from the permanent
  new-installation SQLCipher password and existing source unlock key.
- The Rust core creates a randomized private OS-temp directory, exports
  the verified source with SQLCipher's supported `ATTACH ... KEY ?` and
  `sqlcipher_export`, preserves schema metadata, checks the encrypted
  file header, rejects an incorrect key, reopens with the correct key,
  compares every schema object and record, then deletes the temporary
  encrypted file and containing directory.
- The independent Tauri command also revalidates destination-path
  safety, Alpha schema, and full in-memory source fidelity; all final
  destination paths are *preflight-only*, never opened for writing.
- A zero-change test is required because staged corrections currently
  are verified only in memory; they are **not** applied to the temporary
  ciphertext. No application installation, Host claim or migration is
  enabled.

## Shadow manual acceptance

1. Run the new portable Windows EXE.
2. Inspect the existing Alpha database. Repeat the memory rehearsal with
   **0 staged edits**, expecting `fullDataCopyVerified: true` and, if
   data is unchanged, 27 application tables, 111 columns and 143 rows.
3. On Data Review, enter and confirm a strong **temporary test** key.
   Click the explicit disk test button. For an unencrypted source,
   the existing source unlock password may be blank.
4. Expected response: `temporaryEncryptedCopyVerified: true`,
   `ciphertextHeaderVerified: true`, `wrongKeyRejected: true`,
   `fullDiskCopyVerified: true`, `temporaryFilesRemoved: true`.
   The disk-copy row/table counts should match the memory rehearsal.
5. The reviewed proposed permanent destination file must **not exist**,
   and all original source values must remain unchanged.
6. Stage one allowed edit and confirm the temporary disk-test action
   rejects it until the changes are cleared and a new zero-change
   memory rehearsal succeeds.
7. On final Review, verify the independent temporary encrypted-copy
   proof is present, but `encryptedDestinationVerified: false`,
   `destinationCreated: false`, `migrationEnabled: false` and
   `executionEnabled: false`.

No generated artifact is a release installer or an executable migration.
Temporary-file cleanup and all three native builds must be checked before
a real durable encrypted target migration is considered. The required
strong NEW destination password for every installation remains a separate
future security gate.
