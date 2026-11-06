# Project agent entrypoint — MF_AGENTS_TEMPLATE_V1

> Template: adapt to the current repository before adopting as root AGENTS.md
> or SOUL.md. Do not overwrite an existing binding contract.
> This file is agent onboarding guidance, not permission to use tools.

## On every new chat, resumed chat or interrupted session

1. Read this repository's authoritative **AGENTS.md or SOUL.md**, plus any
   linked onboarding rules. When both exist, use the project-approved
   canonical entry and read the second for nonconflicting identity/context.
2. Confirm repository, authorized branch, HEAD SHA, working changes and
   user-approved scope. Read existing README, ROADMAP and milestones, relevant
   architecture, project CI profile, GitHub Actions, acceptance evidence and
   last recorded development state. Read from the **actual branch**, not
   silently from the default branch.
3. Classify each subgoal as proposed, implemented, locally tested,
   CI-verified, owner-accepted or blocked. A commit, an unverified handover,
   or a green unrelated job is **not** milestone acceptance. Reconcile
   contradictions before advancing; do not repeat already accepted tests
   unless a relevant dependency changed.
4. Give a short resumption report: branch/SHA, active milestone and subgoal,
   last verified evidence, current open risks, exact next step. Continue the
   last approved work; do not reinvent the roadmap or switch branches.
5. Apply the project's versioned **MDCI** policy/profile and test selection
   rules. CI here means GitHub Actions development checks; it does not
   mean a ComfyUI node-graph workflow.

## Missing roadmap / missing MDCI adoption

- Search for an existing ROADMAP and equivalent approved milestone plan
  before concluding that none exists.
- **Roadmap exists:** honor its milestones, subgoal numbers, completed work
  and approved priorities. Fill only documented acceptance gaps by proposing
  additions for owner review.
- **No milestone plan exists:** propose an initial **M0 — Project Roadmap &
  Development CI Foundation** with M0.1 project inventory, M0.2 goals and
  roadmap, M0.3 concrete subgoals and acceptance criteria, M0.4 versioned
  project-specific MDCI adoption, M0.5 first review/approval. This is a
  *proposal*, not an automatically authorized new roadmap or product plan.
- **MDCI policy/profile missing while roadmap exists:** propose a small MDCI
  adoption subgoal within the active milestone (or its owner-selected
  predecessor). Do not reset the roadmap or invent a second M0.
- **Both missing:** propose one combined M0, not two separate onboarding
  milestones. Always ask for the owner-approved priority before committing
  previously nonexistent milestones.
- If this entrypoint itself is missing, a newly onboarded agent should first
  propose adoption of a minimal AGENTS.md **or** SOUL.md, preserving any
  existing alternative agent contract.

## Development CI: portable rules

Follow the **MDCI Core v1.1.0** (template source) plus the adopted project's
**CI profile**, not generic hard-coded Tauri/Rust or Game assumptions.

- T1: smallest deterministic relevant test and lint/format on each code edit.
- T2: affected integration, security and platform regressions at risk
  boundaries or feature-slice completion.
- T3: full appropriate conformance/matrix before merge or high-risk gate.
- T4: explicitly requested acceptance build and observable user-facing test
  **only** when a named, build-worthy milestone subgoal is ready.
- Define a positive, negative, regression and (when applicable) recovery
  criterion for each subgoal, plus OS/environment, exact source commit and
  acceptance authority. A purely technical subgoal may close on T1–T3.
- Do not infer approval to generate packages from a commit or CI pass. Never
  weaken security tests merely to save time. Record skipped and unavailable
  checks honestly. No credentials or private data in CI logs.
- Use project-managed versions and fixtures, deterministic seeds, isolated
  external dependencies and pinned tools where justified.

## Authorization and continuity

Existing project policies, contribution rules, access restrictions and
human decisions outrank this template. Do not autonomously push, merge,
switch branches, overwrite owners' work or deploy without authorization.
Never treat AGENTS/SOUL as a secret store or security enforcement layer.

On each accepted subgoal, record the evidence and next approved step in
the project's existing roadmap/handover convention; create no duplicate
state database. Keep the entrypoint short and link detailed policies.
