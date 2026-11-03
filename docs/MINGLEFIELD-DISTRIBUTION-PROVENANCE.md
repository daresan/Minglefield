# Minglefield distribution provenance and fork recognition

Decision 2026-11-04. Applies to installing Minglefield itself, not third-party games.

## Existing license decision remains binding

The intended GPL-family model (`GPL-3.0-or-later` for Minglefield-owned core code) is unchanged. Its adoption still requires rights review and an actual LICENSE/SPDX change. Under GPL terms, upstream permission cannot be a prerequisite for exercising licensed rights to fork, modify, copy or redistribute. No new restriction is imposed here.

## Official versus recognized versus independent

- **Official upstream:** releases from `daresan/Minglefield` based on reviewed, protected `main`.
- **Upstream-recognized fork:** an independent distribution whose maintainer has received an explicit upstream recognition for a defined repository and release scope.
- **Independent fork:** a fork published under its applicable license without upstream recognition; this is not inherently unauthorized software.
- **Unverified provenance:** insufficient evidence to assert any trusted source.

Upstream recognition is permission to claim recognition, **not** permission to exercise GPL rights. Recognition can be withdrawn for future claims without revoking existing GPL rights. Only the upstream maintainer controls the upstream recognition registry; an independent fork cannot self-assert that status. Use immutable GitHub repository IDs, not just mutable owner/name strings, when implementing the registry.

The upstream installer must not confuse a missing upstream endorsement with unlawful redistribution. Branding, official service operation and the separate Marketplace are different questions subject to the existing policy and legal review.

## No paid certificates

No commercial publisher certificate or paid signing service is required. Release source identity and integrity should use free Git/GitHub mechanisms. SHA-256 checks integrity relative to a manifest but does not prove the manifest or binary originated from the reviewed source commit. The current Rust publisher policy is a fail-closed placeholder, not a working GitHub provenance verifier.

## Implementation sequence

1. Versioned, read-only source/release metadata, tied to an immutable repository ID and commit.
2. Verify source release provenance and artifact integrity, with explicit evidence limitations.
3. Optional upstream-controlled recognition registry for forks.
4. Present official/recognized/independent/unverified distinctions in GUI and CLI.
5. Only enable real installation after runtime, lifecycle, security and cross-platform acceptance gates.

The stricter rules for installing third-party games are independent and must not be reused as Minglefield application distribution policy.
