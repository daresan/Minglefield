# Minglefield Integration Registry v0.1 — Draft

## Decision
Minglefield's public repository maintains the **curated** integration registry. External developers remain free to publish integrations from independently controlled repositories without Minglefield approval. Registry inclusion is an opt-in review process, not a prerequisite for local use.

## Trust boundaries
- **Official:** maintained and reviewed by Minglefield; reserved `minglefield.*` IDs.
- **Community:** independently published; submitted through review, with verified publisher control over the declared release source. Use `community.<publisher>.*` namespace; publisher collision and transfer policy must be enforced during review.
- **External / unregistered:** explicitly added and authorized by the local user, not silently promoted into the curated registry. Source configuration and trust decisions belong in a future local external-source workflow, not in the official registry.

Only `official` and `community` entries appear in the curated registry. The `trust_tier` field denotes curation, **not** an assertion that code is safe.

## Source and versions
- Each entry binds a stable `integration_id` to its publisher and release source. The current adapter supports GitHub Releases; provider-neutral identity must remain independent of GitHub.
- GitHub Releases and tags are the publication mechanism; the registry is **not** a duplicate release catalog. No fabricated versions or unverified entries.
- A release from a game repository or Minglefield platform repository is **not automatically** an integration release. Release identity, artifact provenance, version and compatibility still require a separately specified verification contract.
- An update to an existing entry's source, publisher, trust tier or ID requires explicit security review; no silent source redirection.
- The first registry is intentionally empty until an actual integration publisher and release are verified.
- `registry_version` versions the registry document format, not the MAP protocol, a game project, or an installed integration.

## Validation and admission
JSON Schema checks document shape. Additional cross-record rules are required: unique IDs, reserved namespace, publisher/source ownership evidence, review/audit history and safe source-change handling. A JSON file alone cannot prove publisher ownership or release integrity.

## Future work
1. Add deterministic offline registry validation, including duplicate IDs and namespace restrictions.
2. Add reviewable publisher/source verification workflow.
3. Implement read-only, owner-scoped installed-integration discovery; unknown legacy installations stay unknown.
4. Compare verified installed versions against verified integration releases with a standard SemVer dependency.
5. Add explicit opt-in external sources, preview, confirmation, integrity checks and audited installation; never execute code merely by loading registry metadata.
