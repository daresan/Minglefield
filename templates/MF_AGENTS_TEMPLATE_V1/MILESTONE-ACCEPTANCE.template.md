# Milestone / subgoal acceptance contract (template)

> Adopt under the project's existing ROADMAP numbering. If there is no
> approved roadmap, this is a **proposal**, not evidence of achievement.
> No product, Game engine, OS or package format is assumed.

## Scope and status

- Project / repository:
- Milestone ID/title:
- Subgoal ID/title:
- Outcome a real user/developer can observe:
- Prerequisites / authorizations:
- Current status: proposed / approved / implemented / T1 passed /
  T2 passed / T3 passed / T4 accepted / blocked / deferred
- Owner / acceptance authority:

## Minimal positive and negative tests

| Type | Stimulus and environment | Expected observable result | Evidence (SHA/job/run) |
| --- | --- | --- | --- |
| Positive | [valid input] | [specific postcondition] | [pending] |
| Negative | [wrong identity, tampered input, unavailable dependency, etc.] | [denied / no unsafe change] | [pending] |
| Regression | [previously accepted behavior] | [preserved] | [pending] |
| Recovery, if relevant | [interrupt/retry/conflict] | [safe restart / rollback] | [pending] |

## Deterministic CI gates

- T1 paths, command, OS/tool versions:
- T2 shared integrations/security tests and negative controls:
- T3 platform or environment matrix:
- Expected time/runner budget (estimate, not evidence):
- Required statuses and fallback if no run was triggered:
- Externally nondeterministic tests, separately labeled:

## Explicit build gate

- Portable/release package needed for this subgoal? yes / no / combine
- Reason if yes (actual user-visible or integration acceptance):
- Trigger (manual dispatch or reviewed marker):
- Exact build commit and artifact digests:
- Manual acceptance steps, OS and actual outcome:
- Repair/rerun reason if more than one build:
- Existing data/branches/users/permissions preserved:

## Closure and continuity

- Test results and run URLs:
- Limitations and intentionally deferred features:
- Owner's explicit acceptance / rejection:
- Canonical ROADMAP status updated? (after approval)
- Last confirmed branch/SHA and exact next approved subgoal:

Do not store raw secrets, private user data, access tokens or untrusted
third-party release instructions here. Do not mark unexecuted tests green.
