# MAP v0.4 — B2.3 executor boundary contract (design only)

Status: **proposal for review; NOT implemented, authorized for execution, or production-certified**.
Branch: `wip/map-v04-phase-b1`. Builds on locally validated B2.2 schema v3 and its inert `ready` state. No change to MAP v0.1 wire schemas, `main`, or external integrations.

## Scope and non-goals

Define a trusted internal boundary between a durable authorization decision and an external side effect. B2.3 must not confuse `ready` with permission to execute indefinitely. This document does **not** authorize a real executor, remote calls, retries, job cancellation, refunds, or public API endpoints.

A SQLite transaction cannot atomically commit with an arbitrary external system. Consequently **exactly-once external effects cannot be guaranteed by this service alone**. A downstream idempotency contract may make repeated deliveries safe, but only for integrations that explicitly honor it.

## Trust boundaries

1. **Submitting principal**: supplies an authenticated request to B1; cannot select worker, executor, claim token, policy decision or effect idempotency key.
2. **Claim worker**: trusted internal identity and original opaque claim token; B2.1 assigns ownership. Possession of the token alone does not grant execution rights.
3. **Pre-start gate**: B2.2 rechecks the original session and current policy; `ready` records a historical authorization decision, not a lease or capability.
4. **Execution coordinator (future)**: trusted, authenticated internal component; must bind job ID, original claim, worker identity, immutable action request and approved executor configuration. Never accept caller-supplied principal or target overrides.
5. **Effect adapter (future)**: allowlisted per action type and target; receives minimum necessary data and a stable, scoped effect idempotency key. It must not receive raw session or claim tokens.
6. **External target**: outside the SQLite transaction and potentially unreliable, duplicated, delayed, or non-idempotent. Treat responses as untrusted evidence until validated.

## Proposed state and audit model — not implemented

```text
queued -> claimed -> ready
                    |   \
                    |    -> denied (fresh policy fails before dispatch)
                    -> dispatch_committed -> succeeded | failed | outcome_unknown
```

**Naming decision for review:** prefer `dispatch_committed` to `running` at the durable boundary. It means a single dispatch intent was recorded; it does **not** prove that an external effect began. An adapter-specific `running` observation could be separate later. `failed` must mean a verified terminal failure with known effect semantics; ambiguous timeout, crash, lost acknowledgement, or uncertain remote completion becomes `outcome_unknown`, not `failed`.

Suggested audit events: `job.dispatch_committed`, `job.succeeded`, `job.failed`, `job.outcome_unknown`, `job.denied`. Each event must be durable, uniquely identified and attributable to a trusted internal actor; sensitive tokens and credentials must never enter logs. Any schema v4 change requires an **explicit**, transactional, rollback-tested migration that preserves v3 history and reservations.

## Proposed execution handshake

1. **Prepare (no effects):** identify a `ready` job, its exact original claim owner and token, immutable request fingerprint, action rule and configured adapter. Reject missing or malformed metadata. No dynamic adapter chosen from untrusted request fields.
2. **Reauthorize:** under `BEGIN IMMEDIATE`, verify the claim digest in constant time, job state and ownership, original submitting session, principal, agent, delegation, scope, target, grant validity and current trusted action rule. Policy revocation committed before this transaction must prevent dispatch. Reuse B2.2's fail-closed policy, with explicit tests against rule/configuration drift.
3. **Commit one dispatch intent:** atomically persist a unique per-job `effect_idempotency_key`, adapter identity/version, request fingerprint, trusted worker/coordinator identity, dispatch timestamp and audit event. Make a conditional one-way state transition from `ready` to `dispatch_committed`. **Commit before any external call.** Never dispatch from an uncommitted transaction.
4. **Dispatch once:** only the trusted coordinator that successfully committed the intent may invoke the allowlisted adapter. Pass the persisted idempotency key unchanged. A duplicate coordinator, restart or repeated API call must not invoke the adapter again automatically.
5. **Record outcome:** validate the adapter's response and persist the terminal event atomically. A verified successful effect becomes `succeeded`; a verified no-effect terminal rejection may become `failed` (precise classification to be defined per adapter). Any uncertainty becomes `outcome_unknown`.
6. **Reconcile manually:** if the process crashes between commit and dispatch, or between effect and acknowledgement, the database cannot distinguish those cases. Do not automatically replay. An operator may use downstream read-only status/query APIs keyed by the stable idempotency key to establish an outcome; any new attempt requires a separately reviewed reconciliation protocol.

### Critical limitation: revocation race

Reauthorization before `dispatch_committed` guarantees that previously committed revocations block dispatch. It **cannot** prevent a revocation occurring after the database commit but before the remote side effect. A strict emergency-stop guarantee requires adapter-side authorization/fencing at the actual effect boundary, or an equivalent trusted serialization/lease mechanism. Until such a mechanism exists, do not advertise immediate revocation of in-flight external effects. For high-risk or irreversible actions, **fail closed and do not enable the adapter**.

## Idempotency, crash and budget invariants

- The key is generated server-side, persisted once, unique within a defined namespace (environment + job + adapter), and never reused for a different payload or target. Downstream acceptance of the same key must bind to the same fingerprint.
- A stable key alone does **not** make a non-idempotent adapter safe. No automatic retry, reassignment, lease expiry, or replay on crash or timeout.
- Distinguish `not dispatched`, `possibly dispatched`, and `verified outcome` in operator diagnostics; do not infer completion from `dispatch_committed`.
- Existing B1 budget reservations and cumulative ledger remain unchanged during this design phase. Refund/settlement rules require a separate auditable decision; never refund an ambiguous outcome automatically.
- Never hold a SQLite write transaction open across network I/O.
- Require bounded payloads, adapter timeouts, constrained destinations, credential isolation, and redaction of user/agent secrets in logs.

## Required review and test gates before implementation

1. Explicit v3→v4 migration, populated-data preservation, repeated migration, foreign keys and injected rollback failures.
2. Concurrent coordinators: exactly one durable dispatch intent; no second adapter invocation by local coordination.
3. Wrong token/worker, stale `ready`, changed policy, revoked or expired original session/grant, disabled principal, suspended agent, changed action rule and changed adapter configuration: no dispatch.
4. Audit or state-write failure: no dispatch intent and **zero** adapter calls.
5. Fake adapter: success, verified no-effect failure, timeout, ambiguous response, duplicate callback and malformed response; no external effects in conformance tests.
6. Crash injection before intent commit, after commit/before call, after call/before outcome commit; never automatic replay, preserve unknown-outcome evidence.
7. Prove the adapter's idempotency/fencing semantics independently before enabling any real side effect.
8. Confirm B1/B2.1/B2.2 and MAP v0.1 regressions remain green. Resolve the three inherited expected failures before production authorization claims.

## Decision register (must be resolved before coding)

- **D1:** Adopt `dispatch_committed` or another precise state name; avoid misleading `running`.
- **D2:** Define which adapters can prove downstream idempotency and which must remain disabled.
- **D3:** Define adapter-side revocation/fencing and emergency-stop semantics; identify actions requiring strict enforcement.
- **D4:** Define evidence for `succeeded`, `failed` and `outcome_unknown`, including manual reconciliation authority.
- **D5:** Specify budget settlement, expiry and operator permissions separately.
- **D6:** Decide whether B2.3's first implementation is **simulation-only** (recommended), with an injected fake adapter and no network I/O.

**Implementation gate:** written approval of the decisions above, threat-model review and passing local/CI tests. Until then, B2.3 remains documentation only.
