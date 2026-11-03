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

## Build-time GitHub ancestry check (implemented, not yet an installer release gate)

`installer/scripts/verify_release_source.py --source PATH` checks a version-1 UTF-8 source record against live GitHub REST API metadata using the Python standard library. It is a **release-build tool only**, not a Python requirement for end users. The source record contains `version`, `repository_id`, `repository`, and a full 40-character `commit` hash.

The checker fetches the repository by its claimed owner/name, requires its stable GitHub ID and name to match, confirms the exact commit exists, pins the currently observed default-branch head, and verifies that the release commit is its ancestor using the GitHub compare endpoint. For the official upstream ID `1440772489` it additionally requires canonical name `daresan/Minglefield`, default branch `main`, and GitHub's `protected=true` branch marker. Other repositories may verify their own ancestry without being misrepresented as upstream-recognized. No upstream fork-recognition registry is implemented yet.

All negative cases fail before a success JSON result. Success explicitly reports `artifact_authenticated=false` and `installation_authorized=false`. GitHub HTTPS/API evidence is not a cryptographic binary-build attestation and does not establish that a released installer was built reproducibly from that commit. The standalone tool is not currently invoked as a release-packaging gate because an actual package production workflow has not yet been implemented. Offline tests for identity mismatches, unprotected upstream, ancestry divergence and independent forks run on all three operating systems in `installer-rust.yml`.

When implementing actual packaging, run the checker on the intended source record and pin both the checked source commit and final release artifact digests in versioned release metadata. Preserve the independent GPL fork path and the separately optional upstream recognition label.
