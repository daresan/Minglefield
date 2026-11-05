# Portable GUI milestone — single destination password and encrypted staged edits

**2026-11-05 — explicitly requested one-time test build** on
`feat/game-integration-updates`. Only changes to this marker trigger portable
packaging on the feature branch. Routine installer commits do not.

## What this milestone adds

- The user enters and confirms the **new SQLCipher database password only
  once on Step 3**. Step 4 has **no second new/test password fields**.
  The temporary encrypted-copy test reuses those existing in-memory inputs.
  Passwords are never added to installation-plan JSON or persisted.
- The existing Alpha source unlock password remains separate and optional
  for unencrypted SQLite; a reentered source key takes precedence when given.
- The existing **in-memory migration rehearsal** applies corrections and
  rolls back; the original source is still never modified.
- The new encrypted-copy rehearsal verifies all the same staged corrections
  against their original values and owner/host identities, commits them
  **only in an isolated, verified RAM copy**, encrypts that copy into a
  randomized private temporary SQLCipher file, tests wrong-key rejection,
  reopens with the Step-3 key, compares all data/schema against the corrected
  RAM copy, closes handles and deletes the temporary directory.
- The 7 supported staged correction kinds are tested: user disabled, agent
  disabled, effect description, effect enabled, Game name, Game path, Git
  profile text. Stale, duplicate and trigger-dependent corrections fail closed.
- Response: `verifiedStagedChanges` equals the current memory rehearsal's
  `verifiedChanges`; `stagedValuesMatchCiphertext: true` proves those
  changes survived the temporary SQLCipher round trip.
- No final destination is created or written. `destinationCreated`,
  `encryptedDestinationVerified`, `migrationEnabled` and
  `executionEnabled` remain **false**; no Minglefield install or Host claim.

## Manual acceptance on Shadow

1. Run the portable Windows executable. Inspect the same existing Alpha
   database (previously 27 application tables, 111 columns, 143 rows).
2. On **Step 3**, set and confirm a strong **new** SQLCipher database
   password once. The password remains masked and is not in JSON.
3. On Step 4, run the normal memory rehearsal with zero changes. Run the
   temporary encrypted-disk-copy test **without reentering the new key**.
   Check `verifiedStagedChanges: 0`, `stagedValuesMatchCiphertext: true`,
   `temporaryFilesRemoved: true` and unchanged source/final destination.
4. Stage one or more changes (e.g. Git label, effect description or Game
   name); rerun the memory rehearsal, then the temporary disk-copy test
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
