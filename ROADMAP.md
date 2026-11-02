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

## Local ComfyUI GLB P0 — accepted functional slice
- [x] User-reported successful SkinTokens workflow execution via alpha UI; 431 conformance tests passed. See [P0 acceptance and limitations](docs/COMFYUI-GLB-P0-ACCEPTANCE.md).
- [ ] Independently capture completed ComfyUI history and output provenance in P1.

## Near-term design — Game tab and managed local assets (approved direction; not shipped)
- [x] Record requirements and staged implementation gates in [Game Workspace and Asset Lifecycle v0.1 draft](docs/GAME-WORKSPACE-AND-ASSET-LIFECYCLE-v0.1-DRAFT.md).
- [ ] Game tab: create/import/select Git-backed games; edit per-project staging and output paths.
- [ ] Persistent local asset staging via native file dialog; store asset IDs and job bindings without premature ComfyUI transfer.
- [ ] Transfer staged inputs to ComfyUI **only when the job starts**, using generic file-input capabilities rather than node-specific UI functions.
- [ ] Game build, test, launch and logs; browser preview when supported, otherwise controlled local application launch.
- [x] **P0 release gate before Game tab (P1):** 431 conformance tests passed; Load3D GLB binding confirmed; user reported successful SkinTokens execution and approved continuation. See [P0 acceptance](docs/COMFYUI-GLB-P0-ACCEPTANCE.md).

## P1.4f.2b — Federated integration registry (implementation in progress)

- [x] Add a public, initially empty curated registry, JSON Schema and offline cross-entry validation. See [Integration Registry v0.1 draft](docs/INTEGRATION-REGISTRY-v0.1-DRAFT.md).
- [x] Reserve `minglefield.*` for official entries and `community.<publisher>.*` for reviewed community entries; reject duplicates and malformed entries.
- [ ] Verify tests on the Windows development host and add CI coverage.
- [ ] Define publisher ownership proof, release identity/artifact integrity, and source-transfer review before admitting actual entries.
- [ ] Add explicit, user-authorized external-source support separately; external developers need no approval to publish independently.
- [ ] Connect read-only local installed-integration discovery to curated definitions without changing legacy manifests.

## P1.4f.2a — Integration metadata contract

- [x] Draft identity, installed-version provenance, trusted release-source mapping, multiple-integration semantics and legacy unknown states in [Game Integration Metadata v0.1 draft](docs/GAME-INTEGRATION-METADATA-v0.1-DRAFT.md).
- [ ] Implement read-only inspection with owner isolation and negative conformance tests, without assuming the final package/lockfile format.
- [ ] Decide final persistence and source-of-truth boundary before writing integration metadata to project manifests or lockfiles.

## P1.4f schema/convention audit (2026-11-02)

Existing conventions checked on the active feature branch:
1. `schemas/map/v0.1/game-manifest.schema.json` is a **MAP discovery/negotiation manifest** with `manifest_version: "0.1"`, `game_id`, `map_versions`, capabilities and endpoints. It forbids unknown top-level properties and provides an `extensions` object. It is **not** the local workspace's `.minglefield/project.json`.
2. `docs/map/CAPABILITY-NEGOTIATION-v0.1-DRAFT.md` explicitly separates descriptive discovery metadata from authentication/authorization and uses namespaced capability strings. No package-installation or integration-release identity is specified.
3. `docs/REPOSITORY-PACKAGE-ARCHITECTURE-v0.1-DRAFT.md` proposes `minglefield.yaml` and `minglefield.lock` for versioned packages, but explicitly says package IDs, version ranges and resolver semantics **remain to be standardized**. These files are not implemented as an authoritative package manager.
4. The **implemented** alpha workspace uses `.minglefield/project.json` (`schema_version: 1`, `project_id`), not the proposed `minglefield.yaml`. Its compatibility inspector currently tolerates extra fields but does not validate installed integration records.
5. `server/game_release_metadata.py` is a GitHub-specific read-only metadata adapter; GitHub Releases alone do not prove integration identity.

Design consequence: keep MAP discovery, local workspace configuration and proposed portable package/lockfile formats **separate**. Do not silently turn `extensions`, `map_versions`, `schema_version`, Git tags, or an arbitrary repository URL into installed integration identity. Before introducing any persisted integration list, specify identity, provenance, version, provider-neutral source mapping, duplicate-ID handling and legacy-manifest migration as a separately reviewed contract. Initial implementation should be read-only and must preserve both existing game repositories and v1 manifests.

## P1.4f architecture decision — multiple independent integrations

Code audit (2026-11-02):
- Existing owner-scoped `alpha_game_projects` registry identifies games and repository roots; do not duplicate it.
- Existing `.minglefield/project.json` schema v1 currently records only `schema_version` and `project_id`. Compatibility inspection accepts additional keys but does **not** validate an integrations collection. No installed integration versions can be inferred from schema v1.
- Existing `server/game_release_metadata.py` reads GitHub Releases metadata. It does **not** establish whether any GitHub release belongs to a Minglefield integration.
- Existing update-status API accepts an optional `release_repository` query parameter; the Game tab no longer exposes that field. Do not treat arbitrary client-provided repository names as trusted integration sources.

Agreed design:
- A game MAY have **zero, one, or multiple** independently versioned Minglefield integrations.
- An integration has a stable ID, a separately tracked installed version, and an **official, centrally resolved release source**; these are independent of the game project's ID, its own Git remote, the Minglefield platform version, and manifest `schema_version`.
- Before defining a manifest extension, inspect existing MAP schemas, package/adapter conventions and migration rules; reuse an existing identifier/metadata convention if one exists.
- The authoritative mapping `integration_id -> release source` must be maintained by Minglefield's trusted integration definitions, not a free-text Game-tab field or an arbitrary game manifest URL. Optional source selection is shown only when multiple valid registered choices exist.
- Distinguish a game release, a platform release and an integration release. GitHub Releases is a transport for published metadata, **not** evidence of integration identity by itself.
- Existing v1 manifests are legacy/unversioned with respect to integrations; report `unknown` rather than claiming an update exists. Never silently rewrite them.
- First implementation stage: read-only, owner-scoped discovery of installed integrations and source mapping, including clear missing/unknown states. Only then implement SemVer comparison using a standard dependency and show release notes. Mutations require a separate explicit preview and confirmation stage.
- Preserve existing repositories, Git histories, and local files throughout read-only inspection.

## P1.4f — Game integration update management (in progress)

- [x] P1.4f.1: Read-only project integration status; report unknown update availability when no release source is configured (22 focused tests passed on Windows).
- [ ] P1.4f.2: Read-only release discovery and version comparison, based on **GitHub Releases and Git tags**, not a proprietary release catalog. Use the existing release `tag_name`, `body` (release notes), `html_url`, and published timestamp; link commits via GitHub's existing comparison URLs. Treat untrusted release text as display data only.
- [ ] Define the first published **game integration** version independently from the Minglefield platform version and `.minglefield/project.json` schema version. Do not infer an installed integration version from `schema_version: 1`; currently it is unknown.
- [ ] Use a standard SemVer implementation or an existing project dependency, rather than implementing a custom version parser. Do not guess release tags, repository origins, or available updates.
- [ ] P1.4f.3: Preview release notes, changed files, compatibility requirements and migration steps before modifying a game repository.
- [ ] P1.4f.4: Explicit user-approved installation with conflict detection, rollback/recovery and audit trail; preserve independent game Git remotes, branches and history.
- [ ] For offline or inaccessible release sources, distinguish `unknown` from `up_to_date`. A missing or invalid release is not proof that no update exists.

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
