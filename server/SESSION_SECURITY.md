# MAP v0.3 — Local Identity and Session Security Prototype

**Experimental reference only. Not a production identity provider or network gateway.**

## Components
- [session_store.py](session_store.py): SQLite-persisted enrolled credentials and bearer sessions. Credentials and tokens generated with `secrets.token_urlsafe(32)`, stored only as SHA-256 hashes. Short-lived sessions bind a user, agent and optional delegation.
- [action_gateway.py](action_gateway.py): Resolves a bearer session into an authenticated user identity, checks agent/delegation binding and invokes [SQLite Policy Engine](sqlite_policy_engine.py) with a server-supplied UTC timestamp.
- [test_session_security.py](../tests/conformance/test_session_security.py): local tests for credentials, expiry, binding, revocation, account disabling, authorization and server-time checks.

## Windows verification
From repository root:
```powershell
git pull --ff-only
python -m unittest discover -s tests/conformance -p "test_*.py" -v
python tests/conformance/validate_map_v01.py
```

## Security boundary
The privileged `SessionStore.enroll()` bootstrap operation is **not** safe to expose to users. A real identity provider must establish legal/user identity and account ownership, protect enrollment and recovery, rate-limit authentication, and support MFA/credential rotation.

Session tokens are bearer secrets: transmit only over authenticated TLS, never log them, and protect them against theft. A token grants *identity proof*, not authorization. The gateway additionally checks policy grants and target/scope restrictions. `issue()` binds a session to a requested agent/delegation without verifying that relationship at issuance; policy enforcement at action time is mandatory.

Both stores can share a SQLite database file. The gateway verifies a session and then performs policy authorization in **separate transactions**, leaving a time-of-check/time-of-use window for revocation and suspension. No action is actually dispatched or cancelled here. A production dispatcher must enforce the final decision atomically or via a trusted runtime enforcement boundary, and recheck immediately before execution.

## Remaining risks

Phase A now compares the verified session's agent ID with the persistent
delegation's `grants.agent_id` inside the policy transaction, including retries.
Mismatch returns `agent_delegation_mismatch` before reservation. Session issuance
still accepts binding claims; it does not itself establish agent authority.
Session verification remains a separate transaction: revocation after verification
can still be followed by an allowed policy decision and budget reservation.
See [Phase A security regressions](PHASE_A_SECURITY.md) for executable reproductions
and the explicitly unresolved cross-delegation budget gap.
- No OAuth/OIDC, MFA, password-based authentication, signed identity claims, role-based enrollment, verified real-world identity, credential rotation or incident audit.
- No session-to-transport channel binding, anti-theft protections, rate limits, token refresh or session listing.
- Session revocation is durable but not an in-flight task kill; it only blocks later checks.
- No operator quorum, approval signatures, legal accountability verification, cross-host synchronization or real monetary billing.
- Clock is injectable for deterministic tests; in production it must be a trusted server clock and protected against time rollback.
- Session and policy records need a unified transactional action-dispatch boundary and production schema validation.
- AI agents are not legal persons by virtue of a session record.

## Roadmap
1. Verify tests on Windows and CI.
2. Implement trusted account/agent enrollment and delegated agent session issuance.
3. Design a single transactional authorization/dispatch boundary with cancellation checkpoints.
4. Add signed audit trail, multi-operator quorum, rate limiting and robust credential lifecycle.
5. Review privacy, liability and commercial operation with Austrian/EU counsel.
