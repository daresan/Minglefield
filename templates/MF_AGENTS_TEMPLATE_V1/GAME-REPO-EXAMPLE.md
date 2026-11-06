# Example: adopt MF_AGENTS_TEMPLATE_V1 in a Minglefield Game repository

**Illustrative example only.** No second Minglefield source of truth is
created here. An existing Game repository's AGENTS.md/SOUL.md, Game design,
approved engine, README, roadmap, security and contribution requirements
must be read and retained before applying this example.

## Game-specific mapping

- Canonical entry: project's existing root AGENTS.md **or** SOUL.md.
- Product documentation: existing Game README, project manifest and/or
  design document; MAP compatibility declarations if applicable.
- Roadmap: project-owned game milestones and subgoals.
- CI policy: generic [MDCI Core](MDCI-CORE-v1.1.0.md), adapted
  [Project CI Profile](PROJECT-CI-PROFILE.template.md).
- Acceptance: project-specific
  [Milestone Acceptance](MILESTONE-ACCEPTANCE.template.md).
- Hosts/Effects/Jobs/MAP integration tests apply only if the actual Game
  implements those interfaces. Never invent a global Minglefield authority,
  trusted remote Host or an installer dependency.

## Example initial milestone **only if no approved roadmap exists**

**G0 — Game goals, roadmap and development-CI foundation**

- **G0.1** Existing source/engine/assets/license inventory and playable goal
- **G0.2** Proposed milestone roadmap (playable slice, assets, systems, release)
- **G0.3** Measurable subgoals and positive/negative acceptance checks
- **G0.4** Project CI profile: selected engine, deterministic tests and
  explicit game-build gate
- **G0.5** Maintainer review and approval of roadmap/CI setup

If a roadmap exists, **do not create G0**; resume its last accepted subgoal,
or propose an MDCI adoption subgoal only if that is genuinely missing.

## Example: a subgoal in an already approved playable-game milestone

**G1.02 — Player movement and collision** (illustration)

- T1: deterministic input-to-motion unit tests for this Game engine.
- T2: collision, pause, boundary and regression controls.
- T3: the project's supported platform/engine matrix at integration gate.
- T4: one explicit playable build **only** if the owner needs to accept
  a user-visible movement slice; technical refactors need no package.
- Positive: player moves in expected direction and stops at obstacles.
- Negative: invalid input cannot move player through restricted geometry.
- Regression: unrelated gameplay and existing save compatibility preserved.
- Acceptance: test SHA, CI job results and owner observation; not merely
  a green compile.

## Explicit separation from ComfyUI

- **MDCI CI check / GitHub Actions run**: source lint, game build/tests,
  security, package artifacts and milestone acceptance.
- **ComfyUI workflow**: node graph executed by a configured local/remote
  ComfyUI runtime for generating assets; no GitHub Actions trigger.
- Using ComfyUI to create a texture, video or GLB neither authorizes
  a Game build nor automatically passes an MDCI gate.

## Existing Minglefield boundaries worth preserving

The platform [Repository & Package Architecture v0.1 draft]
(../../docs/REPOSITORY-PACKAGE-ARCHITECTURE-v0.1-DRAFT.md) distinguishes
Game repository manifests from the MAP discovery manifest. The
[Game Workspace & Asset Lifecycle draft]
(../../docs/GAME-WORKSPACE-AND-ASSET-LIFECYCLE-v0.1-DRAFT.md) requires
safe project-owned staging, opt-in execution and separate Game build/run
authorization. These links are **Minglefield template-repository references**:
replace them with actual project references when copying this example.

This example does not alter a Game repository or ship a Game engine.
