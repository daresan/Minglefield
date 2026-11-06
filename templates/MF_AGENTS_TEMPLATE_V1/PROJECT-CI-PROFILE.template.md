# Project CI profile — adopt MDCI Core v1.1.0

> **Template only.** Fill from inspected project facts. Do not run these
> placeholders as CI commands. Owner approval precedes any required-check
> or workflow-trigger changes.

## Identity and current state

- Repository: [owner/repo or local-only project]
- Canonical agent entry: [AGENTS.md OR SOUL.md]
- Current branch and HEAD: [verified branch / SHA]
- Canonical roadmap: [real path, or absent -> propose M0]
- Active milestone/subgoal: [ID, last verified state, next approved step]
- Existing handover/acceptance source: [path or none]
- Adopted core: MDCI Core v1.1.0 / MF_AGENTS_TEMPLATE_V1
- Project CI policy version: [project-specific version]
- Previous CI implementation SHA: [this project's actual SHA or not applicable]

## Tooling and controlled environment

| Field | Verified project value |
| --- | --- |
| Languages / engines | [inspect repo] |
| Runtime/compiler versions | [real pinned/versioned sources] |
| Lockfiles and dependency manifests | [paths] |
| Supported OS / architecture | [supported targets, not assumed all three] |
| Test fixtures, deterministic seeds, clock/network controls | [methods] |
| Repository permissions and protected branches | [verified, do not invent] |

## Path-to-gate map

| Affected files/components | T1 focused checks | T2 safety/integration escalation | T3 merge matrix |
| --- | --- | --- | --- |
| [component A and tests] | [exact command, OS] | [affected regression] | [required platforms] |
| [component B and tests] | [exact command, OS] | [affected regression] | [required platforms] |
| [security-sensitive paths] | [exact command, OS] | [mandatory negative tests] | [risk-based platforms] |
| [documentation only] | [links/schema/security docs check] | [only if compatibility changed] | [ruleset-aware required status] |

Do not skip a required shared-interface regression because an edit fell
outside one narrow path filter. Verify the actual GitHub Actions trigger
semantics against the repository's directory layout.

## T4 artifact / milestone approval

- What is being packaged: [the **project's** real deliverable]
- Explicit GitHub Actions trigger: [owner-approved dispatch or marker]
- Build command and lockfile: [project-specific; NOT Minglefield installer]
- Artifact OS/platforms: [only product-supported targets]
- Provenance/digest check: [project-specific verified method]
- Acceptance-contract location: [path; one per subgoal]
- Approval and retry policy: [who approves, when a repair build is allowed]
- Never package on ordinary push/PR: [actual CI evidence]
- Recovery of previous CI policy: [SHA, reviewed restore steps]

## Open gaps and adoption decisions

- [ ] Roadmap and milestone acceptance status verified against git and CI
- [ ] Required check names and path filters reviewed
- [ ] Fast development check works without unnecessary artifact packaging
- [ ] Security and OS matrix covers risk boundaries
- [ ] Explicit subgoal build gate tested (if applicable)
- [ ] User/maintainer has accepted the adoption

Only mark these complete when observed. A reference template is not an
automatically installed GitHub workflow.
