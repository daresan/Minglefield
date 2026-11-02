# Minglefield Repository & Package Architecture v0.1 — Draft

Status: proposed design, 2026-11-01. No Git provider integration, package registry, asset store or commerce implementation is claimed.

## Decision and rationale
Use Git repositories as the primary **versioned content layer** for games, portable agent definitions, skills, settings, source assets and project templates. Do not build a proprietary Git hosting platform initially. Support local Git first, then GitHub, GitLab and self-hosted Git through a replaceable provider interface. Minglefield remains protocol-first and independent of a mandatory central server or provider.

Git is **not** the authoritative store for runtime identity, live agent memory, active delegations, revocation, credentials, execution policy, transactional accounting or payment settlement. Those require Minglefield runtime/policy services and suitable databases. Binary assets may use Git LFS or content-addressed/object storage; large model weights should use external model registries.

## Resource types and package formats
- Game repository: code, game manifest, MAP compatibility declaration, dependencies, CI/conformance checks, team development workflow.
- Agent package: agent manifest, portable soul/baseline memory, selected skills, portable settings, optional reviewed memory snapshot. Agent identity and live memory are separate from this package.
- Asset package: manifest, provenance, license, dependency metadata, content hashes, files or references to LFS/object storage.

Draft repository layout:
```text
project/
  minglefield.yaml
  minglefield.lock
  LICENSE
  README.md
  game/
  agents/
  assets/
  tests/
```
Manifest format, version ranges, package IDs, integrity hashes and resolver rules remain to be standardized. Manifests must declare the applicable MAP profile/version, dependency identities, provenance and licensing metadata. Publishing and execution should validate compatibility and applicable authorization. An editable manifest is **not** a security or payment enforcement mechanism; server-side verification and signed/reproducible release metadata are needed for trusted publication.

## Repository provider boundary
A provider-neutral adapter should expose: inspect/create/open repository, clone/fetch, list branches/tags, read commit, stage/commit, push, compare/diff, and request review/merge when supported. Never assume GitHub-specific identifiers in MAP core schemas. Begin with local Git and an optional GitHub adapter. Provider authentication must be user-authorized, minimally scoped and kept in a secure credential store; no access tokens in agent packages or repository manifests. Do not execute repository hooks or arbitrary build scripts on untrusted clones.

## Visibility and transfer
- Private: selected collaborators and teams; provider access controls apply.
- Public: anyone may clone under the applicable license.
- Clone: independent package copy with separate identity/runtime unless explicitly linked.
- Follow/update: opt-in package version tracking.
- Shared agent: multiple authorized operators/users access one durable agent identity under independent MAP delegations; NOT equivalent to cloning a package.
- Component export: owner selects soul, skills, portable settings, and optionally reviewed memory snapshot; redact secrets, third-party data, restricted game memories and credentials.
- Revocation: prevents **future authorized access/actions**; cannot erase previously cloned data. Shared-agent live memory requires concurrency, isolation and audit controls.

## Governance, licensing and commerce
MAP compatibility and conformance are technical requirements for officially recognized Minglefield packages, game sessions and catalog publication. Independent implementations remain possible. The proposed 5% founder/platform participation is a **separate contractual objective for eligible commercial transactions**, not a mandatory MAP wire-level charge or universal open-source license obligation. Official marketplace checkout, rentals, jobs and managed services may enforce agreed commercial terms; external Git clones and independent transactions cannot be universally metered by Git. Creator prices/margins and platform fees require transparent contracts and accounting.

Licenses are **not yet finalized**. The repository's existing ARCHITECTURE.md describes candidate licenses only. Austrian/EU legal review is required for license compatibility, asset rights, contributor terms, data protection, commerce and platform participation. Do not represent the draft as binding license text or as an automatic levy on all forks.

## Implementation gates
1. Freeze draft manifest/package semantics and threat model; create conformance fixtures.
2. Implement local Git adapter, project creation/import, manifest validation and lockfile.
3. Add GitHub authentication and repository operations behind adapter; GitLab/self-hosted follow.
4. Add agent/asset catalog, package cloning, selective export and team access; separate durable runtime identity.
5. Add official marketplace/transaction layer only after legal and accounting review.

## First demonstrable outcome
A user and an authorized local agent work on a versioned game project, run a local ComfyUI asset-generation job through Minglefield, inspect the generated asset and propose a reviewable repository change. No remote LLM hosting is required.
