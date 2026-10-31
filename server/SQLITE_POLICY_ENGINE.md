# MAP v0.2 — SQLite Policy Engine (experimental)

This is a **local, transactional reference prototype**, not an authenticated production authorization service.

- Implementation: [sqlite_policy_engine.py](sqlite_policy_engine.py)
- Tests: [test_sqlite_policy_engine.py](../tests/conformance/test_sqlite_policy_engine.py)
- Previous in-memory reference: [policy_engine.py](policy_engine.py)

## Run on Windows PowerShell

From repository root:

```powershell
python -m unittest discover -s tests/conformance -p "test_*.py" -v
python tests/conformance/validate_map_v01.py
```

Uses only Python standard-library `sqlite3` for storage. JSON Schema validation uses the separately installed `jsonschema` dependency.

## Persistence and concurrency

`SQLitePolicyEngine(database_path)` creates three SQLite tables: agents, grants and operations. Every mutation and authorization decision runs inside a `BEGIN IMMEDIATE` transaction, serializing competing writers to the same database file. This prevents concurrent reservations from exceeding the same grant's spend limit within the SQLite file. Operation IDs are unique per delegation, with a stored fingerprint to distinguish retries from conflicting replays. Revocation and suspension persist across restarts.

Example:

```python
from server.sqlite_policy_engine import SQLitePolicyEngine
# When run from repo root, first add server/ to sys.path, or use
# PYTHONPATH=server and import sqlite_policy_engine instead.
```

The class expects *schema-validated* agent/grant dictionaries and *authenticated* `verified_actor` / `verified_requester` identities supplied by a trusted caller.

## Explicit limitations

- No cryptographic authentication, token validation, verified legal identities or real multi-operator approval quorum.
- No distributed policy enforcement; SQLite is suitable for one host and one shared local database file, **not** multiple independently replicated runtimes.
- No actual process cancellation. Suspension prevents subsequent authorization decisions only; in-flight actions must be stopped by a separate trusted runtime.
- No billing: `cost_minor` is an illustrative integer reservation, not a payment transaction or currency-aware ledger. A failed downstream task does not automatically refund a reservation.
- No signed audit trail, migrations, database backup/restore policy, key rotation, rate limits, or external host-policy enforcement.
- Input record schema validation is **not** performed inside the engine. Invalid/untrusted data must be rejected before it reaches this code.
- Authorization decisions are time-bounded only against the **caller-supplied** `at` value; a production implementation must use a trusted server clock and enforce monotonic/replay-safe semantics.
- Role and policy changes are not implemented; operator roles in the stored descriptor remain static.
- No automatic expiry cleanup, and no live session admission or action dispatch integration.

## Next security gate

Add trusted identity/session binding, server-controlled time, explicit operator approval governance, durable audit log and runtime-enforced cancellation. Verify the GitHub Actions run before claiming CI success.
