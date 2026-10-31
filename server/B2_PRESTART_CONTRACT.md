# MAP v0.4 — B2.2 pre-start authorization design

Status: **B2.2 implementation and regression gate complete for the current no-effects prototype; not production security certification**. Branch: `wip/map-v04-phase-b1`.
As of 2026-10-31: 124 tests OK (three known expected failures), 17 focused pre-start tests and six migration tests OK, MAP v0.1 validator PASS and `git diff --check` clean, per maintainer's local Windows run.
No changes to MAP v0.1 wire protocol, `main`, or external executors.

## Decision: no automatic retry of external effects

A claimed job is inert. Worker crash or restart must not release, reclaim,
reassign, or automatically replay a claim. A future effect may have occurred
even if its completion was not durably recorded; retry without an executor
idempotency guarantee risks duplicate effects. Operator reconciliation and
`outcome_unknown` handling belong to a later phase.

## B2.2 scope: pre-start gate, no effects

B2.2 implements a trusted internal operation that consumes `job_id`,
`worker_id` and the original opaque claim token. It must never accept a
user-supplied principal or policy decision. The token is only a fencing
credential, **not** permission to execute.

Within one `BEGIN IMMEDIATE` transaction:

1. Require schema version and state appropriate to this operation; fail closed
   on unsupported versions, missing jobs and legacy/incomplete claims.
2. Verify `state='claimed'`, exact `claimed_by`, and constant-time equality
   of SHA-256 claim-token digest with the stored `claim_token_hash`.
   Never log or persist the plaintext token.
3. Reauthorize the **original** submitting session, principal, agent, grant,
   scope, target, validity window and current trusted action rule. Use the
   same fail-closed policy as claim, under the same writer lock. A replacement
   session cannot revive the job.
4. If authorization fails, transition `claimed -> denied` and append an
   audit event atomically. Preserve the budget reservation and claim metadata
   for forensic history; no automatic refund.
5. If authorization succeeds, record a durable authorization outcome and audit
   event atomically. **Do not execute effects in B2.2.**

## State and schema decision

Current schema v2 permits only `queued`, `claimed`, `denied` and audit
events `job.queued`, `job.claimed`, `job.denied`. It cannot persist a
`started` state or a successful pre-start event.

B2.2 uses an explicit schema v3 migration, after tests
for populated-v2 preservation and rollback. Implemented new state:
`ready` (authorization passed but **no effect started**). Do **not** call
it `started`: that would falsely imply execution. A later B2.3 transaction
may move `ready -> running` only after a fresh policy check and an agreed
executor/idempotency contract. In B2.2, `ready` remains inert and is never
automatically retried.

Implemented v3 transitions (future transitions shown for context):

```text
queued  -> claimed | denied       (B2.1)
claimed -> ready   | denied       (B2.2)
ready   -> running | denied       (future B2.3; no implementation now)
```

Add `job.ready` to the audit event vocabulary. Preserve old audit events,
reservations, identifiers and claim-token hashes. Migration must be
transactional, idempotent and foreign-key clean. No silent upgrade on normal
B1 service startup.

## Security and test gates

- Wrong worker, wrong token, missing token, wrong state, unknown job: reject
  without state change, audit entry, or budget mutation.
- Token digest verification must be constant-time; no plaintext persistence.
- Revocation or expiry after claim but before pre-start must deny.
- A valid claim with current permissions can transition only once; competing
  callers cannot both succeed.
- SQL fault injection at state and audit writes rolls back the entire gate.
- Restart preserves `ready` as inert; no automatic execution or reclaim.
- v2 -> v3 migration preserves populated jobs, events and reservations.
- Existing B1, B2.1 and MAP v0.1 conformance checks remain green.

## Implementation order

1. Add v3 migration and migration tests, without modifying worker behavior.
2. Add the trusted pre-start gate and focused tests.
3. Run full conformance locally; review security invariants before any
   executor integration.

## Verified implementation status (2026-10-31)

- `server/b2_prestart_schema.py`: explicit transactional v2→v3 migration; repeat invocation preserves populated v3 jobs, `ready` state, events and reservations.
- `server/b2_prestart.py`: trusted claim fencing and current-policy reauthorization, atomic `ready`/`denied` plus audit; no effects. Malformed stored claim digests and unencodable tokens reject without mutation.
- `server/b2_worker.py`: claim-only worker accepts v2/v3 and migrates legacy v1 to v2, without downgrading v3.
- `tests/conformance/test_b2_prestart_gate.py`: 17 passing local tests covering claim ownership, original session revocation/expiry, grant revocation, agent suspension, malformed grant/request policy, concurrency, restart, audit and state-update rollback, invalid inputs and hashes, and v3 claim integration.
- `tests/conformance/test_b2_prestart_schema.py`: six passing local tests covering migration preservation, rollback, repeat invocation, v1 rejection, v3 ready/audit and post-migration submission.
- **Residual hardening / future review:** explicit tests for incomplete claim metadata and legacy null session binding at pre-start; grant expiry after claim; deeper structural validation when schema version already reads v3; security review of trusted caller boundary and malformed DB types. These are not claimed as fully tested.
- **B2.3 prerequisite:** define trusted executor boundary, reauthorize immediately before external effect, explicit effect idempotency keys, durable outcome/unknown-outcome handling, no automatic replay or reassignment after ambiguous execution, operator reconciliation and audit semantics. Do not treat `ready` as an irrevocable execution capability.
- The three known expected failures are inherited legacy authorization-path issues, **not** waived for production readiness.

