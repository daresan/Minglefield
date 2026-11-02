# P1.4f.2g.1 — Unified package lock target (draft)

Status: **format contract only**. No writer, migration, package resolver, installer or claim that any game already has installed packages.

## Decision and scope

- `minglefield.yaml` is the future **declaration** of requested packages/dependencies; its syntax is not finalized in this step.
- Root `minglefield.lock` is the **single future authoritative resolved package lock** for game integrations and, eventually, other portable package kinds. It is not a verification certificate.
- `.minglefield/project.json` remains the existing workspace identity manifest. MAP discovery manifests and protocol versions remain separate.
- `.minglefield/integrations.lock.json` is a **read-only legacy alpha input**, not a second authoritative lock. Do not write or auto-migrate it. The current Game inspector continues to read it until a deliberate cutover.
- The registry supplies curated identity/source mappings, not locally installed versions; external sources require separate explicit authorization.
- An entry in either lock is **declarative**; no field in a user-editable lock establishes trustworthy verification.

## Proposed root lock shape

The JSON document below is illustrative; the companion JSON Schema is a **draft target**, not an accepted persisted format:

```json
{
  "lock_version": "0.1",
  "project_id": "game.example",
  "packages": [
    {
      "package_id": "community.alice.godot",
      "kind": "game_integration",
      "version": "1.2.3",
      "publisher": "alice",
      "release_source": {"provider": "github", "repository": "alice/godot"},
      "artifact": {"reference": "release-asset-1", "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
    }
  ]
}
```

`project_id` must match the authorized game registration; package IDs must be unique. The lock may record an optional immutable source revision in a future revision. Version comparison uses a standard version library, not handwritten SemVer parsing. Additional package kinds require explicit schema definitions; do not accept arbitrary kinds in v0.1.

## Read precedence / migration policy

1. **Neither lock exists:** installation state unknown, never inferred empty.
2. **Only alpha lock exists:** keep the current read-only alpha inspection, label it legacy/unverified. No migration and no invented installed versions.
3. **Only root lock exists (future reader):** validate structure, project binding, sources and integrity declarations; verification remains unknown until independently attested.
4. **Both exist:** report `conflicting_lock_sources` for manual review. Do not silently prefer one or merge entries.
5. **Malformed, unsupported, symlinked or mismatched files:** manual review; no writes or fallback that conceals an error.

The current alpha inspector does **not yet implement** rules 3–5 for root `minglefield.lock`. They are acceptance criteria for a future read-only cutover, not claims about present behavior.

## Completion gate and return to Game plan

- Draft root-lock schema and offline conformance tests.
- Explicit legacy/collision policy; no changes to game files.
- Later: read-only root-lock inspection and separate artifact/source verification evidence, then **opt-in integration updates**.
- Return to the planned Game workflow (asset management, build/test/launch, and human/agent development), rather than expanding a general-purpose package manager.
