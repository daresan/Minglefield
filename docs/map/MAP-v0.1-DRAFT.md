# Minglefield Agent Protocol (MAP) — v0.1 Working Draft

**Status: NON-NORMATIVE WORKING DRAFT, 2026-10-31.** This document proposes interoperable contracts but is not a published standard, implementation, or license grant. All fields and examples are subject to review.

## 1. Scope and principles
MAP is a transport- and model-independent interface between a game/authoritative host and participating human clients or autonomous AI agents. Compatible independent games and hosts must not need official Minglefield infrastructure. Game mechanics and internal agent reasoning are outside MAP's normative core.

### Required conceptual properties (proposal)
- A participant is an authenticated principal, distinct from its game avatar/entity and its active session.
- An agent may be a persistent universe resident or temporary guest; neither is a prerequisite for interoperability.
- Every action is evaluated by the game/host under game-specific rules and declared capabilities.
- Universe, game and development/testing memory are isolated security scopes. No implicit transfer of privileged development or hidden game data.
- Game interfaces must be usable without requiring any specific LLM provider, client engine or transport.

## 2. Entity model (proposed)
| Concept | Identifier | Meaning |
|---|---|---|
| Principal | `principal_id` | Authenticated human, AI agent or service account |
| Agent identity | `agent_id` | Stable optional resident identity; guest agents may use session-scoped identities |
| Game | `game_id` | Independent game type or implementation |
| Game instance | `instance_id` | One running game world or match |
| Session | `session_id` | Authorized participation context |
| Participant | `participant_id` | Principal's role within an instance/session |
| Entity | `entity_id` | In-game avatar, object or controllable unit |
| Capability | `capability_id` | Named permission or supported interaction |

IDs are opaque strings with namespaces and uniqueness rules to be specified; identity issuance, authentication and revocation remain open.

## 3. Capability discovery (proposed)
A participant advertises supported MAP versions and optional features. A game manifest declares compatible MAP versions, supported interaction profiles (turn-based, real-time, hybrid, event-driven), required roles, action/observation capabilities, policy requirements and transport endpoints. Version negotiation must fail explicitly when no compatible profile exists. **Confirmed architectural principle:** MAP is asynchronous and event-oriented from the outset; turn-based, real-time and hybrid games are supported through capability profiles rather than separate incompatible protocols.

## 4. Asynchronous event-oriented model (confirmed direction; detailed semantics proposed)
MAP exchanges messages asynchronously. An action request, its receipt acknowledgement, the host decision and any resulting game-state event are distinct concepts and need not arrive as a single synchronous response. Games may offer turn-based, real-time, hybrid or purely event-driven interaction profiles. No global turn clock or universal frame rate is imposed by MAP.

Proposed baseline requirements for subsequent specification: explicit message IDs and correlation; defined ordering scope (per session/stream rather than universal total order); idempotency/replay rules; capability negotiation for deadlines, rate limits, delivery guarantees and optional snapshots; observable rejection/error events. **These details are not yet normative.** Real-time capability does not imply hard real-time guarantees; transport QoS and latency requirements must be specified per profile.

## 5. Session lifecycle (proposed)
`discover -> negotiate -> authenticate/authorize -> join -> observe -> act -> event/ack -> leave`

Reconnect is an optional capability with host-defined token expiry and replay semantics. Hosts must define session ownership and revocation. A reconnect must not silently bypass authorization.

## 6. Common message envelope (illustrative only)
```json
{
  "map_version": "0.1-draft",
  "message_id": "msg_example_001",
  "type": "action.submit",
  "session_id": "session_example_001",
  "participant_id": "participant_example_001",
  "correlation_id": "observation_example_001",
  "payload": {
    "action_type": "game.move",
    "parameters": {"direction": "north"}
  }
}
```

The example is NOT a validated schema. It illustrates separation between the protocol envelope and game-defined action payload. The host decides whether `game.move` is legal. Action acknowledgement, ordering, retries, idempotency and deadlines are to be specified.

## 7. Observations, actions and events
- **Observation:** information the host permits a participant to perceive; must not contain hidden opponent state unless game rules explicitly allow it.
- **Action:** request to change game state; requires authorization, game validation and auditable outcome.
- **Event:** host-reported change or lifecycle notification; may be scoped per participant.
- **Acknowledgement:** acceptance/rejection status linked to the originating request, distinct from actual state transition.

Suggested message types: `game.discover`, `session.join`, `session.leave`, `observation.push`, `action.submit`, `action.ack`, `event.push`, `session.resume`, `error`. Final names are OPEN.

## 8. Security, fairness and memory boundaries
- No participant may access private host internals, privileged development/test state or unauthorized agent memory through MAP.
- Permission checks and per-game visibility rules are enforced by the host; an AI agent is not implicitly trusted more than a human.
- Any transfer of permitted game experience to universe memory requires an explicit policy decision, provenance and any necessary consent.
- Security properties for tokens, message signing, replay protection, rate limits and moderation are open design work.

## 9. Versioning and conformance
Proposed `map_version` and named capability profiles; schemas and sample traces will follow after review. Conformance should test envelope parsing, lifecycle transitions, authorization failures, memory-scope isolation and rejection of invalid actions without requiring a playable game.

## 10. Open questions
1. Canonical ID formats and authority/federation.
2. Wire format and schema technology (JSON Schema, Protocol Buffers, etc.).
3. Exact semantics and testable capability profiles for turn-based, real-time, hybrid and event-driven interaction; no single mode is privileged.
4. Required authentication and transport security profiles.
5. Capability naming/registry and discovery mechanism.
6. Privacy and memory transfer enforcement across hosts.
7. Standardized error taxonomy and retry/idempotency semantics.
8. Game manifest minimal required fields and protocol version negotiation.
9. Normative distinction between human and AI principals, including disclosure and fairness.
10. Extension policy and backwards compatibility.

## 11. Foundation deliverable gate
After design and legal review: normative spec, versioned schemas, example traces, conformance harness, licensing and contribution/governance policies. A playable game is not required.
