# MAP v0.4 — B2.3 simulation-first decision proposal

Status: **proposed decisions for maintainer review; no executor implementation or real effects authorized**.
Branch: `wip/map-v04-phase-b1`. Companion to [B2_EXECUTOR_CONTRACT.md](B2_EXECUTOR_CONTRACT.md).

## Recommended D1–D6 resolutions

| ID | Recommendation for the first prototype | Constraint / unresolved production decision |
| --- | --- | --- |
| D1 | Use `dispatch_committed` for a durable intent, never `running` as proof of effect. Terminal `succeeded`, `failed`, `outcome_unknown` require separate audit evidence. | Precise lifecycle of operator reconciliation and cancellation remains open. |
| D2 | Allow **only an in-process fake adapter** in the first implementation. No HTTP, subprocess, file writes outside the test database, game mutation, or plugin-defined real adapter. | Each real adapter later needs independently verified idempotency and payload binding. |
| D3 | Reauthorize under the writer lock before intent commit; fail closed on revoked or changed policy. Fake adapter has no externally observable effect. | Real-time revocation after commit cannot be guaranteed without downstream fencing; block real high-risk adapters. |
| D4 | Fake adapter emits deterministic typed outcomes: confirmed success, confirmed no-effect rejection, or ambiguous result. Timeout/crash/invalid response => `outcome_unknown` or a documented unresolved intent, never inferred success. | Define evidence provenance, reconciliation authority, and read-only external verification before real dispatch. |
| D5 | Keep B1 budget reservation and cumulative spent ledger unchanged in B2.3 simulation. No automatic refunds, settlement, or expiry-driven retries. | Settlement and operator approval need their own design and tests. |
| D6 | Implement **simulation-only**, opt-in, with an injected fake adapter and explicit test harness. Never start a background executor on application startup. | Real effects require a separate, explicit maintainer approval and security review. |

These recommendations are **not yet accepted decisions**. They narrow the next review to a safe testable slice.

## Implementation slices after approval

1. **B2.3a — schema only:** explicit v3→v4 migration and tests. Proposed `dispatch_committed` plus terminal states and audit events; persist a unique per-job idempotency key, immutable request fingerprint and adapter identifier/version. No executor code or effects.
2. **B2.3b — durable dispatch-intent gate:** trusted internal API rechecks original session, worker/claim fencing and current policy; one atomic intent and audit entry. Tests for concurrency, revocation, bad metadata and SQL rollback. Still no adapter invocation.
3. **B2.3c — fake-adapter harness:** separate synchronous test-only invocation after committed intent. No network/subprocess/real filesystem effects; no automatic restart replay. Crash-point injection, outcome classification and audit tests.
4. **B2.3d — review gate:** local/CI conformance, threat model and explicit go/no-go for *designing* real adapters. Production integration is a separate future milestone.

## Threat model and invariants to verify

- **Untrusted inputs:** original request JSON, stored malformed database fields, adapter responses, caller-supplied worker IDs and claim tokens. Only trusted server-side configuration may select an adapter.
- **Authorization drift:** grant revoked/expired, session revoked/expired, principal disabled, agent suspended, action rule or target changed between `ready` and dispatch intent.
- **Concurrent claims:** only one coordinator commits intent for a job; every losing contender produces zero fake-adapter calls.
- **Commit-to-effect gap:** after committing intent, crash may occur before fake invocation. Never infer that a remote effect happened; do not auto-replay on restart.
- **Effect-to-outcome gap:** after fake invocation, crash may occur before recording the outcome. Mark uncertainty explicitly on recovery or leave a clearly documented unresolved intent for operator reconciliation; never auto-retry.
- **Audit and credentials:** append-only event semantics; no raw bearer/session/claim token, secrets or sensitive payloads in audit. Validate uniqueness and referential integrity.
- **Migration integrity:** preserve v3 jobs, audit events, claims, ready state, idempotency and cumulative reservations; rollback entirely on injected failures.

## Approval gate

Before code beyond documentation, maintainer should approve or amend D1–D6, particularly the meaning of `failed`, handling of ambiguous outcomes, and the hard prohibition on real effects. Once approved, implement **B2.3a only**, commit it on the development branch, and request local tests before advancing.

**Current baseline:** B2.2 locally verified with 124 tests OK (three inherited expected failures), 17 focused gate tests, six migration tests and MAP v0.1 validator PASS. No B2.3 runtime exists.
