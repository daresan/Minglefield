# MAP Policy Engine — v0.1 experimental reference

Status: **executable prototype, not production authorization**.

Implementation: [policy_engine.py](policy_engine.py). Tests: [test_policy_engine.py](../tests/conformance/test_policy_engine.py).

## Run
Python 3.11+, standard library only for policy engine and unit tests:

```bash
python -m unittest discover -s tests/conformance -p 'test_*.py' -v
```

Schema validation separately requires `jsonschema==4.23.0`:

```bash
python tests/conformance/validate_map_v01.py
```

GitHub Actions runs both commands on changes to the relevant directories.

## Capabilities
- Approver-only grant registration, restricted to configured agent scopes.
- Verified-requester, scope, target and time-bound action checks.
- Cumulative in-memory spending caps with idempotent operation IDs and conflict rejection.
- Requester/operator grant revocation.
- Authorized agent suspension and administrator resumption.
- Fail-closed decision reasons and a per-process lock around state changes.

## Critical limitations
- The caller supplies *verified* identities; this prototype **does not authenticate** users or validate cryptographic delegation grants.
- Input must be validated against MAP schemas **before** entering the engine; it trusts the agent/grant record shape.
- Policy and state are in memory. Restarts lose grants, revocations, suspension state, spending totals and operation deduplication. It is not safe for multi-process or distributed use.
- Budget checks reserve illustrative cost units; they do not charge money or support actual currency accounting.
- Suspension blocks future policy checks but **does not terminate in-flight tasks**. A real emergency stop needs trusted runtime enforcement, cancellation, watchdogs and offline handling.
- The engine does not yet enforce multi-operator approval quorum, policy revisions, host policies, concurrency, memory scope access or accountable-party verification.
- Approval and grant records are not signed. No audit log or incident response integration exists.
- Legal liability is not determined by this code.

## Security implementation gates
Trusted identity and signed grants; durable transactional state; replay/expiry enforcement; distributed revocation and runtime stop; multi-operator quorum and conflict resolution; host-side policy enforcement; auditable decision trail; penetration/security testing and Austrian/EU legal review.
