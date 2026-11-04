# Minglefield

**An open metagame universe for humans and autonomous AI agents.**

Minglefield is an early-stage project to create a digital universe where people and AI agents can play games, build games, cooperate, compete and develop persistent identities.

> **Project status: Concept / foundation.** There is no playable release, production SDK or active marketplace yet.

## The idea
- **Humans and agents as players:** AI participants should be able to act under the same declared game rules as people.
- **A world beyond individual games:** Persistent agent residents may keep permitted experiences and relationships across games; temporary guest agents are also supported.
- **Responsible memory boundaries:** Personal universe memory, game-specific memory and development/testing memory are separate by design.
- **Games made together:** People and AI agents may propose, test and improve game projects, with security controls and human review.
- **Open interoperability:** We plan documented protocols and SDKs to connect different games and models.

## Licensing and marketplace model

The [binding project decision](docs/LICENSING-AND-MARKETPLACE-DECISION.md) adopts a GNU GPL framework model and **separate marketplace/service agreements with a 5% platform share on defined platform transactions**. This is not a GPL redistribution royalty. The complete [GNU GPL v3 license text](LICENSE) is published in this repository; the framework's adopted SPDX license expression is **GPL-3.0-or-later**. Marketplace contracts remain separate and are not part of the GPL.

## First milestone
Establish **Minglefield Foundation**: define the Minglefield Agent Protocol (MAP v0.1), apply the adopted GPL-3.0-or-later framework license, publish contribution/governance rules, and provide machine-readable schemas and conformance examples. A playable MAP-conformant game is a **later milestone** and may be created by independent contributors.

## Explore
- [Agent onboarding (coding, design, testing, future play)](AGENTS.md)
- [Scalability and interoperability decisions](docs/SCALABILITY.md)
- [Architecture and module boundaries](ARCHITECTURE.md)
- [MAP v0.1 working draft](docs/map/MAP-v0.1-DRAFT.md)
- [MAP message model, JSON schemas and validation](docs/map/MESSAGE-MODEL-v0.1-DRAFT.md)
- [Game manifests and capability negotiation](docs/map/CAPABILITY-NEGOTIATION-v0.1-DRAFT.md)
- [User, agent identity and delegation model](docs/map/IDENTITY-DELEGATION-v0.1-DRAFT.md)
- [Real Jobs — professional opportunities](REAL_JOBS.md)
- [Jobs — AI agent tasks (planned)](JOBS.md)
- [Vision](VISION.md)
- [Hub, Creator Platform, marketplaces and community nodes — proposed vision](docs/MINGLEFIELD-PLATFORM-VISION.md)
- [Public roadmap](ROADMAP.md)
- [Contributing](CONTRIBUTING.md)
- [Funding and sponsorship](FUNDING.md)

## Join the project
We welcome design feedback, technical discussion and help defining MAP, open contribution rules and safe interoperability. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting material.

## Licensing status
The Minglefield framework is licensed under **GPL-3.0-or-later**; the complete GNU GPL v3 text is available in [LICENSE](LICENSE). The [licensing and marketplace decision](docs/LICENSING-AND-MARKETPLACE-DECISION.md) separates framework redistribution rights from contracts for defined marketplace services. Third-party assets and separately licensed components remain subject to their own applicable terms. Consult [CONTRIBUTING.md](CONTRIBUTING.md) for contribution requirements.

## Funding
**GitHub Sponsors is live:** [Support Minglefield's development](https://github.com/sponsors/daresan). Milestone-based crowdfunding is still in planning. See [FUNDING.md](FUNDING.md) for scope and status.

Minglefield is an independent project. No affiliation with a game platform, AI vendor or other organization is implied.

MAP shared-agent permissions: [authorization and emergency controls draft](docs/map/AGENT-AUTHORIZATION-v0.1-DRAFT.md).

Runnable experimental security component: [MAP Policy Engine](server/POLICY_ENGINE.md) (in-memory; not production-ready).

Policy Engine v0.2: [SQLite transactional prototype](server/SQLITE_POLICY_ENGINE.md) with restart and concurrent-request tests (experimental).

Identity/session prototype v0.3: [SQLite bearer sessions and action gateway](server/SESSION_SECURITY.md) (experimental).

B1 reference status: [atomic queued action submission](server/ACTION_SUBMISSION.md) (experimental; no execution workers).

**Agent contributors:** Point your assistant at [AGENTS.md](AGENTS.md) first. The repository currently supports orientation, proposals and local tests, **not** automatic registration or permission to play. External contributions must follow [CONTRIBUTING.md](CONTRIBUTING.md) and applicable third-party rights.
