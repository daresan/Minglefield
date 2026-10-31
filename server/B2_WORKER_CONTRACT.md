# MAP v0.4 preparation — B2.1/B2.2 worker claim and reauthorization contract

Status: **design draft; no worker implementation or external execution is authorized**.
Branch: `wip/map-v04-phase-b1`. MAP v0.1 wire schemas remain unchanged.

## Scope and compatibility

B1 `ActionService.submit()` remains unchanged and continues to create durable
`queued` jobs and reserve budget once. B2 adds a **trusted internal worker API**,
not a public MAP endpoint. Worker identity, executor selection and clock are
trusted server-side inputs, never caller-controlled request parameters.

B1's `action_jobs.state CHECK(state='queued')` and
`action_audit.job_id UNIQUE` constraints cannot represent B2 transitions.
Introduce an additive, versioned SQLite migration (schema v2) that rebuilds
those two tables transactionally while preserving all B1 records and their IDs,
requests, reservations, timestamps and queued audit events. Keep a one-to-many
audit history with unique event IDs; never silently delete historical events.
Migration must be restart-safe, fail closed for unsupported versions, and
maintain foreign-key integrity. Do not change legacy authorization APIs.

## Proposed state machine

```text
queued ── claim + reauthorize ──> claimed
   │                              │
   └── deny at claim ──────────> denied
                                  │
                                  ├── pre-start reauthorize fails ──> denied
                                  └── later B2.3+ start ────────────> running
                                                                  ├──> succeeded
                                                                  ├──> failed
                                                                  └──> outcome_unknown
```

Only `queued -> claimed` and `queued -> denied` are in B2.1/B2.2.
`claimed` is **not** permission to perform effects: before any future start,
authorization must be checked again in a serialized transaction. `running`,
terminal transitions, cancellation and recovery are explicitly deferred.
No worker is allowed to execute an external effect in this phase.

## Atomic claim protocol

- A trusted worker supplies a bounded, nonempty `worker_id` and requests a
  single eligible job. Never accept an arbitrary user/agent identity from it.
- Open SQLite `BEGIN IMMEDIATE`; choose the oldest queued job with stable
  `(created_at, job_id)` ordering. All competing workers serialize on the
  writer lock. A worker may only claim a job while its state is `queued`.
- Within the same transaction, re-evaluate authorization against **current**
  session/principal, agent, grant, action rule, scope, target and validity.
  Compare immutable job request fields to stored identity/delegation bindings.
  A B1 job has no persisted session reference: **the design must resolve this
  before coding**, either by adding a trustworthy session binding at submit
  time or by defining a documented, narrower grant/principal-based claim policy.
  Never infer the original session from a new token supplied by the worker.
- If authorization fails, atomically transition to `denied` and append an
  audit event with a machine-readable denial reason. Do not release or refund
  reservations automatically; B1's cumulative ledger remains authoritative.
- If authorization succeeds, atomically transition to `claimed`, assign the
  worker and a fresh opaque claim token, and append `job.claimed` audit event.
  Commit before returning claim data. An exception rolls back *all* changes.
- A claim token is an internal fencing credential, not a bearer authorization
  for effects. The future start transition must verify token, worker ownership,
  current state and reauthorization under the writer lock.

## Revocation and concurrency guarantees

- Revocation committed before the claim transaction acquires the writer lock
  must cause denial. A claim committed first may remain `claimed` after a
  subsequent revocation, but **must not start** without a new check.
- Two workers cannot successfully claim the same queued job. The job state,
  worker ownership and audit event change together or not at all.
- If a worker crashes after a claim, the job stays `claimed` in B2.1/B2.2.
  No automatic lease expiry, reclaim, retries, or external effects yet.
  B2.3/B2.4 must define fencing, leases, crash recovery and effect semantics.
- Do not claim exactly-once external execution. Atomic database claims alone
  cannot guarantee it.

## Tests required before enabling worker behavior

1. Concurrent workers claim one job at most once, with one claim audit event.
2. Deterministic FIFO selection and idempotent B1 replay remain intact.
3. Revoked/expired grant, suspended agent, disabled principal, and invalid
   session policy (once resolved) cannot progress to `claimed`.
4. Revocation-before-claim denies; claim-before-revocation cannot authorize
   a future start.
5. SQL trigger fault injection at state update and audit insertion rolls back.
6. Migration from populated B1 SQLite database preserves all jobs, audit
   history, reservations and foreign keys; repeated migration is harmless.
7. Worker crash/restart leaves claimed job inert; no duplicate claims/effects.
8. Existing B1 and MAP v0.1 conformance tests remain green.

## Decision gate before implementation

**Open decision:** Session semantics. B1 stores `user_id`, `agent_id` and
`delegation_id`, but not the session/token identifier. A worker cannot
recheck the *specific submitting session* without new durable metadata.
Recommended: persist a non-secret session identifier/hash reference for new
jobs and define a safe treatment of existing B1 jobs lacking it (deny claim
until resubmitted or explicitly reconciled). This requires reviewing the
current session schema and rotation behavior before implementing B2.1.

No changes to `main` or real executor integrations are part of this draft.
