# P1.4f.3 — Game Integration Update Assessment Contract v0.1 (draft)

Status: **contract only; no installation authority**. Scope: the existing owner-scoped Game integration release discovery and preview. No new package manager, lock writer, registry admission path, or installer.

## Authority and input boundaries

1. Authorization of the authenticated owner, host and project precedes repository access, release discovery, or filesystem inspection. Never use a client-supplied repository or source as authority.
2. The validated curated registry (or a separately authorized, project-scoped source in a future explicit contract) supplies publisher and release source. An editable `minglefield.lock` is a declaration only.
3. The current discovery comparison uses `declared_version` and PEP 440 stable public versions; it is not an installed-version comparison. Preserve `comparison_basis: declared_version`, `verification_state: unknown` and `installation_allowed: false` until independent installation evidence exists.
4. Release notes, tags and GitHub changed-file listings are **untrusted advisory metadata**. They must not be interpreted as executable instructions, compatibility proof, migration authorization, artifact integrity or installed-file evidence.

## Assessment dimensions (independent, fail closed)

| Dimension | Required evidence for a positive result | Insufficient / negative result |
| --- | --- | --- |
| Source/release identity | Authorized registry source and independently bound release/asset identity | Unknown or invalid; stop before installation |
| Installed baseline | Trusted installer-origin journal and independently rechecked installed files, scoped to owner/host/project/integration | `unknown` even when lock declares a version |
| Compatibility | Versioned, validated compatibility contract bound to the exact release and target Game/runtime capabilities, evaluated against trusted local facts | `unknown` with manual review; confirmed mismatch is `incompatible` |
| Migration | Versioned, validated migration plan bound to the source and target releases, enumerating operations, prerequisites, data effects and recovery requirements | `unknown` with manual review; a plan is not permission to execute |
| Local conflicts | Read-only snapshot of the target paths, tracked/untracked Git changes, ownership and overlaps with unrelated Game files | `unknown` when snapshot incomplete; confirmed collision is `conflict` |
| Artifact integrity | SHA-256 of exact artifact bytes checked against an independently trusted expected digest | `unknown` or `invalid`; never trust lockfile digest alone |
| Approval | Explicit authenticated owner consent bound to host/project/integration, source, release, artifact digest, assessed changes and transaction nonce | Missing/stale approval blocks installation |
| Recovery | Verified staging, journaled atomic commit strategy, backup/rollback and crash recovery for all affected paths | Unknown or incomplete recovery plan blocks installation |

A reviewer acknowledging an `unknown` result does **not** transform it into a verified result. Manual review can inform a future explicit decision, but cannot bypass source, integrity, authorization or recovery gates.

## Preview semantics

Keep existing `preview.release_notes`, `preview.changed_files`, `preview.compatibility`, `preview.migration`, `preview.artifact_integrity` and `preview.installation_allowed` fields. New assessment dimensions must be additive, independently typed, and must not silently change the meaning of existing fields.

- `preview.state: incomplete` while any required assessment lacks evidence.
- `compatibility.state: unknown` / `reason: no_verified_compatibility_contract` and `requires_manual_review: true` until the bound contract is actually validated.
- `migration.state: unknown` / `reason: no_verified_migration_plan` and `requires_manual_review: true` until the bound plan is actually validated.
- File comparisons marked `available` mean metadata was retrieved, **not** that local changes are safe or that migration is unnecessary.
- UI renders all remote text as text, never HTML. Unknown remains neutral; confirmed conflicts must not appear as safe.
- This P1.4f.3 contract adds **no install button or execution path**. `installation_allowed` stays false.

## Implementation sequence and acceptance

1. Add offline assessment classifiers and negative tests with explicit provenance parameters; keep the current preview response backward compatible.
2. Bind compatibility contracts and migration plans to exact authorized release identities; define their JSON Schemas before accepting third-party claims.
3. Add read-only local conflict inspection and scoped owner authorization, without changing the Game Git working tree.
4. Expose each assessment and its evidence limits in the existing Game preview; verify JavaScript syntax and browser interaction.
5. Only in P1.4f.4: authenticated opt-in, trusted artifact digest, staging, audited commit, rollback/recovery, post-install reinspection and end-to-end tests.

Acceptance for this contract-only step: documentation and regression tests pass on Windows; no Game repository, Alpha DB, host configuration, runtime or production registry is modified.

References: `docs/GAME-DELIVERY-CONTINUITY.md`, `docs/GAME-INTEGRATION-VERIFICATION-v0.1-DRAFT.md`, `docs/GAME-INTEGRATION-UPDATE-DISCOVERY.md`.

## Repository identifier policy (schema v0.1)

The compatibility and migration declaration schemas accept a GitHub source as
`owner/repository` with exactly two nonempty segments. Each segment may contain ASCII letters, digits, underscores, dots and hyphens,
including a leading dot (for example `owner/.mygame`). Segments consisting
**only** of dots (including `.`, `..` and `...`), backslashes, empty
segments and additional path separators are rejected.
This is a deliberately conservative assessment-document policy; it is not a
claim about every name GitHub itself might accept. The same rule applies to
both assessment schemas. Schema acceptance is never proof of authorized source.

This policy is scoped to assessment-document source identifiers; it does not rename or constrain Game project repositories. Centralization with the existing registry and lock source identifier validation should be a separate compatibility-reviewed change, not an implicit schema migration.
