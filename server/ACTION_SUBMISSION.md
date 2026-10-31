# MAP v0.4 preparation — B1 atomic submission

Experimental local reference, not production authentication or an executor.
The MAP v0.1 wire schemas are unchanged. All jobs remain `queued`; the database
constraint rejects other states. There are no workers, external effects, retries
of effects, automatic refunds or execution guarantees.

## Trusted setup and API

Use one local SQLite file initialized by `SQLitePolicyEngine` and `SessionStore`.
Provision users, agent descriptors and grants through trusted bootstrap code.
Never expose `enroll`, `register_agent`, or arbitrary `verified_actor` arguments
to unauthenticated clients. B1 does not implement an identity provider.

```python
from action_service import ActionService, ActionRule

service = ActionService(database, actions={
    "game.feedback": ActionRule(
        scope="game.test_feedback", cost_minor=100, revision="price.1"
    )
})
result = service.submit(
    token=token, agent_id="agent.shared.01", delegation_id="grant.01",
    target_id="game.maze", action_type="game.feedback",
    parameters={"text": "example"}, idempotency_key="request.1"
)
```

The action catalogue is trusted host configuration, copied into an immutable
mapping of immutable rules. Each allowed action has a fixed nonnegative integer
reservation and required scope. Unknown actions are denied. Parameters cannot
override the configured price or scope. These are illustrative budget units, not
currency settlement. Variable-cost execution needs a separately reviewed costing
and enforcement contract; it is outside B1. A malicious or misconfigured host can
still choose unsafe prices. There is no client `cost_minor`, `user_id` or `at` field.

The optional injected clock is only a trusted server/test dependency. By default,
the service uses server wall time and samples it after acquiring the write lock.
Wall-clock rollback protection is not implemented.

## Transaction and authorization

Each submit opens one connection, enables foreign keys, and executes
`BEGIN IMMEDIATE`. It does not invoke legacy methods that open transactions.
Within this transaction it verifies token hash, user disablement, session revocation
and expiry, agent/delegation binding, registered delegation agent, requester,
grant status/revocation, agent suspension, scope, target and grant validity.

It then checks idempotency and both budget levels, updates the reservation, inserts
the job and inserts its `job.queued` audit event. Commit precedes the returned
successful result. Explicit denials roll back; any exception, including SQL or
commit errors, rolls back and propagates. Unexpected storage/configuration errors
are not reported as accepted jobs. No success is returned before commit.

Revocation and submission serialize on SQLite's writer lock. A revocation committed
before submit acquires the lock causes denial. If submit obtains the lock first,
revocation waits and the queued job may already exist when revocation completes.
That is the transaction ordering, not a guarantee of cancellation. B1 does not
cancel existing queued jobs; B2 must recheck permissions before any future start.

## Accounting and legacy compatibility

`grants.spent_minor` remains the authoritative cumulative reservation ledger.
Delegation usage is that row; agent usage is the sum across **all** grants for the
agent, including revoked/expired grants. The grant update therefore increases both
logical reservations atomically; no duplicated agent counter can drift from legacy
rows. The job additionally records its own reservation, price revision and policy
revision. Job cost must not be added to the grant sum a second time.

All existing v0.2 reservations count, including those without operation IDs. B1
does not infer whether they were executed, failed or refunded. Existing excess
over a limit is retained, and new submissions are denied until policy/accounting
is reconciled through a future reviewed mechanism. No legacy reservation is erased.
Integer values and limits are checked against signed 64-bit storage bounds.

The legacy APIs remain unchanged. **Their old authorization path still has the
Phase-A documented gaps.** They must not be exposed as an alternative execution or
reservation endpoint in a deployment relying on B1 limits. B1 sees committed
legacy usage, but an old `authorize()` caller can still overspend the aggregate
agent budget afterwards. Database writes and provisioning are trusted operations;
B1 is not a security boundary against other code with database write access.

## Idempotency contract

The unique scope is `(authenticated user, delegation, idempotency key)`, independent
of bearer-token identity or rotation. All current authorization checks run on
replay too. A valid identical retry returns the original job ID, without another
reservation or event. Revoked/expired authorization cannot retrieve it via submit.

The canonical semantic request includes format version, authenticated user,
agent, delegation, target, action type, derived scope and the full parameters.
Sorted JSON object keys, compact separators and escaped Unicode form the B1
canonical encoding. Array order and scalar type distinctions are retained:
`1` and `1.0` are distinct, as are distinct Unicode sequences. Non-finite floats,
non-string object keys, isolated Unicode surrogate code points in keys or values,
non-JSON values and parameter encodings over 64 KiB are
rejected. The 64 KiB bound counts characters in the ASCII-only escaped
canonical representation, so it also counts its UTF-8 bytes; it is not a raw
transport byte limit. Deeply nested parameters are rejected when recursion
limits are reached. This is a defined Python reference format, not a claim of RFC 8785 or
cross-codec canonicalization. Raw JSON parsing and duplicate-key rejection belong
to a future transport adapter.

Both SHA-256 fingerprint and exact canonical request are compared. Altered semantic
content returns `idempotency_conflict`. Server pricing revisions are not client
request semantics: identical retries retain the originally stored reservation and
price revision, even if prices change. A changed required scope changes the
fingerprint. New keys use the current price. No automatic deduplication expiry exists.

A key matching an existing legacy `(delegation_id, operation_id)` returns
`legacy_operation_conflict`; a reservation must never silently become a job.
Callers must reconcile its history, not blindly retry with a new key.

## Additive migration

Construction performs an idempotent transaction adding `action_schema` (version 1),
`action_jobs`, `action_audit`, and `grants_agent_budget` index. Existing base tables
must already exist. Unsupported action-schema versions fail closed. No existing
table or record is deleted, rewritten or backfilled into jobs; `operations` remains
unchanged. Restart repeats migration safely. This supports the repository's known
v0.2/v0.3 schema, not arbitrary or manually corrupted database layouts.

The audit event has a stable ID, authenticated actor, server time and job reference;
the job contains immutable-by-API request and policy/price metadata. Tokens and
credentials are not copied into jobs/events. Audit records are local and not
tamper-evident against database administrators. Denied requests are not persisted
as audit events in B1. Retention, backup operations and recovery administration
remain future work.

## Verification

`tests/conformance/test_action_submission.py` covers concurrent identical and
distinct submissions, cross-delegation budgets, authorization failures, canonical
conflicts, token rotation/restart, old reservations, queued-only storage and
transaction fault injection at each write boundary. Existing Phase-A expected
failures remain unchanged and concern only the legacy APIs.

Run from the repository root:

```text
python -B -m unittest discover -s tests/conformance -p 'test_*.py' -v
python -B tests/conformance/validate_map_v01.py
```

## Scaling and resource boundaries

See [scalability direction](../docs/SCALABILITY.md) for the proposed separation of
wire protocol, submission, worker lifecycle and future database backends. The
current single-file SQLite writer lock is a local correctness reference, not a
horizontal-scaling design. B1 enforces the serialized 64 KiB parameter bound
before opening its write transaction, but does not yet define independent
transport-level body-size, nesting-depth, or rate limits.

Additional tests: `tests/conformance/test_unicode_boundary.py` and
`tests/conformance/test_action_payload_limits.py`.
