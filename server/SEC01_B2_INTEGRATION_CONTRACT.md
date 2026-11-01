# SEC-01 — MAP/B2 to Game Adapter Fencing Integration Contract (Draft)

Status: **design contract only; NOT approved for implementation or external effects**  
Branch: `wip/map-v04-security-hardening`  
Parent: [SEC01_ADAPTER_FENCING_RFC.md](SEC01_ADAPTER_FENCING_RFC.md)  
Evidence: maintainer verified **222/222 conformance tests**, MAP v0.1 validator PASS and clean Git working tree after `6128d1c`. This document is not executable and has not been independently tested.

## A. Concrete existing boundaries

| Component | Authoritative data today | Relevant transaction/behavior | Limitation |
| --- | --- | --- | --- |
| `ActionService.submit` | `auth_sessions`, `auth_principals`, `grants`, `agents`, trusted `ActionRule` | `BEGIN IMMEDIATE`; persists `action_jobs` with `request_json`, SHA-256 `fingerprint`, `policy_revision`, original `session_token_hash` and reserved cost | No effect-side capability or aggregate revocation epoch |
| `ClaimWorker._check` | Original session, current grant/agent and trusted action rule | Shared transactional check invoked at claim, prestart and dispatch | Only fences **before** intent commit |
| `DispatchGate.commit_intent` | Claimed worker/token and current authorization; trusted adapter map | Atomic `ready -> dispatch_committed`; writes `effect_idempotency_key`, `dispatch_fingerprint`, `adapter_id`, `adapter_version`, `dispatched_at` | Does not authenticate an external executor or convey an effect-side authorization fence |
| `FakeSimulationCoordinator.run_once` | Reads effect key from `dispatch_committed` | Fake invocation **after** intent transaction; never replays committed intent on restart | No post-commit revocation check, no real effect-side acceptance |
| `SQLiteEffectBoundary` (`sec01_fencing_sqlite.py`) | Separate simulation-only SQLite epoch and accepted-effect rows | `BEGIN IMMEDIATE` serializes revoke/accept across connections; accepts same-key replay as historical record | Not connected to B2, not authenticated, no shared epoch with real policy writers, no external effect |

These are observations about the current implementation, not claims of distributed guarantees.

## B. Security model: three distinct phases

1. **Authorization / intent (MAP):** validate current authority, produce a durable immutable intent and identifier. `dispatch_committed` means *only* that MAP recorded intent.
2. **Effect admission (effect-owning trust boundary):** atomically validate current authority/epoch and immutable intent binding, then record the *accepted* decision with durable idempotency state. This is the critical SEC-01 linearization point.
3. **Execution and outcome evidence (adapter):** an admitted effect may execute; result, timeout, unknown outcome and reconciliation are separate from admission. Admission must never be reported as successful execution.

**Strict revocation ordering guarantee:** revocation serialized before admission denies a new effect. Admission serialized before revocation cannot be retroactively undone. This contract must cover *the actual effect-owning system*; checking a MAP SQLite database immediately before sending a remote call does not close the network check-to-use race.

## C. Proposed responsibilities (not implemented)

**MAP authority service:**
- Owns the canonical source of user, agent, grant and session authorization decisions; maintains an appropriately scoped, persistent, monotonic **fencing epoch** or equivalent revocation token whenever any relevant authority is weakened, revoked, suspended, expired or disabled.
- Ensures that epoch updates and corresponding revocation state changes are serialized and durable; agents' `policy_revision` alone is not sufficient. Expiration must be evaluated against a trusted effect-side clock in addition to change epochs.
- Issues a short-lived authenticated, audience-bound authorization artifact derived solely from a verified committed intent. Defines revocation semantics, credential lifetime and failure behavior.

**MAP trusted coordinator/executor:**
- Authenticates as a separate least-privilege principal (SEC-04); obtains artifact only for an eligible intent. Never trusts caller-supplied effect key, revision, adapter ID or target.
- Cannot bypass admission, change request bindings or automatically retry an uncertain effect. Must not interpret `already_accepted` as permission to invoke a second time.

**Game adapter / effect-owning system:**
- Validates artifact signature/issuer/audience/expiry and **atomically** compares current authoritative fencing state at effect admission, *within the same acceptance boundary* that records the effect key and immutable binding.
- Rejects stale/unknown epochs, invalid credentials, mismatched bindings and missing current authority. Explicitly distinguishes new acceptance, historical same-key acceptance, denial and uncertain status.
- Does not provide strict revocation claims if it cannot participate in an atomic trusted admission protocol. Such adapters remain ineligible for high-risk effects.

**Game developer:** owns game-specific action semantics, parameter schemas, engine implementation and any custom deterministic algorithms or task models. MAP does not mandate a particular engine, model or central model-training service.

## D. Proposed versioned effect-authorization artifact — design fields

Proposed logical fields (not a wire JSON schema or existing DB columns):

| Field | Source / required binding |
| --- | --- |
| `contract_version`, `issuer`, `audience`, `issued_at`, `expires_at` | Trusted issuer and intended adapter; bounds capability use |
| `job_id`, `user_id`, `agent_id`, `delegation_id`, original session reference | MAP job and original-session linkage; no bearer token disclosure |
| `action_type`, `scope`, `target_id`, canonical `request_fingerprint` | Verified persisted request and trusted action rule |
| `adapter_id`, `adapter_version`, `effect_idempotency_key` | Committed immutable dispatch intent |
| `submitted_policy_revision`, `fencing_epoch`, `authority_scope` | Current authoritative policy and cross-source revocation epoch |
| `executor_identity`, `credential_nonce` | Authenticated coordinator/executor and artifact uniqueness |

The exact serialized representation, cryptography, freshness mechanism, replay resistance, clock skew and authority-scope granularity require security review. A `session_token_hash` is a local lookup reference, **not** an externally shareable authentication credential.

**Binding rule:** any discrepancy between the committed job, submitted policy, trusted action configuration, presented artifact and adapter-admitted binding is a denial. Include action-specific validated parameters in the binding via the immutable request fingerprint; parameter schema validation remains adapter-specific (SEC-07).

## E. Atomicity choices and unresolved distributed boundary

**Option A — collocated authority + acceptance:** trusted authority and effect admission commit in one transactional datastore controlled by the effect owner. Simplest defensible serialization semantics, but requires authority-state ownership and reliable replication of all MAP revocations into that datastore; asynchronous propagation alone cannot guarantee immediate revocation.

**Option B — trusted remote admission/authority service:** external adapter performs an authenticated admission operation whose authority check and durable idempotency record are serialized by an authoritative service. The service must ensure no independently initiated external side effect can bypass admission. A remote *precheck* without atomic acceptance is insufficient.

**Option C — offline capability with expiry only:** bounded exposure, **not strict immediate revocation**. Must explicitly advertise delay and be prohibited for high-risk effects under the current release gate.

**Open design question:** how MAP revocation transactions and remote admission share a single linearization order across failure/partition boundaries. Neither independent SQLite databases nor asynchronous epoch copying supply this property. No option is approved in this document.

## F. Required failure and recovery semantics

- **Revoked before admission:** no new acceptance; return a stable denial with attributable evidence.
- **Accepted before revocation:** preserve historical admission and one-effect-per-key invariant; later revocation does not erase acceptance.
- **Same key, same binding:** return historical admission/status only; never treat this as a fresh authorization to invoke again.
- **Same key, different binding:** deny and log integrity violation.
- **Timeout, crash, partition or stale authority view:** fail closed on new admission if freshness cannot be established; classify unknown execution outcome separately, **no automatic retry or refund**.
- **Lost/invalid capability, clock problems, epoch rollback or ABA:** deny; secure operator investigation where necessary.
- **Evidence:** authenticated admission receipts and execution/outcome evidence require a separate provenance and audit contract (SEC-02/03/05).

## G. Proposed implementation order and acceptance tests

1. **Specification only:** review trust boundary, epoch ownership, revocation coverage, authority freshness and admission linearization; decide A/B/C explicitly with a game adapter owner.
2. **Isolated trusted simulation:** model distinct session/grant/agent/principal epoch invalidation, expiry, immutable bindings, and restart/concurrency cases; keep all components outside B2 execution.
3. **Bridge design (no calls):** draft a read-only B2 intent projection and a versioned artifact validator, with tests proving that caller-controlled fields and existing `session_token_hash` cannot become external credentials.
4. **Security review:** authenticated executor, key management, crash evidence, threat modeling, external system capabilities, and explicit maintainer approval.
5. **Only after separate authorization:** implement a concrete effect-owning acceptance adapter and adversarial distributed tests. No real effect invocation or automated dispatch replay until release blockers are resolved.

Mandatory negative tests include post-intent grant revocation, session revocation/expiry, principal disablement, agent suspension/policy updates, effect-key rebinding, epoch rollback, cross-adapter audience misuse, parallel accept/revoke ordering, process restart, uncertain accepted-before-timeout states and stale/partitioned authority.

## G.1 Capability-validator adversarial follow-up (2026-11-01)

The isolated `sec01_capability_validation.py` validator checks exact envelope shape, committed intent fields, context strings, a time interval and the current simulated authority epochs. **It does not authenticate provenance or bind validation atomically to admission.** New adversarial regression tests at `41a059a` illustrate three distinct boundaries:

- An unsigned envelope constructed to match the trusted inputs can pass structural checks; `shape_valid_not_authenticated` is not an authorization decision.
- Revoking a grant after successful structural validation but before SQLite admission causes the *atomic admission* to reject the old epoch. Calling the validator alone does not protect this gap.
- The B2 `CommittedIntent` projection excludes the original session reference. Therefore the validator currently matches grant/agent/principal authority identities against the intent but **cannot establish that the supplied session identity is the original job session**. A separately provisioned session ID can pass its shape checks. This is deliberately documented as an unresolved binding gap, **not** an acceptable credential model.

**Required bridge decision before any capability issuance:** bind an opaque, trusted original-session identifier to the projected intent using an internal authority lookup or a protected issuer-side mapping. Do not expose `session_token_hash` or bearer credentials as external artifact fields. The issuer must authenticate the executor, establish that original-session link, sign or otherwise authenticate the complete envelope, and ensure effect-side admission enforces current authority atomically.

These new tests require maintainer-local validation; the last confirmed full-suite baseline remains **235/235** until reported otherwise. No B2 state, wire schema or real-effect path is changed by these tests.

## H. Decision and non-goals

**Decision:** keep `server/sec01_fencing_sqlite.py` and `server/sec01_fencing_sim.py` isolated; do **not** change `action_jobs` schema v4, B2 coordinator, dispatch path, or public MAP wire contracts on this design step.

**SEC-01 remains CRITICAL / OPEN.** This contract defines what must be designed and tested, not what current code already provides. Separate unresolved SEC-02/03/04/05/06/08/09 release gates still apply.
