# MAP v0.1 — Message Envelope and Processing Rules (Draft)

Status: **technical draft**, 2026-10-31. The founder has **confirmed JSON as the reference encoding with interchangeable encodings**. Field details and guarantees below are proposals pending review, conformance testing and legal clearance. No published license yet.

## 1. Logical message model
MAP defines logical messages independent of transport and encoding. JSON is the v0.1 reference representation. A different codec must preserve field names/semantics, scalar types, identifiers, ordering metadata and payload meaning. A non-JSON codec is **not automatically conformant**: interoperability requires a declared codec profile, canonical mapping and conformance vectors. No mandatory binary codec in v0.1.

### Envelope fields
| Field | Requirement | Meaning |
|---|---|---|
| `map_version` | required | Semantic protocol version; draft schema accepts `0.1` |
| `message_id` | required | Unique within the sender's authority; duplicate detection scope to be defined |
| `type` | required | Namespaced logical message type |
| `sent_at` | required | RFC3339 UTC instant for diagnostics; never the authoritative ordering source |
| `source` | required | Sender kind and opaque identifier; not proof of identity |
| `payload` | required | Message-type-specific object |
| `target` | optional | Addressed endpoint; transport may route independently |
| `session_id` | conditional | Required for session-scoped actions, acknowledgements, observations and events in initial schemas |
| `participant_id` | conditional | Required for action submit and participant-specific observations |
| `stream_id` | conditional | Required for streamed events and observations |
| `sequence` | conditional | Nonnegative stream-local monotonic number assigned by the stream authority |
| `correlation_id` | conditional | References the original request; required for acknowledgements/errors |
| `causation_id` | optional | Immediate causal predecessor; not necessarily a client request |
| `idempotency_key` | conditional | Required for action submission; identifies a retryable logical operation |
| `expires_at` | optional | Request expiry; host must enforce when negotiated |
| `trace_id` | optional | Diagnostics only, not a permission token |
| `extensions` | optional | Namespaced extensions; unknown noncritical extensions ignored, critical negotiation TBD |

All identifiers are opaque strings. No identifier, timestamp, `source` value or trace field alone confers authorization. The reference schema deliberately rejects unknown **top-level** fields; extensions belong in `extensions`. Schemas permit game-defined objects inside relevant payloads.

## 2. Message families in initial schemas
- `action.submit`: agent/client intent; does **not** guarantee execution.
- `action.ack`: `receipt/received`, `decision/accepted|rejected`, `execution/succeeded|failed`. Each phase is independent. Acceptance is not success.
- `event.push`: host-reported occurrence, with stream-local `sequence` and visibility constraints.
- `observation.push`: participant-specific authorized view; no unrestricted world state.
- `protocol.error`: protocol-level failure with stable code and `retryable` flag.

Further lifecycle messages (`session.join`, `session.resume`, manifest discovery and capability negotiation) are reserved for later schemas; they are **not** validated by the initial message-family schemas.

## 3. Processing rules (draft)
1. Parse and validate the envelope, negotiated codec/profile and message-type schema; reject malformed or unsupported messages without applying game effects.
2. Authenticate the actual transport/session principal and authorize source, session, participant, action and target. Do not trust `source` as an identity assertion.
3. Check expiry, replay, idempotency and rate limits before dispatch.
4. For action submission, the host may send a receipt acknowledgement; this indicates **receipt only**. A later decision may reject the action. A successful execution result is distinct.
5. The host controls game-state mutation, authoritative event creation and participant-specific observation filtering.
6. Within one authoritative stream, `sequence` strictly increases for newly emitted items; gaps can indicate loss or filtering and must not be interpreted as proof of tampering. No total order across streams is promised.
7. Clients correlate acknowledgements by `correlation_id` and events by `causation_id` where present. Neither field guarantees event delivery.
8. Retrying an action with the **same idempotency key** and the same authenticated actor/session must not apply its side effects twice during the host's declared deduplication window. The host must reject reuse with different payload; deduplication window and persistence guarantees remain to be specified.
9. No exactly-once delivery claim. A transport may deliver duplicates, out-of-order or late messages. Reconnect, snapshot, replay, backpressure and ordering QoS require negotiated profiles.
10. Errors must not leak restricted game state, privileged developer information or another participant's memory.
11. Timestamps are for diagnostics and optional deadline evaluation only; they do not supersede stream sequence and authoritative host decisions.
12. Real-time support means an appropriate profile can be negotiated, **not** guaranteed hard real-time performance.

## 4. Schema validation scope
The base envelope schema checks syntax and simple constraints. Specialized schemas check five initial message families. JSON Schema **cannot alone** prove authentication, time validity, global uniqueness, replay protection, sequence monotonicity, memory isolation or successful host authorization. Those require stateful conformance tests.

Schema URLs and relative `$ref` are currently repository-local draft identifiers, not a stable deployed schema registry.

## 5. Examples and validation
- [JSON Schema directory](../../schemas/map/v0.1/)
- [Sample asynchronous trace](../../examples/map/v0.1/async-action-trace.json)
- [Local validation script](../../tests/conformance/validate_map_v01.py)

Run with Python 3.11+ and `pip install jsonschema>=4.18`:
```bash
python tests/conformance/validate_map_v01.py
```

## 6. Remaining design decisions
- Full session/discovery/capability schemas and negotiation failure rules.
- Required/optional semantics for `target`, `expires_at`, `trace_id` and extensions.
- Identifier scope, exact idempotency retention, stream replay and snapshot rules.
- Codec registry, canonical mapping and security constraints for alternate encodings.
- Error taxonomy, access-control binding, participant-scoped sequence visibility.
- JSON Schema validation format requirements and compatibility across validators.
- Security profiles, transport authentication, timeouts, flow control and federated authority.

**Approval boundary:** JSON as reference with interchangeable encodings is confirmed; these exact fields and processing semantics remain reviewable draft proposals.
