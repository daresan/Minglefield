# Portable GUI test milestone — 2026-11-05

**Purpose:** One explicitly requested cross-platform portable build for manual
acceptance of the migration rehearsal introduced on the active feature branch.

**Changes included:** read-only Alpha record review; verified consistent SQLite
snapshot; full mandatory Alpha schema check; every-table row-count inventory;
staged disabled/description/name corrections; snapshot-only transaction rehearsal
with rollback; separate destination path preflight; final wizard review.

**Scope:** Windows portable EXE, Linux AppImage, macOS portable app. These
artifacts are **test previews only**, not finished Minglefield installers.

**Manual acceptance (Windows):**
1. Launch the portable EXE without installing the setup manager itself.
2. Select an existing Alpha SQLite database; confirm users, hosts, effects,
   host jobs, alpha jobs and games render where present.
3. Stage only approved non-security text/disabled changes.
4. Select a different existing directory and an unused destination filename.
5. Run the migration rehearsal, inspect verified table counts and the final
   review; confirm the source and destination are unchanged.
6. Try an already-existing destination and stale original value; both must
   be rejected. Installation and migration execution must remain unavailable.

**Safety gate:** No live source-data mutation or SQLCipher output is enabled.
Only modify this file when the maintainer needs a new milestone test build.
