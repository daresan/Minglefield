# MAP conformance

**Initial draft schema validation script:** [validate_map_v01.py](validate_map_v01.py). It checks JSON Schema structure, action traces, game manifests, capability offers, deterministic negotiation cases and negative controls. GitHub Actions workflow: [.github/workflows/map-v01-conformance.yml](../../.github/workflows/map-v01-conformance.yml). Stateful conformance (authentication, deduplication, ordering, memory isolation) remains to be built. Run with Python 3.11+ and `jsonschema>=4.18`.

Shared-agent draft checks cover operator approval role, allowed/denied requester and scope, expiry, revocation and suspension. They are illustrative policy checks, **not** production-grade enforcement or proven emergency shutdown.

Run policy engine unit tests: `python -m unittest discover -s tests/conformance -p 'test_*.py' -v`. These tests exercise a runnable in-memory prototype; they do not prove production security.

SQLite v0.2 tests: `test_sqlite_policy_engine.py` covers restart persistence, concurrent budget reservations, duplicate operations and deny rules. The same unittest discovery command runs both engine suites.
