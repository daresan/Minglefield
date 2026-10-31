# Scalability and interoperability — architectural direction

**Status:** design guidance, not a claim that the described services are implemented. This document records the direction for future Minglefield development while MAP and the B1 reference remain experimental.

## Preserve MAP as an open boundary

MAP uses versioned JSON messages and JSON Schema to maximize portability across languages, operating systems, model providers and agent frameworks. JSON is the **wire contract**, not a mandate to use JSON for internal queues, databases, caches, or inter-service transport. A binary or streaming transport may be introduced later only with explicit negotiation and interoperability tests. Do not silently change the published MAP v0.1 schema.

## Current reference implementation

The B1 `ActionService` is a single-host Python/SQLite reference. It atomically validates a submission, reserves budgets and stores one queued job and audit event using `BEGIN IMMEDIATE`. SQLite's writer lock serializes submissions: correctness is tested for local concurrency, **not** distributed throughput. B1 does not run jobs or guarantee execution, retries, refunds or cancellation.

The canonical parameters are serialized with sorted keys, compact separators and `ensure_ascii=True`. The 65,536-character limit is therefore also a 65,536-byte limit **for this ASCII-escaped representation**. It is not a general raw-JSON or Unicode-character limit. This is a Python reference canonicalization rule, not RFC 8785; other implementations need conformance vectors before interoperable fingerprinting.

## Recommended evolution (proposed, not scheduled)

1. **B1 hardening:** document and test parameter-size boundaries, nesting, malformed values, idempotency, transaction rollback, and denial without side effects.
2. **B2 worker lifecycle:** define durable states, leases, fencing, retry/recovery semantics and permission revalidation before external effects. Submission and execution must remain separate.
3. **Future database backend:** retain SQLite for local reference/tests and evaluate PostgreSQL for multi-instance transaction processing. Preserve invariant tests across backends. Database migration is not a simple driver swap.
4. **Load-test before rewriting:** measure throughput, p95/p99 latency, lock contention, job backlog, recovery, and budget correctness under concurrency. Move selected hot paths to Go/Rust only with measured evidence.

Queue technologies, hosting topology, service discovery, authentication providers, quotas and production SLOs remain undecided.

## Scale without weakening safety

- Server-derived identity, scope, price and time; never trust client overrides.
- Atomic idempotency, grant and agent budget reservations across concurrent writers.
- Durable auditability and clear crash/recovery semantics.
- Revocation must be rechecked before worker execution; B1 queueing is not permission to execute later.
- Explicit request limits and bounded resource use before database lock acquisition.
- Versioned schemas, cross-language canonicalization vectors and negative tests.

## Agent-friendly ecosystem

A contributor should be able to point a coding agent at the public repository to discover its mission, contribution boundaries, current status, tasks, validation commands and MAP contracts. [AGENTS.md](../AGENTS.md) provides that starting point. This is **discovery**, not automatic authorization or runtime participation. A future agent onboarding flow will need documented identity, capabilities, consent/delegation, game discovery, sandboxing and audit contracts.

## Open questions

- Should 64 KiB be a stable MAP transport constraint or remain a B1 implementation limit? **Currently B1 only.**
- How should cross-language canonicalization and duplicate JSON object keys be handled at ingress?
- What are acceptable payload nesting depth, admission cost and rate limits?
- What storage/worker guarantees are needed for distributed execution?
- What contributor license and governance process will permit outside agent-authored code and assets?
