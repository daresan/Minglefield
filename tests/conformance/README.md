# MAP conformance

**Initial draft schema validation script:** [validate_map_v01.py](validate_map_v01.py). It checks JSON Schema structure, action traces, game manifests, capability offers, deterministic negotiation cases and negative controls. GitHub Actions workflow: [.github/workflows/map-v01-conformance.yml](../../.github/workflows/map-v01-conformance.yml). Stateful conformance (authentication, deduplication, ordering, memory isolation) remains to be built. Run with Python 3.11+ and `jsonschema>=4.18`.

Shared-agent draft checks cover operator approval role, allowed/denied requester and scope, expiry, revocation and suspension. They are illustrative policy checks, **not** production-grade enforcement or proven emergency shutdown.

Run policy engine unit tests: `python -m unittest discover -s tests/conformance -p 'test_*.py' -v`. These tests exercise a runnable in-memory prototype; they do not prove production security.

SQLite v0.2 tests: `test_sqlite_policy_engine.py` covers restart persistence, concurrent budget reservations, duplicate operations and deny rules. The same unittest discovery command runs both engine suites.

Session v0.3 tests: `test_session_security.py` covers token verification, expiry, binding, durable revocation and policy gateway integration. Unittest discovery includes this module.

Phase A: `test_phase_a_regressions.py` covers persistent agent binding and input
validation. It also contains **three expected failures for unresolved P1 risks**:
session revocation between transactions and aggregate agent budgets in both engines.
See [the security record](../../server/PHASE_A_SECURITY.md). Report these known
failures explicitly even when unittest exits successfully.

B1: `test_action_submission.py` verifies the new atomic submission path separately
from legacy APIs. See [the B1 contract](../../server/ACTION_SUBMISSION.md) for migration,
accounting, canonicalization and security boundaries. No test executes external actions.
