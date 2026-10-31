# Optional Minglefield server core

**Experimental reference implementations are available** for policy decisions, SQLite persistence, local bearer sessions and atomic queued-job submission. There is no production server, action executor or runtime cancellation yet. Discovery and reference hosting remain planned. Compatible independent hosts are permitted.

Candidate license: AGPL 3.0; exact variant and dependency boundaries pending legal review.

## Experimental policy engine

[MAP Policy Engine prototype and usage](POLICY_ENGINE.md) implements an in-memory policy decision point with tests. It is not a production authorization service.

## SQLite-backed v0.2 prototype

[SQLite policy engine](SQLITE_POLICY_ENGINE.md) adds durable local state and transactional concurrency tests. Authentication and real runtime cancellation remain future work.

## Identity and session prototype v0.3

[Session security and authenticated gateway](SESSION_SECURITY.md) binds bearer sessions to user, agent and delegation and uses server time. Experimental, not production identity or dispatch.

## Atomic submission B1

[ActionService and its security/accounting contract](ACTION_SUBMISSION.md) add a
single-transaction submit path, persistent queued jobs, audit events and aggregate
agent budgets. Legacy APIs retain their documented limitations. No execution exists.
