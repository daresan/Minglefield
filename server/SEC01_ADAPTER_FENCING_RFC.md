# RFC — SEC-01 Effect-Boundary Revocation Fencing (Draft)

Status: **design only; NOT approved for implementation or real effects**  
Scope: Minglefield MAP B2 simulation-to-real-adapter boundary.  
Security finding: SEC-01 (Critical / open).  
Evidence baseline: maintainer's Windows run at `eccb7d3`: 6/6 fake-coordinator tests, 211/211 conformance tests, MAP v0.1 validator PASS, clean working tree.

## 1. Problem and non-goals

B2's `ready -> dispatch_committed` transition rechecks current authority transactionally and records an effect key, adapter identity/version and request fingerprint. The actual fake invocation occurs **after** the transaction. Revoking a session, grant or agent after commit does not provide a fence at a future real effect-owning system.

The simulation's no-replay guarantee is not a revocation guarantee. This RFC does not implement an executor, add public endpoints, modify wire schemas, migrate storage, or authorize real effects. It does not promise cancellation of effects already accepted.

## 2. Proposed authority and effect contract

A future trusted executor MUST authenticate independently (SEC-04) and present an immutable, server-issued effect authorization binding:

- job ID and original user/agent/delegation/session identities;
- action type, target, trusted adapter ID and version;
- canonical request fingerprint and effect idempotency key;
- submission policy revision and a monotonic authorization epoch covering relevant grant/agent/session revocations;
- bounded authorization lifetime and issuer/audience binding.

No caller-controlled request parameter may supply or override these fields. The exact credential format, storage, signing, expiry and trust anchors remain design decisions, not existing B2 features.

## 3. Atomic effect-boundary decision

The effect-owning system MUST atomically compare the supplied authorization epoch and effect identity with authoritative current state **at the point where it accepts the effect**, and persist a decision tied to the idempotency key. Repeating the same key with a different request fingerprint, target, action or adapter binding MUST fail. A revoked or stale epoch MUST fail before new effect acceptance.

A check performed only by the MAP coordinator immediately before an HTTP request is insufficient: revocation may occur between that check and the external acceptance. The adapter must document whether it can perform an atomic fence itself, use a trusted transactional authority service, or cannot offer strict fencing. Network partitions and stale caches cannot silently count as fresh authorization; high-risk effects MUST fail closed.

**Ordering contract:** if revocation is committed before the effect's atomic acceptance, the effect MUST be rejected. If effect acceptance is committed first, later revocation cannot retroactively guarantee cancellation. The system must expose the acceptance decision and evidence, not infer it from a dispatch intent or network timeout.

## 4. Revocation scope and versioning

Grant revocation, agent suspension/policy revision, original session revocation/expiry, and principal disablement require explicitly defined epoch-invalidation rules. Epoch increments must be monotonic, persisted and serialized with revocation updates. Avoid ABA: an authority removed and subsequently restored must not make an old capability valid again. A plain agent descriptor revision alone is insufficient to cover grant/session changes.

The existing B2 `policy_revision` check at claim/prestart/dispatch is pre-intent protection; it is not this effect-boundary epoch.

## 5. Crash, uncertainty and reconciliation

Preserve the durable `dispatch_committed` intent and existing no-automatic-replay policy. A timeout or crash around effect acceptance is **unknown**, not success or confirmed no-effect. Any future read-only reconciliation requires authenticated executor identity, verifiable adapter evidence, idempotency lookup semantics, audit attribution and operator review (SEC-02/03/05). Do not refund or replay automatically on an unknown outcome (SEC-08).

## 6. Adapter risk classes and admission

- **Fence-capable adapter:** eligible only for a later, separately approved implementation after atomic acceptance, idempotency, evidence and concurrency tests pass.
- **Bounded-delay revocation adapter:** cannot claim strict revocation; a separate explicit risk decision is required, and high-risk effects remain prohibited.
- **No-fence adapter:** prohibited for high-risk effects. Simulation-only use is unaffected.

A future per-adapter contract must document maximum revocation propagation delay, effect reversibility, acceptance point, concurrency guarantees and failure behavior. MAP does not assume game developers use any particular model, engine or algorithm.

## 7. Required adversarial verification (not yet implemented)

1. Revoke grant after intent but before effect acceptance: deny.
2. Revoke original session, disable principal, suspend agent or change policy epoch after intent: deny.
3. Race revocation and acceptance in both serialization orders; assert only the specified winner can accept.
4. Reuse effect key with mismatched target/fingerprint/adapter: deny.
5. Replay same key after success, timeout and crash: no duplicate effect; preserve unknown where evidence is absent.
6. Test stale cache, partition, missing/expired capability, compromised/untrusted executor, and epoch rollback/ABA.
7. Verify refusal leaves no externally accepted effect and records attributable evidence; verify accepted-before-revoked is reported accurately rather than called preventable.

## 8. Decision gate

**SEC-01 remains Critical / OPEN.** This RFC is a proposal for independent security and maintainer review. No production adapter, real invocation, public endpoint, automatic replay, or schema migration is authorized. The current B2 test baseline proves only the documented simulation properties.
