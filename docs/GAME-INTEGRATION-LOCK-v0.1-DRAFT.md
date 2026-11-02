# P1.4f.2e — Game integration installation lock v0.1 (draft)

This is a **proposed local game-project lockfile contract**, not a migration, installed-version claim or package installer. Proposed location: `.minglefield/integrations.lock.json`. This complements (and does not replace) the future portable `minglefield.yaml` / `minglefield.lock` package model. Before adopting it as a persisted format, reconcile the naming and authority with that model.

## Ownership and scope

- The public Minglefield registry defines curated integration IDs and trusted release-source mappings; GitHub Releases remain the publication source.
- A lockfile is **per game project**. It records observed/installed package identities, versions and artifact provenance, not global latest versions or user permissions.
- `project_id` must equal the owner-authorized registered game project; check before accepting a lockfile.
- The lockfile must be treated as untrusted local input, even when schema-valid. An editable `verification_status: "verified"` is **not evidence** of cryptographic verification.
- The authoritative verification outcome must come from a trusted installation/verification process that checks the artifact digest against actual bytes, binds publisher and release identity to the trusted source, and records an auditable result. Until that process exists, the application must not claim a version is verified merely because a file says so.
- `artifact.reference` is an opaque release artifact locator, not an executable URL. No fetch or execution during inspection.
- `artifact.sha256` is a lowercase 64-character digest declaration, **not** evidence that the artifact has been checked.
- `source_revision` is optional immutable source provenance; a Git tag alone is not necessarily immutable.
- Version syntax and SemVer comparison must use an agreed standard library, not a custom implementation. The draft only requires a nonempty version string.

## States and safety

- Missing lockfile: installation state **unknown**, never an asserted empty installation.
- Explicit empty `integrations: []` is a recorded empty set, but not proof that no unmanaged integrations exist.
- Duplicate integration IDs and mismatched project IDs are errors. Malformed, unsupported, or symlinked lockfiles require manual review.
- A lock entry whose ID is not in the curated registry may represent a user-authorized external integration; **do not automatically trust or reject its existence**. Its source authorization is separate.
- A lock entry with a curated ID but conflicting publisher/source must be flagged; no silent source substitution.
- Reading a lockfile never changes the repository, invokes Git, downloads a release or installs software.

## Next implementation gates

1. Validate schema and duplicate identities with offline conformance tests.
2. Add owner-scoped, symlink-safe, read-only lockfile inspection with explicit legacy unknown state.
3. Specify installer-attested verification evidence and reconcile with portable package lockfile before any writes.
4. Only then expose reliable installed-version comparisons and opt-in update installation.

## P1.4f.2 version-policy clarification (2026-11-03)

The provisional SemVer wording above is superseded for read-only discovery by the
[PEP 440 stable-channel and separate comparison-state contract](GAME-INTEGRATION-UPDATE-DISCOVERY.md).
Declaration comparison never promotes installation or artifact verification.
