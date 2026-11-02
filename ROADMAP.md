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

## Cross-cutting design — developer-owned game logic and specialized models (planned)
- [ ] Ensure MAP-compatible games can integrate developer-chosen deterministic algorithms and/or small task-specialized custom models ("mini-models") according to task complexity; neither approach is mandatory.
- [ ] Keep design, implementation, training/fine-tuning, evaluation, deployment and integration of such algorithms/models the responsibility and choice of the individual game developer or Developer Team. Minglefield is **not** required to provide a central model-creation or training service.
- [ ] Publish engine-agnostic interface specifications, recommended practices, security and performance guidance, and practical tutorials for building and integrating custom mini-models or deterministic algorithms.
- [ ] Provide optional example implementations and reusable starter templates for game prototypes, including deterministic-only, mini-model-assisted and hybrid patterns.
- [ ] Document versioning, reproducibility, model/data provenance and licensing considerations where relevant, while allowing independently developed runtimes and inference backends.
- [ ] Preserve game/team isolation and MAP authorization boundaries: integrating game logic or a model never implicitly grants agent identity, delegation, private memory access or external-effect authority.

## Near-term vertical slice — local ComfyUI execution and versioned projects (approved direction)
- [x] Document Git-backed repository/package architecture and boundaries in [Repository & Package Architecture v0.1 draft](docs/REPOSITORY-PACKAGE-ARCHITECTURE-v0.1-DRAFT.md).
- [x] Document the safe, incremental local ComfyUI executor plan in [Local ComfyUI Executor v0.1 draft](docs/COMFYUI-LOCAL-EXECUTOR-v0.1-DRAFT.md).
- [ ] Read-only local workflow discovery and automatic input/parameter form generation for supported ComfyUI API-format JSON workflows.
- [ ] Explicitly opted-in, human-approved, loopback-only ComfyUI execution with authenticated job submission, status, audit and bounded outputs; do not reuse simulation-only effect execution as a bypass.
- [ ] Local Git project import/create, manifest and dependency validation, versioned asset output and reviewable changes.
- [ ] First reproducible human + agent game-asset creation workflow; no remote hosting or autonomous external effects before independent security gates.

## Near-term design — Game tab and managed local assets (approved direction; not shipped)
- [x] Record requirements and staged implementation gates in [Game Workspace and Asset Lifecycle v0.1 draft](docs/GAME-WORKSPACE-AND-ASSET-LIFECYCLE-v0.1-DRAFT.md).
- [ ] Game tab: create/import/select Git-backed games; edit per-project staging and output paths.
- [ ] Persistent local asset staging via native file dialog; store asset IDs and job bindings without premature ComfyUI transfer.
- [ ] Transfer staged inputs to ComfyUI **only when the job starts**, using generic file-input capabilities rather than node-specific UI functions.
- [ ] Game build, test, launch and logs; browser preview when supported, otherwise controlled local application launch.
- [ ] Re-run full conformance suite and first-workflow regression tests before expanding execution behavior.

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
