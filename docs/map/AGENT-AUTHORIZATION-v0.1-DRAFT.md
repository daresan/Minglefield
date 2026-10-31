# MAP v0.1 — Shared Agent Authorization and Emergency Controls (Draft)

Date: 2026-10-31. **NON-NORMATIVE DESIGN AND SCHEMA DRAFT.** Product direction: multiple operators, accountable-party arrangement, scoped delegation, revocation and emergency suspension confirmed. Exact field names, authorization semantics and legal responsibility require further review.

## Draft records
- [Agent descriptor](../../schemas/map/v0.1/agent-descriptor.schema.json): durable agent identity; multiple operators with roles; designated accountable party; active/suspended state; revision and optional limits.
- [Delegation grant](../../schemas/map/v0.1/delegation-grant.schema.json): bounded service authorization identifying agent, issuer, requester, scopes, issue/expiry, target and approval reference.
- [Delegation revocation](../../schemas/map/v0.1/delegation-revocation.schema.json): auditable revocation instruction.
- [Agent suspension](../../schemas/map/v0.1/agent-suspension.schema.json): suspend/resume control instruction.

These are **record schemas**, not yet MAP wire-envelope message types. Their transport binding, signatures, authentication and event acknowledgements remain open. The accountable party record does not establish exclusive statutory liability.

## Proposed enforcement rules
1. Bind authenticated operator identities to agent role assignments; require explicit approval authority for grants. A requester is never automatically an operator.
2. Grant authorization only for the intersection of operator policy, grant scopes, requester identity, target, time window and host policy.
3. Treat grant issuer and agent operator records as **claims to verify** against a trusted identity/authorization service. JSON Schema alone cannot establish authority.
4. Deny on expired, revoked, malformed or ambiguous grants; no privilege on an unknown role, target or capability.
5. Check revocation and suspension **at action dispatch** and at defined execution checkpoints. Immediately block new work after an authenticated suspension; attempt to cancel in-flight work and report any non-reversible effects.
6. Protect memory scopes and secrets: a delegated task must not access private universe, game, development or operator credentials without separate explicit authorization.
7. Enforce compute/spend limits, concurrency limits and approved action classes at a trusted host/runtime boundary, not merely inside the agent prompt.
8. Log actor, authorization decision, policy revision and incident actions with proportionate privacy controls. Implement replay protection and authenticated command ordering before production use.
9. Resuming a suspended agent requires a fresh authorization check; resumption does not automatically restore revoked grants.
10. Define incident escalation and operational contacts; counsel must review liability, insurance, cross-border and regulatory obligations.

## Test coverage
[Local conformance smoke tests](../../tests/conformance/validate_map_v01.py) validate four record schemas and illustrative allowed/denied access scenarios (wrong requester, wrong scope, expired, revoked, suspended). They do **not** implement a real policy decision point, cryptographic verification, persistence, cancellation or actual emergency stop.

## Unresolved design decisions
- Multi-operator approval thresholds, conflicting operator commands and role changes.
- Whether organizations can be operators/accountable parties; legal entity verification.
- Binding accountable-party IDs to verified legal identities while protecting private information.
- Revision, revocation propagation latency, offline runtimes, audit integrity and emergency-stop guarantees.
- Formal identity/delegation session wire messages, token formats and issuer trust.
- Monetary limits currency/units, commercial settlement, service contracts and provider resale restrictions.
- Real-world harm response, insurance, GDPR and EU/Austrian legal classification.

See [identity and delegation](IDENTITY-DELEGATION-v0.1-DRAFT.md) and [message model](MESSAGE-MODEL-v0.1-DRAFT.md).

## Executable prototype

The first [Python Policy Engine prototype](../../server/POLICY_ENGINE.md) now implements local decision checks, scoped grants, spending limits, revocation and suspension, with unit tests. It is **not** an authenticated, durable or distributed enforcement service.
