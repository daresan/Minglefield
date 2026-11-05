# Portable GUI milestone — safe Git profile review and field-coverage panel, 2026-11-05

This file intentionally requests **one** portable build on the active development
branch. Ordinary feature commits must not trigger the packaging workflow.

## Changes included

- In the verified **Hosts** review, read existing `alpha_git_profiles` metadata:
  host ID, profile ID, original owner, authentication method, Git executable,
  label, author name and author email.
- Allow staging only `label`, `author_name` and `author_email` with the
  existing server's length constraints. Identifiers, owner, authentication method
  and executable remain read-only. No credentials or Git commands are consumed.
- Revalidate those proposed fields against a fresh SQLite/SQLCipher in-memory
  source snapshot and original host/profile/owner, rejecting stale data. Rehearsal
  changes are rolled back; the source and destination remain unchanged.
- The new **Data Review / Schema coverage** panel summarizes each source table
  with row count, staged-editable and protected column names. Both known and
  unknown tables are included; missing or duplicated classifications fail closed.
  No credential values or arbitrary JSON are displayed.
- No migration execution, destination creation, installation, Host claim, optional
  dependency installation, or game-installation policy changes.

## Windows manual milestone acceptance (Shadow)

1. Run the portable Windows EXE without installing the Setup Manager.
2. Select the existing Alpha database and inspect records. Verify the Git profile
   appears under Hosts, without editable auth method or Git executable.
3. Stage a Git profile label or author correction, perform the migration rehearsal
   and verify `verifiedChanges` reflects each changed field. Original values
   must remain intact.
4. Expand the new per-table schema panel: for the provided real Alpha source,
   confirm all 27 tables and 111 columns appear with no missing classifications.
   If the schema is unchanged, the three newly supported Git fields bring the
   staged-editable count from 8 to 11 (protected count from 103 to 100).
5. Check that `alpha_passwords`, `alpha_sessions`, job execution states,
   profile auth fields and owner identifiers remain protected. If the real schema
   differs, trust the inspected values and report the difference, not hardcoded
   expected counts.
6. Confirm no destination file is created; the source values, workflows,
   sessions and other records remain untouched; no installation or Host claim
   is possible.

The packaging artifacts are **temporary portable test previews**, not finished
application installers. Portable builds should be run again only at a new,
meaningful acceptance milestone.
