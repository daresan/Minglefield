# MAP v0.4 — B2.3d security review and decision gate

Status: **code-based preliminary security review; not a production certification**. Reviewed branch: `wip/map-v04-phase-b1` at `ca8a4e1` (prior to this report). No changes to `main`. Scope: B1 submission, B2 claim/prestart, B2.3 dispatch, fake coordinator/outcome recorder, read-only inspector, schema v4, and existing contracts.

## Decision

- **GO**: continue *simulation-only* development, negative/security tests, documentation and independent adapter design.
- **NO-GO**: enable real external effects, expose dispatch/recorder/inspector as public APIs, promise exactly-once effects, strict immediate revocation, verified outcome provenance, production-grade accounting or audit chronology.
- **Evidence**: maintainer's local run at `ca8a4e1`: 4/4 focused inspector tests; 162 conformance tests OK with **3 inherited expected failures**; MAP v0.1 validator PASS; `git diff --check` clean. This review did not itself execute local tests or a penetration test.

## Findings and required controls

| ID | Severity for real effects | Evidence / risk | Required mitigation |
| --- | --- | --- | --- |
| SEC-01 | **Critical / blocker** | `DispatchGate.commit_intent` reauthorizes under `BEGIN IMMEDIATE`, but after commit there is no downstream revocation/fencing. A subsequent grant/session revocation cannot stop an in-flight remote call. | Define per-adapter fencing/authorization at effect boundary; deny high-risk effects without it. Test revocation after intent commit. |
| SEC-02 | **High / blocker** | `FakeOutcomeRecorder.record` accepts a caller-created `FakeOutcome` and a persisted effect key. It cannot prove invocation, adapter identity, or external evidence provenance. Correct for trusted simulation only. | Define trusted executor identity, signed/verified or queryable adapter evidence, scoped credentials and manual reconciliation authority before real integration. |
| SEC-03 | **High / blocker** | `dispatch_committed` may mean crash before or after invocation; the fake coordinator deliberately does not replay. No persisted invocation attempt/acknowledgement evidence can distinguish the gap. | Keep unresolved intent; implement explicit read-only reconciliation design, evidence model and operator review; prohibit automatic retry. |
| SEC-04 | **High / blocker** | The internal `DispatchGate`, `FakeOutcomeRecorder` and `DispatchInspector` do not independently authenticate an operator/coordinator. Their safety assumes a trusted in-process caller and protected SQLite access. | Define authenticated coordinator/operator roles, least-privilege access, isolation of DB/claim tokens, and authorization for inspection/reconciliation. Do not expose these classes directly as endpoints. |
| SEC-05 | **Medium / audit limitation** | `action_audit` uses timestamps and random event IDs; `DispatchInspector` presents events in lifecycle order, **not independently evidenced commit order**. Audit rows lack distinct trusted coordinator identity and a durable sequence. | Add append-only sequencing/actor attribution with explicit migration and rollback tests; distinguish display ordering from historical proof. |
| SEC-06 | **High / release blocker** | Three inherited expected failures remain in the legacy authorization test suite. Their precise exploitability has **not** been determined by this review. | Triage each test and root cause; close or explicitly scope out affected legacy paths before any production authorization claim. |
| SEC-07 | **Medium / hardening** | `ClaimWorker._check` checks important policy fields but does not validate a complete strict schema for all persisted grant/agent/request structures. Certain malformed-but-type-compatible values could produce misleading decisions. | Add strict typed structural validation and adversarial mutation tests; fail closed on malformed policy or request data. |
| SEC-08 | **Medium / operational** | The simulator uses an immutable configured adapter map, but does not persist independent coordinator identity; budget reservations remain spent even for verified no-effect failure and ambiguous outcomes. | Define coordinator attribution and a separate auditable settlement/refund protocol; never auto-refund unknown outcomes. |
| SEC-09 | **Medium / trust boundary** | `FakeSimulationCoordinator` permits caller-specified simulation scenario/crash point and reads the committed effect key through an internal DB transaction. This is acceptable in a trusted test harness, not as a user-facing execution interface. | Keep fake controls test-only; forbid untrusted scenario selection and effect-key access in any future production coordinator. |

## Verified code-level properties (not proof of production safety)

- The B1 submission reserves budget and records a queued job within a SQLite writer transaction.
- Claim, prestart and dispatch check the original session and current grant/policy; dispatch validates worker claim digest and canonical request fingerprint.
- A successful `ready -> dispatch_committed` transition persists adapter ID/version and effect idempotency key before the fake invocation.
- A second coordinator cannot win the same state transition; the fake coordinator has no restart replay.
- Fake terminal transitions and audit inserts share one SQLite transaction; the read-only inspector does not mutate jobs.
- Tests cover concurrent dispatch, revoked/expired sessions and grants, bad claims, injected audit failures, crash points and simulated timeout. Coverage does **not** establish behavior of a real external system.

## SEC-07 follow-up — current hardening branch (2026-11-01)

Status: **mitigated, not closed**. This is a follow-up to the original review at `ca8a4e1`, not a replacement of its historical evidence. Maintainer locally validated `0571d3a`: 23/23 worker tests, 186/186 conformance tests, MAP v0.1 validator PASS, `git diff --check` and `git status --short` clean. These results do not validate later documentation commits.

The shared `ClaimWorker._check` path used by claim, prestart and dispatch now rejects non-object requests; invalid request version/parameters; missing or conflicting user/agent/delegation bindings; invalid grant/agent identity, status, revision, scope list and budget-limit types; invalid grant time types/order; revoked/suspended authorities; and invalid original sessions. Tests cover targeted persisted-record mutations, including delegation changes after claim and after ready.

**Residual work before closure:** compare all security-relevant persisted grant, agent and request fields against their normative schemas; validate typed identity/target/action/scope fields and policy revisions as appropriate; verify nested request parameters against action-specific contracts if defined; establish fail-closed behavior at each transition for remaining malformed-but-type-compatible cases. A passing suite is not evidence of complete schema coverage. SEC-01 through SEC-06 and SEC-08/09 retain their separate status; no actual external effects authorized.

## SEC-07 schema-parity assessment — 2026-11-01

Status: **mitigated, still open pending targeted follow-up**. Maintainer validated commit `862b0a4`: 18/18 dispatch tests, 199/199 conformance tests, MAP v0.1 validator PASS, clean diff/status. This is a local regression baseline, not proof of complete structural or production security.

| Field / boundary | Schema comparison | B2 handling / decision |
| --- | --- | --- |
| Agent identity, operators, roles, state, revision and optional runtime/policy | Matches required/optional property sets, ID patterns, role enumeration, uniqueness and basic types | B2 additionally caps integer values at `MAX_INT` and rejects booleans as integers: intentional operational restriction. |
| Grant identities, optional target/approval, scopes, status and budget | Matches property sets, ID/scope patterns, unique nonempty scopes and status values | B2 caps budgets at `MAX_INT`; intentional operational restriction. |
| Grant `issued_at` / `expires_at` | Schema declares `format: date-time` | Structural validator currently checks strings only; worker parses timestamps via `_time` and checks interval against server time. Need explicit date-time parity tests and consistent rejection of malformed formats. |
| Agent `policy.allowed_scopes` | Schema permits an empty array, but each present item must be a nonempty string and entries unique | Structural validator accepts empty arrays; transactional worker requires list membership for the action, so empty means no authorization. |
| Agent `policy` absent | Schema allows omission | Structural validator accepts omission; worker requires an explicit policy/allowed-scopes list to authorize. This is an intentional fail-closed execution restriction, not a schema mismatch. |
| Grant `target_id` absent | Schema permits omission | Worker requires exact target binding to the request; omission denies execution. Intentional fail-closed restriction. |
| Persisted B2 request | Internal record includes version, user/agent/delegation/target, action type, scope, parameters | **Not identical to** `action-submit.schema.json`, which defines an envelope with a payload. Do not claim wire-schema parity for this internal format. Define/document a dedicated persisted-record contract if promoted beyond B2. |
| Request action/scope strings | Wire `action-submit` constrains `payload.action_type` to a dotted pattern; persisted request has no dedicated normative schema | Current validator accepts any nonempty action/scope strings (action capped at 128); worker requires trusted action rule and exact scope match. Assess whether a stricter internal grammar is appropriate without changing wire semantics. |
| Nested request `parameters` | Wire payload permits arbitrary JSON object; action-specific contract is not defined here | Validator checks object type only. Worker binds to a trusted action rule but does not perform action-specific parameter validation; keep this as a separate integration contract requirement. |

The shared `ClaimWorker._check` is used transactionally at claim, prestart and dispatch. Post-claim/post-ready mutation tests cover malformed agent, grant and request records and deny before ready/dispatch intent. These tests are **not** exhaustive fuzzing or proof of schema equivalence.

**Closure prerequisites:** document and test date-time behavior; explicitly distinguish structural validity from execution authorization; decide on a persisted-request grammar and action-specific parameter contracts; rerun full conformance and obtain maintainer review. No real effects authorized.

## SEC-07 persisted-request contract and parameter boundary — 2026-11-01

The persisted B2 request is an **internal, server-generated authorization snapshot**, not the MAP `action.submit` wire envelope. `ActionService.submit` derives `user_id` from the authenticated session, `scope` from the trusted `ActionRule`, and `version=1` from the server. It copies caller-supplied `parameters` only after validating JSON compatibility, canonicalizing them, and enforcing the 65,536-character encoded limit. The snapshot is persisted with a SHA-256 fingerprint; dispatch rechecks canonical content and fingerprint.

`valid_request` checks the exact internal property set, version, ID shapes, nonempty action/scope strings, action length and object-typed parameters. It **does not** decide which actions exist, whether a scope is granted, whether a target is authorized or whether parameters satisfy the semantics of a particular game action. The shared transactional `ClaimWorker._check` rechecks identity bindings, trusted action rule/scope, grant and agent allowlists, and target. Dispatch additionally checks request fingerprint and adapter mapping. Mutation regression tests now exercise action/scope/identity/target changes at claim, as well as structural corruptions at prestart and dispatch.

**Future adapter contract requirement:** each real adapter or game integration must specify its own versioned parameter contract (schema or equivalent validation), including types, ranges, size/complexity bounds, semantic constraints and canonicalization expectations. The trusted integration boundary must validate parameters before any effect; arbitrary JSON object shape is **not** sufficient evidence of action-specific safety. No universal game-parameter schema is imposed by MAP or this B2 simulation.

**Remaining review:** assess strict grammar for the internal action/scope fields separately from the wire format, and determine whether additional policy revision/fingerprint consistency checks are needed at each transition. The tests added after the 200/200 baseline require local verification. SEC-07 remains open until that review and maintainer acceptance. This section does not authorize external effects.

## SEC-07 revision fencing and internal grammar decision — 2026-11-01

**Maintainer-verified baseline:** after commits `2dc1080` and `1171f28`, the maintainer reported **210/210 conformance tests OK**, MAP v0.1 validator PASS, and clean `git diff --check` / `git status --short`. The two new tests exercise an agent descriptor revision change after claim and after ready, respectively, while leaving allowed scopes unchanged. Both deny with `policy_revision_changed`; the dispatch case additionally asserts no effect key, adapter identity or dispatch timestamp. Earlier claim-stage revision mutation coverage is also included.

**Revision decision:** B2 jobs are bound to the agent descriptor revision stored at submission. The shared transactional authorization check compares that stored `policy_revision` against the current valid agent descriptor revision at claim, prestart and dispatch. A mismatch fails closed, even when scopes are unchanged; resubmission under the new revision is required. This is **pre-intent fencing only** and does not solve SEC-01 revocation after a committed dispatch intent. It also does not claim to detect unauthorized changes to policy content that preserve the revision; trusted policy writers must maintain revision semantics.

**Internal action/scope grammar decision:** keep the internal persisted request's action and scope fields structurally constrained as documented (nonempty strings, action length bound) rather than automatically imposing the MAP wire envelope's action-name grammar on the B2 snapshot. Submission derives scope from a trusted configured `ActionRule`; each transactional transition requires an existing trusted action and an exact rule/snapshot scope match, followed by current grant and agent allowlist checks. This is an **intentional internal contract distinction**, not a relaxation of normative wire validation. A future public MAP ingress must validate its wire schema separately. Trusted action configuration should use stable, documented names; tightening its grammar would be a separate compatibility-reviewed change.

**SEC-07 disposition:** the identified B2 persisted-record structural validation and revision-fencing work is **mitigated and maintainer-validated for the simulation-only scope**. The remaining action-specific parameter contract is a **mandatory future real-adapter boundary requirement**, not a generic MAP parameter schema. This review does not certify all malformed inputs, hostile database writes, or external effect safety. SEC-01 through SEC-06 and SEC-08/09 remain independent findings. No production or real-effect authorization follows from closing the B2-focused SEC-07 hardening work.

## Release gates for future real-adapter design

1. Resolve SEC-01 through SEC-04 and SEC-06, including a concrete threat model and independent adversarial tests.
2. Specify an adapter-specific idempotency contract: stable key + immutable payload/target fingerprint, verified effect status, timeout semantics and fencing.
3. Define and test evidence-backed operator reconciliation; never infer success from intent or automatically replay uncertain effects.
4. Define access control for dispatch, inspection and outcome recording, plus credential handling and audit attribution.
5. Review SEC-05, SEC-07, SEC-08 and SEC-09 with explicit risk acceptance or implementation plans.
6. Run complete local and CI suites and obtain separate maintainer approval for **each** real-effect adapter. This review is **not** that approval.

## Recommended next small steps

- **B2.3d-1**: confirm this finding register and decide which legacy expected failures block which release surfaces.
- **B2.3d-2**: add negative tests for malformed policy/request data and dispatch-state invariants without enabling effects.
- **B2.3d-3**: write a separate real-adapter interface RFC, including revocation fencing and evidence-based reconciliation; implementation remains prohibited pending explicit approval.

No external effect, background worker, automatic replay, migration or public API is authorized by this document.
