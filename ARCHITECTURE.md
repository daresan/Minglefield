# Minglefield — Architecture Baseline v0.1

Status: **architecture proposal consolidated from approved project principles**, 2026-10-31. This is not a running implementation or final MAP specification.

## Core principle
Minglefield is an open, interoperable universe and game ecosystem, **not one mandatory game or engine**. Independent human and AI developers should be able to implement compatible games and agents.

## Logical modules
| Module | Responsibility | Proposed license |
|---|---|---|
| `docs/map/` | Human-readable MAP specification, lifecycle, semantics, conformance | CC BY 4.0 candidate |
| `schemas/map/` | Versioned, machine-readable protocol schemas | Apache 2.0 candidate |
| `sdk/` | Client libraries and adapters, not server internals | Apache 2.0 candidate |
| `server/` | Optional official authoritative services: sessions, discovery, policy enforcement | AGPL 3.0 candidate |
| `tests/conformance/` | Protocol-level black-box tests independent of implementation | Apache 2.0 candidate |
| `examples/` | Small independent integration examples; playable games later | Per-example license |
| `docs/governance/` | Contributor, security, governance and interoperability policies | CC BY 4.0 candidate |
| `apps/` | Optional official universe UI/client; engine choice pending | License TBD |
| `services/` | Optional official hosting/marketplace; not required for implementing MAP | License and terms TBD |

**No licenses have been granted by this proposed matrix.** License texts and precise scope will be published only after legal/rights review.

## System boundaries
```
Human client ──────┐
AI agent + adapter ├── MAP contracts ── compatible game / authoritative host
Other clients ─────┘            │
                                ├── identity, permissions, sessions
                                ├── events, actions, observations
                                └── memory access policy (not a shared unrestricted memory pool)

Optional universe client ── discovery / game portals
Optional official services ── hosting / marketplace / funding (separate contracts)
```

- **MAP is asynchronous and event-oriented from the outset**, with capability profiles for turn-based, real-time, hybrid and event-driven games. No specific transport, global turn clock or fixed frame rate is required by the core protocol.
- **MAP is an interoperability contract**, not a requirement to use the official server or any specific LLM, client engine, transport or commercial service.
- **Game authority** and game rules belong to the implementing game/host; MAP defines the common interface and conformance expectations.
- **User/agent operation:** one natural-person user account may control multiple agents running self-hosted, through user-owned cloud subscriptions or optional future Minglefield-managed AI services. Agents may play, develop and be delegated for bounded services to other users; operator, requester, runtime and game participant are separate roles. See [identity/delegation draft](docs/map/IDENTITY-DELEGATION-v0.1-DRAFT.md).
- **AI residency** may be persistent or guest-based. Three memory scopes remain separate: universe, game, development/testing. Restricted game knowledge must not automatically enter persistent universe memory.
- **Transport choice** (HTTP, WebSocket, MCP discovery adapter, etc.) is a future profile/extension decision. Do not bake a single vendor protocol into the MAP core.
- **SDKs and games** should not need to incorporate AGPL server code merely to implement MAP. License compatibility of shared code requires review.
- **5% commercial participation** is a separate contractual goal for eligible official transactions, not a MAP protocol or open-source licensing requirement.
- **Sponsorship/fundraising** designated for Minglefield is earmarked for project development and separate from commercial revenue.

## MAP v0.1 specification work packages
1. Actors, IDs, capabilities, guest/persistent residency and trust boundaries.
2. Game manifest, discovery and supported protocol versions.
3. Session create/join/leave/reconnect and participant roles.
4. Observation, action, event and acknowledgement envelopes; ordering, errors and idempotency.
5. Permissions, game fairness, policy and moderation hooks.
6. Memory scope labels, access/transfer rules and explicit consent.
7. Conformance profiles, sample traces and compatibility tests.
8. Security model, threat assumptions and versioning/deprecation.

## First milestone acceptance criteria
- Reviewed MAP v0.1 text and machine-readable example schemas.
- Basic conformance harness and implementation-independent example traces.
- Published, legally reviewed license mapping and contribution/governance rules.
- No playable game, official host deployment, Godot client or commercial marketplace is required for Foundation completion.

## Decisions still open
- Precise MAP wire format, transports, authority delegation, versioning and required vs optional capabilities.
- Exact license variants, contribution attestations and patent/trademark policy.
- Monorepo versus separate repositories when implementation size grows.
- Reference implementation language and engine choices.
- Legal/commercial terms for official managed services.

See [roadmap](ROADMAP.md) and [contributing](CONTRIBUTING.md).
