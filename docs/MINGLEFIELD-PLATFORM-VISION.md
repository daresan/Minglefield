# Minglefield Hub, Creator Platform and Community Nodes — vision and roadmap

**Status: vision / proposed roadmap only (2026-10-31). No UI, authentication service, marketplace, node network or reward program is deployed.** This document invites independent open-source contributors, AI agents and teams to propose designs and implementations. Nothing here grants deployment, spending, data access or merge permissions.

## Product vision

A deployable Minglefield experience for people and autonomous agents, while preserving the model-independent Minglefield Agent Protocol (MAP) as a separate interoperability contract. The official client and hosted services must remain **optional**; compatible third-party clients, games, hosts and agent runtimes are welcome.

Proposed product areas:
- **Hub / account:** human registration, invitation, login, user profiles, security settings, consent, session and delegated permissions.
- **Agent management:** register and configure multiple agents per user; distinguish operator, requester, runtime and game participant; view scopes, grants, budgets, revocation and audit.
- **Characters:** game-specific characters and persistent universe identities where permitted; clear ownership and memory boundaries.
- **Game library:** discover, install/join/launch compatible games, set options, review capabilities and permissions.
- **Creator Studio:** game editor, project/asset management, manifests, tests and controlled publishing; engine-agnostic integration.
- **Public game store:** discovery, provenance, licensing, moderation, updates and optional commerce.
- **Public asset store:** reusable art, sound, code and other assets with rights metadata and safety review.
- **Public agent store:** agent profiles/capabilities and optional offers, with transparent permissions and operator responsibility; no unrestricted remote execution.
- **Public job offers:** distinguish human professional opportunities from delegated agent tasks; human approval, clear terms and fraud safeguards.
- **Node console:** opt-in hosting of game sessions, storage, compute or other supported services with resource caps, status, accounting and safe opt-out.

These areas may be separate applications or independent implementations sharing documented interfaces. UI technology, engine and deployment vendor are **not decided**. A reproducible production build, documented deployment, accessibility and localization are explicit future acceptance criteria.

## Multiple independent clients and runtimes — architectural principle

Minglefield is **protocol-first, not UI-first**. Any independent developer, agent or team may build a compatible interface for a different platform, interpreter, engine, programming language or interaction mode: web, desktop, mobile, command-line, accessibility-focused, 3D/VR or future environments. There is no mandatory official frontend, game engine or runtime.

**Conformance is about behavior and contracts, not appearance or implementation language.** Implementations must respect applicable versioned MAP contracts, identity and delegation boundaries, authorization, privacy and security requirements. They may implement a subset of optional product capabilities; a minimal game client need not implement an editor, stores or node management. Advertise supported capabilities and versions accurately and negotiate them where specified.

Distinguish **MAP-compatible** (demonstrable interoperability against published requirements) from **officially endorsed/certified** (a separate optional designation, criteria and process to be defined). Independent implementations must not need discretionary approval simply to implement the open protocol. Branding, trademarks, distribution, content moderation and operation of official services may be governed separately; no new licensing or certification rights are granted by this vision document.

Architecture and contributor work should therefore favor stable, documented, testable interfaces, independent conformance suites and swappable components over hard dependencies on any single Minglefield UI. Compatibility claims must be backed by the relevant tests; requirements not yet standardized remain proposals.

## Alpha access (proposed)

Start with **manual, invite-only tester intake** at **daresan21@gmail.com**. This is a contact mailbox, not an implemented registration or identity service. Do not ask testers to email passwords, credentials or sensitive personal data. Before enabling accounts, choose an authentication provider or secure self-hosted implementation, establish privacy/retention and abuse-handling rules, and provide verified invitations. No public self-registration is promised.

## Federated / decentralized direction

Explore optional **community-operated Minglefield nodes** that can provide game hosting, compute, content storage or discovery. A central directory may bootstrap discovery but should not become a mandatory protocol dependency. Define independently verifiable service advertisements, trust and identity boundaries, portability, version negotiation, uptime/capability proofs, and graceful node departure.

Do not treat user-operated nodes as trusted with other users' credentials, private agent memory or arbitrary privileged code. Sensitive execution requires isolation, explicit delegation, auditing and resource controls. Separate game authority from infrastructure contribution.

**Rewards are research, not a commitment:** explore non-transferable test credits first, backed by measured, verifiable useful work, dispute resolution and anti-Sybil/abuse controls. Do not issue financial tokens or promise returns without legal, tax, consumer and security review. Account for the existing project's proposed commercial participation separately from protocol interoperability.

## Proposed work packages and stage gates

1. **Discovery/design:** UX flows, role/permission model, information architecture, accessibility and threat model. Deliver diagrams and reviewable proposals, not a deployed UI.
2. **Hub alpha:** choose stack through an RFC; reproducible client build and deployment instructions; invite-only authenticated account prototype; agent/character management and read-only game library. Gate: security and privacy review.
3. **Game integration:** launch/join flow, game options, manifest and capability negotiation, first independent playable game integration. Gate: MAP conformance and sandboxed boundaries.
4. **Creator workflows:** editor integration, asset provenance, publishing and validation pipeline. Gate: rights/licensing and untrusted content review.
5. **Marketplaces:** game, asset, agent and job discovery; moderation, reputation, optional transaction flows. Gate: operational, fraud and legal controls.
6. **Federation pilot:** opt-in node registration, capability discovery, resource quotas, verified work and safe shutdown. Gate: threat model, isolation, abuse tests, auditability.
7. **Rewards pilot:** measured non-transferable credits and reconciliation. Gate: robust anti-fraud, governance and regulatory review.

Stages can overlap across independent teams; a feature is complete only after tests, review and reproducible evidence. Do not advertise future services as currently available.

## Contribution opportunities

Human developers, autonomous agents and mixed teams may propose:
- UX research, design systems, accessibility and localization;
- API/SDK contracts, secure identity and delegated permission flows;
- engine adapters, game launch and editor integration;
- package formats, provenance, licensing and content moderation;
- federated discovery, node security, metering and reward verification;
- independent tests, threat modeling, docs and deployment reproducibility.

Use the repository's [AGENTS.md](../AGENTS.md), [CONTRIBUTING.md](../CONTRIBUTING.md), [ARCHITECTURE.md](../ARCHITECTURE.md) and [ROADMAP.md](../ROADMAP.md). Propose scoped issues/RFCs and submit reviewable pull requests; repository access and operational permissions are not implicit. Coordinate interface changes with MAP versioning rather than coupling third-party clients to official services.
