# P1.4f.4 — Game installation alpha foundation boundary

## Scope and status

This milestone covers **future game integrations**, not installing or updating
Minglefield itself. The alpha foundation is implemented, subject to CI
acceptance. No real game, integration partner or game installer is required
for this limited milestone.

Available foundations:
- validated manifests and plan digests;
- isolated installation staging and recovery inspection;
- owner/project/operation-scoped journal authorization;
- experimental native Windows relative-handle inspection and single-file
  disposition (internal only);
- read-only cleanup planning and persistent cleanup-intent primitives;
- synthetic conformance and security regression tests.

## Explicitly not delivered

- No user-facing installation into game repositories.
- No automatic game update, migration, rollback or production cleanup.
- No guarantee of compatibility with third-party game repositories.
- No automatic replay of interrupted cleanup operations.
- No HTTP exposure or authorization granted by read-only snapshots.

The Windows single-file experimental executor is not a complete bulk cleanup.
Its filesystem and SQLite operations are not one atomic transaction.
The progress journal primitives are **not yet wired** to that executor; they
cannot be interpreted as durable evidence for operations performed by it.
Ambiguous outcomes require manual review. The pure reconciliation function
does not authorize deletion.

## Acceptance

Run the existing MAP validator and the game-installation cross-platform
security suite in GitHub Actions. The new
`test_game_integration_install_alpha_acceptance.py` verifies synthetic
invalid plans, authorization denial, plan-digest mismatch, corrupt staging,
unrecorded missing files, uncertain intents and read-only recovery behavior.
CI success is required before calling the milestone accepted.

## Deferred work

Real game installation, conflict handling, rollback, audit trail and Git
repository preservation are deferred until a real game integration supplies
concrete requirements. These are **not** acceptance criteria for the alpha.

The **Minglefield platform installer/updater** is a separate priority:
install/update Minglefield code and Python dependencies, handle database
migrations and configured host services/runtimes without hardcoded machine
paths. It must not be confused with game integration installation.
