# Portable GUI milestone — full Alpha record review, 2026-11-05

This file is changed **only for significant manual test milestones** and
triggers one portable build for Windows, Linux and macOS. Ordinary installer
commits must never trigger portable packaging.

## Implemented for this milestone

- Same-directory migration preview: another, unused filename is permitted.
  Reject the actual source filename, existing files, and source SQLite
  `-wal`, `-shm`, `-journal` sidecar filenames.
- Existing Alpha users **and agents**: display identities, owners, and disabled
  flags; only disabled flags may be staged for migration.
- Hosts: display the existing host owner plus allowlisted Comfy runtime
  metadata (runtime ID, kind, endpoint, enabled, input folder). Raw runtime
  configs, secrets and arbitrary JSON keys must remain unavailable.
- Effects: stage description and enabled flag. No actual execution is enabled.
- Jobs: keep request/job identity and execution state read-only.
- Games: stage project name, repository root, job attachments root and output
  root. Preserve project ID, host, owner, and settings revision.
- A complete database rehearsal rereads and validates all mandatory Alpha
  tables, inventories **every** existing table with row counts, simulates all
  staged changes in an in-memory transaction, checks integrity and referential
  constraints, and rolls back.
- No source database writes; no SQLCipher destination creation; no real
  installation or Host claim.

## Manual Windows/Shadow acceptance

1. Launch portable EXE; select the real Alpha database and verify the category
   tabs show the extra agent, runtime, effect and Game path fields.
2. Choose the **same directory** as the source and a **different unused
   filename**, rehearse with zero changes; it must succeed.
3. Stage an effect activation, agent disabled status and one Game directory
   correction, then rehearse. The verified-changes count should match the
   edits and the table inventory should still include all 27 tables.
4. Try a changed source filename, an occupied target filename, and one source
   sidecar filename as destination. The source's actual filename, existing
   targets and sidecars must fail, with no overwrites.
5. Check actual source values, sessions, passwords and stored workflows remain
   unchanged; ensure the destination does not exist.
6. Confirm that project owner and revision, credentials and job status cannot
   be edited; migration and installation execution remain disabled.

The generated artifacts are temporary test previews, **not Minglefield
application installers** and do not perform any data migration.
