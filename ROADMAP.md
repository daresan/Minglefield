# Public Roadmap

This is a direction of travel, **not** a delivery promise. Milestones and technical choices may change as prototypes are tested.

> **Platform UI and federation:** See [Minglefield Platform Vision](docs/MINGLEFIELD-PLATFORM-VISION.md) for the proposed Hub, agent/character management, game library/editor, public stores, job offers, community nodes and rewards research. This is a contributor-facing roadmap, not a deployed product or committed implementation stack.

## Stage 0 — Public foundation (in progress)
- [x] Establish the public repository.
- [x] Publish the initial project vision, roadmap and contribution guidelines.
- [ ] Select and review open-source licenses before accepting external code contributions.
- [ ] Establish public discussion and issue templates.
- [x] Publish Real Jobs category and initial Austrian legal counsel expression-of-interest call.
- [x] Publish MAP v0.1 non-normative working draft.
- [ ] Complete the initial funding platform setup and compliance checks.

## Stage 1 — Minglefield Foundation (first milestone)
- [ ] Define MAP v0.1: identity, discovery, sessions, observations, actions, permissions, fairness and memory boundaries.
- [x] Add draft game manifest and capability negotiation schemas, examples and conformance workflow (CI result pending verification).
- [ ] Publish machine-readable schemas, example messages and basic conformance tests.
- [ ] Choose and publish open-source licenses for code, specifications, SDKs and documentation as appropriate.
- [ ] Establish contribution, AI-assisted contribution, security and governance rules.
- [ ] Review versioning, compatibility and change management.

**Completion gate:** a publicly documented, testable protocol and clear legal/contribution framework. A playable game is not required.

## Cross-cutting design — human/agent teams (planned)
- [ ] Define Developer Teams and Game Teams as distinct collaboration contexts containing human users and explicitly selected, accessible agents.
- [ ] Specify team creation, invitations/consent, roles, membership lifecycle, agent availability, and join/leave/revocation.
- [ ] Define team-scoped participation without transferring agent ownership, operator authority, private memory or delegation privileges to teammates.
- [ ] Require independent authorization for each agent action: authenticated requester, valid agent delegation, team membership/role and target game/project policy.
- [ ] Define isolation of team development/game resources, audit attribution, and cross-team context/memory boundaries.
- [ ] Prototype and test team permissions separately from simulation-only B2 dispatch; no real effects are authorized.

## Cross-cutting design — task-specialized custom mini-models (planned)
- [ ] Support creating, training or fine-tuning, evaluating, versioning and registering small task-specialized custom models ("mini-models") as reusable Minglefield components.
- [ ] Allow explicitly selected mini-models to be integrated into games and human/agent Developer Teams and Game Teams, including specialized tasks and optional local or externally hosted inference.
- [ ] Define model provenance, training-data rights/consent, licensing, reproducible artifacts, resource budgets, evaluation and compatibility contracts before deployment.
- [ ] Distinguish a mini-model's inference capability from an agent's identity and authority: model attachment must never implicitly grant team membership, access to private memory, delegation or action permissions.
- [ ] Prototype sandboxed inference, model lifecycle management and team/game-scoped access controls; any effects must pass the independently authorized MAP action boundary.
- [ ] Keep model-training infrastructure, formats and runtime backends open for research; this roadmap does not imply an implemented training service.

## Stage 2 — First independent game integration (planned)
- [ ] Validate MAP through a reproducible playable example.
- [ ] Accept implementations from independent human or AI contributors and mixed teams.
- [ ] Publish conformance results, limitations and integration documentation.

## Stage 3 — Persistent universe (planned)
- [ ] 3D lobby and homespace prototype, potentially with Godot.
- [ ] Persistent resident agent identity and temporary guest agents.
- [ ] Isolated universe, game and development/testing memory contexts.
- [ ] Game discovery and portal integration.

## Stage 4 — Creator ecosystem (planned)
- [ ] Public game SDK, manifest, examples and compatibility tests.
- [ ] Safe agent-assisted development workflows with human review.

## Stage 5 — Community funding and commerce (planned)
- [ ] Funding and contribution opportunities; external sponsorship can begin earlier.
- [ ] Explore a marketplace and transparent creator revenue-sharing model, subject to legal and operational review.

## Stage 6 — Interoperability and scale (research)
- [ ] Optional distributed hosting and external game integrations.
- [ ] Accessibility, VR and additional engines as feasible.

**Progress reporting:** Only completed, tested work will be marked as shipped.

- [x] Draft multi-operator agent, delegation, revocation and suspension schemas and illustrative authorization checks.
- [ ] Define authenticated policy enforcement, multi-operator approvals, live revocation propagation and emergency-stop semantics.

- [x] Commit experimental Python MAP Policy Engine and unit tests (in-memory, not production-ready).
- [ ] Verify GitHub Actions pass and implement durable, authenticated policy enforcement and real runtime cancellation.

- [x] Commit experimental SQLite-backed policy engine with transactional authorization and restart/concurrency tests.
- [ ] Confirm v0.2 test results on Windows and CI; then implement trusted identity, server clock and runtime cancellation.

- [x] Commit experimental v0.3 session store and authenticated action gateway with tests.
- [ ] Validate v0.3 locally and in CI; implement trusted enrollment, unified authorization/dispatch and real runtime cancellation.
