# MAP action execution preparation — Phase A

Status: experimental reference hardening, 2026-10-31. No v0.4 executor is implemented.
MAP v0.1 wire schemas and protocol semantics are unchanged.

## Fixed and covered

- The gateway passes the verified session agent to SQLite authorization. The
  persistent delegation agent must match, including on an idempotent retry.
  Tests cover both an unregistered claimed agent and another registered agent,
  reopening the policy store, and absence of reservation on rejection.
- Both engines reject absent/empty operation IDs for positive costs with
  `operation_id_required`. The in-memory engine now uses SQLite's existing falsy-ID
  check. Nonnegative integer cost validation remains unchanged; booleans, floats,
  strings, null, containers and negative costs are regression-tested.
- Zero-cost optional/empty IDs retain their existing behavior. No new operation-ID
  type/format contract is introduced. Callers still validate inputs; this is not
  comprehensive runtime schema validation.
- Push and pull-request workflow filters now include `server/**` as well as
  `tests/conformance/**`.

Tests: `tests/conformance/test_phase_a_regressions.py`.

## Explicitly unresolved P1 reproductions

Three tests use `unittest.expectedFailure` and assert the desired safe behavior.
They are known failures, not evidence of a fix. If the property starts passing,
unittest reports an unexpected success and fails the run, requiring marker review.

1. `test_known_p1_revocation_between_verify_and_policy_must_deny` inserts an
   authenticated token revocation immediately after the real session verification
   commits, before the policy transaction. This deterministic interleaving needs
   no timing sleeps. The token is demonstrably revoked, but authorization still
   succeeds and reserves budget. A shared submission transaction is deferred.
2. `test_known_p1_sqlite_agent_budget_must_cover_all_grants` submits six distinct
   grants at 200 units each against the example agent cap of 1,000. Persistent
   reservations total 1,200. Per-grant checks do not enforce an aggregate cap.
3. `test_known_p1_memory_agent_budget_must_cover_all_grants` reproduces the same
   budget gap in the in-memory reference. Agent-wide accounting is deferred.

Other unresolved boundaries: trusted enrollment is a caller responsibility;
`verified_actor` is not authentication; direct policy timestamps are caller-supplied;
there is no job queue, external-effect idempotency, execution audit, runtime
cancellation or atomic authorization/dispatch. Positive policy decisions must not
be advertised as safe exactly-once execution. Session revocation is not process stop.

## Local verification

From the public repository root, use Python 3.11+:

```text
python -B -m unittest discover -s tests/conformance -p 'test_*.py' -v
python -B tests/conformance/validate_map_v01.py
```

The original 24 tests must remain successful. Phase A adds five passing regression
tests and three explicit expected failures: 32 tests total, 29 passes and three
known failures. A green process exit must always be reported with this qualification.

Verified locally on Windows on 2026-10-31:

- Unittest: **32 tests, 29 passed, 3 expected failures**, exit code 0. All original
  24 tests passed. SQLite tests ran outside the restricted sandbox because its
  temporary-directory access failed during baseline verification.
- Schema validator: **PASS**, 13 schemas, 6 action trace messages, 5 negotiation
  cases, 3 baseline negative controls and shared-agent authorization checks.
- Workflow inspection: both event blocks contain `server/**` and
  `tests/conformance/**`; local path-matching checks passed for the gateway,
  SQLite policy engine and new regression module on both push and pull request
  (six checks). No remote GitHub Actions run was triggered or verified.
- `git diff --check` passed. Wire schemas and example traces have no changes.
- Environment: Python 3.11.15, SQLite 3.53.1, jsonschema 4.26.0 and referencing
  0.37.0. CI pins jsonschema 4.23.0; exact dependency parity was not tested.
