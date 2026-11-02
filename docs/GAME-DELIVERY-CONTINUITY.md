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
