# Game delivery continuity: P1.4f through P1.5 and beyond

Decision confirmed 2026-11-02: **Do not stop at P1.4f.2g.** Finish the complete integration-update user journey before starting P1.5. Avoid unrelated infrastructure expansion, not the necessary completion work.

## P1.4f acceptance gate

In an authorized Game workspace, the user can:
1. Inspect installed integrations and their trusted publisher/release source.
2. Discover releases and compare installed/available versions, with offline and unknown handled honestly.
3. Preview release notes, changed files, compatibility constraints and migration requirements.
4. Explicitly approve an update, with source and artifact integrity checks, conflict detection and audit.
5. Recover or roll back a failed update without damaging the independent Game Git remote, branch, history or unrelated files.
6. Re-inspect the installation and confirm the resulting version/state.

Test successful updates, source mismatch, artifact tampering, unavailable release metadata, local conflicts, partial failure and recovery. No automatic updates or silent repository mutation.

P1.4f.2g.1 unified-lock contract was confirmed on the Windows host: 4 package-lock, 8 integration and 26 Game-project tests passed (38 total). Later steps: 2g.2 verification evidence, 2g.3 read-only unified lock inspection, then complete preview, approved installation and end-to-end testing.

## P1.4f.3 implementation and contract alignment (2026-11-02)

Current read-only behavior:
- Curated registry identity and release source are checked before remote release discovery.
- The comparison uses a *declared* lock version, not a verified installed version. Results remain `state: unknown` / `installation_not_verified`; `version_comparison` is informational only.
- Missing or invalid installation declarations produce an unknown status, not a verified empty installation or a green up-to-date signal.
- Release notes and changed-file comparison are advisory; compatibility, migration and artifact integrity remain unknown, and `installation_allowed` is false.
- The Alpha UI displays these limitations; a JavaScript syntax regression test now checks the served page. A real browser interaction test is still pending.

Remaining gates before claiming update availability or enabling installation:
1. Define and implement independently verified installed-version evidence, consistent with `GAME-INTEGRATION-VERIFICATION-v0.1-DRAFT.md` and the authoritative unified-lock design. Do not promote legacy lock declarations to evidence.
2. Resolve the SemVer versus PEP 440 version comparison decision and define stable/prerelease/tag handling; do not silently equate MAP versions with package versions.
3. Provide trustworthy compatibility and migration assessments, including conflict checks and explicit manual-review paths.
4. Require explicit approval, authorized source and artifact digest verification, auditable installation, rollback/recovery and post-install reinspection.
5. Add negative and end-to-end tests for source mismatch, tampering, offline metadata, local changes, partial failure and recovery; add browser-level tab/overlay interaction coverage.

Signal contract until verified evidence exists: grey for unknown/unverified; yellow may mean a newer release than a *declaration* or required manual review, never a proven installable update; red for confirmed invalid/conflicting evidence; green requires independently verified installation plus reliable current release comparison. Do not introduce a parallel package, lock or installer contract.

## P1.5 next: Game workspace and asset management

Extend the existing Game tab and project registration rather than rebuild them:
- Per-game staging/output settings and persistent asset registration.
- Native local file selection; durable asset IDs and job bindings.
- Upload staged inputs to ComfyUI only when the job actually starts.
- Game build/test/launch/logs, browser preview where supported, controlled local launch otherwise.

Define user-facing acceptance tests before closing P1.5.

## Longer-term stages, not forgotten

- Stage 2: reproducible playable MAP-compatible independent game, human/AI contributions.
- Stage 3: persistent universe, lobby/homespace, persistent and guest agents, separated memory contexts, portals.
- Stage 4: public SDK and creator workflows.
- Stage 5: funding, creator commerce and legal review.
- Stage 6: interoperability, optional distributed hosting and additional engines.
- Cross-cutting: Developer Teams and Game Teams, explicit agent delegation, per-action authorization and isolation.

Keep ROADMAP.md as the main milestone index. This note defines acceptance gates and does not claim these features have shipped.

## P1.4f.2 clarification (2026-11-03)

[Read-only discovery](GAME-INTEGRATION-UPDATE-DISCOVERY.md) now defines the PEP 440
stable-channel decision and explicit declaration-only comparison states. This resolves
the version-policy question above for discovery; verified installation and the complete
P1.4f.3/P1.4f.4 acceptance gates remain open. No Game data migration is performed.

## P1.4f.3 assessment contract (2026-11-03)

The fail-closed, contract-only assessment specification is recorded in
[Game Integration Update Assessment v0.1 draft](GAME-INTEGRATION-UPDATE-ASSESSMENT-v0.1-DRAFT.md).
It defines independent compatibility, migration, local-conflict, source, integrity,
approval and recovery evidence gates. No installer, trust promotion or runtime
mutation is introduced by this documentation step. Implementation and Windows
acceptance tests remain pending.
