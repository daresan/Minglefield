# SEC-01 — Variant 2: Authoritative Remote Admission Service (Architecture Decision Draft)

Status: **preferred design direction, not production approval**  
Scope: independent Minglefield game developers and external game systems  
Related: [SEC01_B2_INTEGRATION_CONTRACT.md](SEC01_B2_INTEGRATION_CONTRACT.md) and [SEC01_ADAPTER_FENCING_RFC.md](SEC01_ADAPTER_FENCING_RFC.md)  
Verified starting point: maintainer reported 5/5 composite tests, 257/257 conformance tests, MAP v0.1 validator PASS and clean Git at `0489975`.

## Decision

**Prefer variant 2**: a trusted, remotely callable authority/admission service, while keeping game-specific effect execution under the game developer's control. **Do not implement a standalone "is authorized?" preflight endpoint and describe it as fencing.** The authority check and durable admission/idempotency decision MUST be one serializable operation at one authoritative linearization point.

**Critical qualification:** A remotely recorded admission cannot, by itself, make a separate game-side side effect atomic or irrevocable. A participating game adapter must enforce admission as a mandatory gate at its own effect boundary. Exact guarantees depend on whether the effect is transactional, idempotent, cancellable and independently executable. A game that can bypass this gate cannot claim strong SEC-01 fencing.

## Roles and trust boundaries

| Actor | Responsibility | Must not do |
| --- | --- | --- |
| MAP/B2 | Authenticate original requester, validate current agent/grant/session/principal authority, persist intent and canonical request fingerprint | Interpret `dispatch_committed` as adapter acceptance or effect success |
| Trusted admission service | Authenticate the executor, bind intent to current authoritative revocation state, atomically decide `deny` / `admitted_new` / `previously_admitted`, record idempotency and evidence | Admit on stale asynchronous-only policy, trust user-provided adapter/target/effect key, report successful game execution |
| Game-side adapter | Verify admission proof and audience/binding, prevent independent/bypassing effect paths, validate action-specific parameters; execute at most once according to its own durable mechanism | Treat a reusable `previously_admitted` response as permission to execute again |
| Operator/reconciler (future) | Investigate unknown outcomes using authenticated evidence | Automatically retry or refund an unknown effect |

All calls and receipts require authenticated identities and channel protections before any real adapter; those controls are future work covered by SEC-02/03/04/05.

## Linearization and ordering

For strict revocation, the admission service must consult **authoritative** session/grant/agent/principal state and compare a persisted monotonic epoch (or an equivalent invalidation mechanism) in the **same serializable transaction** that records admission. The policy/revocation writers and admission decision must share a verifiable global order; syncing a second database asynchronously is insufficient.

### Transaction A — revoke first

1. Trusted policy authority commits session/grant/agent/principal revocation and epoch update.
2. Executor presents a committed intent and trusted authorization artifact to the admission service.
3. Admission transaction sees revoked/stale authority, denies and creates **no new admitted effect**.
4. Game adapter performs no effect.

### Transaction B — admit first

1. Admission transaction verifies authority and stores the immutable effect-key-to-intent binding as `admitted_new`.
2. Policy authority commits revocation afterwards.
3. The admission record remains historical; the policy cannot retroactively undo the admission.
4. Game-side execution may still be pending. The system MUST distinguish **admitted** from **executed** and document whether game-side cancellation is possible.

### Transaction C — validation-to-use race

1. A separate capability-shape check returns `bound_shape_not_authenticated_or_admitted`.
2. Revocation commits.
3. Admission MUST re-check authoritative state inside its own acceptance transaction and deny. No previously computed successful validation can override this result.

### Transaction D — timeout/partition

1. Executor submits an admission request and the response is lost.
2. Outcome is **unknown**: the service may have durably admitted, or rejected, the request.
3. Repeated queries by effect key return authenticated **status only**; they MUST NOT trigger a new game invocation. No automatic retry and no automatic refund.
4. If the service cannot obtain current authoritative revocation state, it fails closed for **new** admissions. Previously admitted status is never a new-effect authorization.

## Interface sketch — NON-NORMATIVE and NOT IMPLEMENTED

A future private `admit_effect` request would bind: contract version; committed job ID; immutable request fingerprint; original session linkage proved *issuer-side*; agent, grant, user and authority epochs; action/scope/target; adapter ID/version and audience; effect idempotency key; signed issuer metadata; authenticated executor identity and deadline. No bearer session token, token hash, claim token or untrusted parameters may be used as authority proof.

Possible results:
- `denied` with bounded reason and attributed audit evidence;
- `admitted_new` with a durable, adapter-specific acceptance receipt (not proof of execution);
- `previously_admitted` containing historical status only (not renewed execution permission);
- `unknown` at the caller boundary on timeout or unavailable evidence, never guessed success.

The actual endpoint, cryptographic format, key rotation, access control, data model and status reconciliation API require a separate design and security approval. Do not introduce wire/schema commitments on the basis of this sketch.

## Effect-side enforcement choices

**Transactional game effect:** best candidate for strong guarantees when the game can bind receipt consumption and mutation in one durable game-owned transaction, with unique effect key and no bypass paths. The cross-system admission decision still needs explicitly defined cancellation and uncertainty semantics; it is not automatically a single distributed transaction.

**Idempotent nontransactional effect:** requires a game-owned durable dedupe barrier, effect status evidence and a defined crash/unknown policy. `At most one new admission` by MAP does NOT prove `at most one external execution`.

**Irreversible external API without fencing:** no strict guarantee is possible; keep high-risk effects blocked. Short-lived capabilities only bound exposure time, not immediate revocation.

## Threats and adversarial acceptance tests (future)

1. Revoke each of session, grant, agent and principal **after intent** but **before admission**: no new admission.
2. Race admission/revocation in both serial orders across independent processes; assert exactly the stipulated winner.
3. Modify target, scope, action, fingerprint, adapter, audience, original-session linkage, effect key and executor: deny, preserve original binding.
4. Reuse effect key with identical content: historical status only; changed content: integrity denial.
5. Admit under stale cache, replicated lag, clock skew, unavailable authority, replayed nonce or rolled-back epoch: deny new admission.
6. Crash before admission, after admission/before game execution, and after execution/before report: preserve correct unknown statuses and no automatic replay.
7. Game adapter bypass test: attempt effect without accepted/verified proof, or twice with same proof; both must be blocked by game-side enforcement.
8. Revoke after admission/before execution: accurately classify as already admitted; either enforce game-supported cancellation or explicitly document residual exposure.
9. Simulate service partition and lost reply; require authenticated read-only reconciliation, no guessed success/refund.

## Gate and immediate next work

1. **Architecture review:** decide ownership of the authoritative revocation transaction and how remote admission sees exactly that state without asynchronous freshness gaps.
2. **Game integration interface design:** choose a reference transactional game adapter contract with durable dedupe and proof consumption; keep models/algorithms developer-owned.
3. **Isolated simulation only:** model admission service and mock game transaction, with concurrency/partition negative tests. Do not modify B2 schema v4 or its fake coordinator.
4. **Security gates:** resolve SEC-01/02/03/04/06 and outstanding audit/reconciliation matters, then obtain separate adapter-specific maintainer approval.

**Disposition: SEC-01 CRITICAL / OPEN; NO-GO for real effects.** Variant 2 is the preferred architecture to investigate, not an assertion that remote admission solves the distributed effect-atomicity problem.
