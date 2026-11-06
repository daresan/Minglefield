# MDCI Core v1.1.0 — project-independent GitHub development CI

**Contract:** reusable engineering policy, not executable CI tooling.
**Template distribution:** MF_AGENTS_TEMPLATE_V1.
**Distinct from:** the deployed Minglefield installer-specific MDCI v1.0.0,
ComfyUI node-graph workflows, Game/Jobs runtime orchestration, MAP versions
and application release versions.

## Adopt from existing project state

Read the authorized root AGENTS.md or SOUL.md, project roadmap, accepted
milestones, last verified evidence, technologies, test commands, CI workflows,
branch restrictions and approvals. **Preserve and extend**, do not replace
approved governance or force a new roadmap on an established project.
A template is not authorization to install, publish, merge or execute code.

If no roadmap is found, propose initial M0 Project Roadmap & Development CI
Foundation (inventory -> milestones -> subgoals/acceptance -> project CI
adoption -> owner approval). If a roadmap exists but MDCI is absent, propose
one MDCI adoption subgoal inside the existing roadmap. Neither creates files
or changes priority without owner approval.

## Required project profile

An adopted profile provides the true repo root, versioned MDCI policy,
tools and lockfiles, component/path ownership, deterministic T1 test
commands, cross-component/T2 regression mapping, T3 platform/release
matrix, T4 artifact build and acceptance commands, high-risk paths, approved
CI triggers and required status checks, and old-configuration rollback SHA.

Use the project profile template, but do not hardcode Minglefield/Tauri,
Python/SQLCipher, game engines or default runner OS into the general policy.
Prefer small GitHub Actions files with path filters, stable job names and
least-privilege read-only permissions. Untrusted pull requests cannot use
secrets or push commits. Never turn user-provided game scripts into trusted
arbitrary CI commands merely by referencing them in a manifest.

## Test selection (T1–T4)

| Gate | Trigger | Minimum evidence | Portable/release artifacts |
| --- | --- | --- | --- |
| **T1 — focused** | Relevant code change | Changed component's deterministic tests, format and lint | No |
| **T2 — regression/security** | Shared interface, auth, filesystem, data, game isolation or feature slice | Affected dependencies, negative controls, platform cases where needed | No |
| **T3 — integration/merge** | Milestone integration, PR merge, high-risk change, release candidate | Full appropriate suites and actual relevant OS/engine/runtime matrix | No (unless T4 separately approved) |
| **T4 — acceptance** | Named user-visible subgoal, after its prerequisites | Provenanced exact SHA, user-observable positive/negative/recovery tests and owner approval | One explicit build if required |

Critical data integrity and authorization changes get T2/T3 **earlier**
when risks warrant; "smallest" never means missing security. Static docs
and administrative edits should not compile application binaries unless
they change a protected compatibility contract. A CI unit-test binary
is not a release/portable package.

Technical-only subgoals can be accepted on T1–T3 without a package.
One acceptance build per independently user-visible subgoal is a default
maximum, not a promise to generate packages for every line item. Necessary
repair/retest builds require a recorded reason. Package workflows should
be explicit dispatch or reviewed milestone marker; avoid automatic
packaging on every push/PR, while keeping required check evidence intact.

## Deterministic evidence and GitHub Actions discipline

- Prefer pinned compiler/interpreter/dependency/Action versions or a reviewed
  update cadence, locked installs, stable fixtures, seeded randomness and
  isolated clocks/network. Record nondeterministic external integration tests
  separately; no fake "deterministic" claims for live cloud services.
- Record Git SHA, OS, test command, success/failure/skipped, artifact digests
  and operator acceptance; an empty API response or missing required job
  cannot be interpreted as green.
- Keep T1 quick. Use relevant OS/risk matrices, caches and concurrency
  cancellation of superseded **push** runs only. Do not cancel a manually
  approved acceptance build or silently discard required PR evidence.
- GitHub branch protection may require checks that appear even for docs-only
  commits; plan aggregate required status carefully, without reporting a
  skipped test as passed. Inspect configured rules before changing names.
- Minimize workflow privileges; do not give jobs write tokens or secrets
  unless independently approved and properly isolated.

## Milestone and subgoal contract

For each proposed or existing subgoal, capture:
ID/title, business or gameplay outcome, prerequisites/dependencies,
positive observable acceptance, negative and regression controls, failure
or recovery test when relevant, targeted T1–T3 commands and environments,
T4 build need (yes/no/reuse), source commit and independent acceptance.

Statuses are distinct: proposed; approved; implemented; focused-tested;
CI-tested; user-accepted; blocked; deferred. Never promote from one
category to another without evidence. The roadmap stays the canonical
milestone index; store detailed cases in an existing acceptance document,
not a second competing roadmap.

## Versioning and rollback

Version **MDCI Core** independently from the project CI profile, release,
MAP/game protocol and ComfyUI node-graph definitions. Use SemVer:
major = breaking contract, minor = new compatible behavior or adoption
capability, patch = corrections. Record the adopted template version and
the previous workflow SHA in the profile. Restore older CI through an
owner-reviewed commit in the authorized branch; never auto force-push or
keep parallel executable versions that duplicate triggers.

New projects do **not** inherit the old Minglefield installer SHA as their
own rollback reference. Git history of each adopting project is authoritative.

## Agent reinitialization

On every resumed/new session read the root entrypoint and existing
roadmap/CI/acceptance evidence. Report current branch/SHA, last accepted
subgoal, pending CI, next owner-approved action, and risks; continue exactly
there. If evidence is missing, mark it unknown and seek targeted
verification instead of fabricating state. No duplicate test runs solely
because the chat was interrupted.
