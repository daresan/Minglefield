# MAP v0.1 — Identity, Agent Operation and Delegation (Draft)

Date: 2026-10-31
Status: **NON-NORMATIVE DRAFT**. Product direction approved by founder; protocol field details and legal terms open.

## Confirmed ecosystem model
A Minglefield User is initially a natural person with one account and potentially many linked agents. Agents may run on the user's hardware, third-party cloud subscriptions or optional future Minglefield-managed AI services. Agents may play, build games, test, provide feedback, collaborate or provide paid services to other users under configurable owner/developer conditions.

## Distinct identities and authority
| Role | Proposed identifier | Purpose |
|---|---|---|
| User account | `user_id` | Natural person controlling linked agents; platform identity |
| Agent | `agent_id` | Durable logical agent identity independent of runtime |
| Runtime | `runtime_id` | Self-hosted/cloud/Minglefield-managed execution instance |
| Owner/operator | `operator_user_id` | User authorizing the agent's behavior and service terms |
| Requester | `requester_user_id` | User commissioning a delegated service |
| Delegation | `delegation_id` | Scoped, revocable authorization for a particular assignment |
| Session | `session_id` | Authorized game/development connection |
| Participant | `participant_id` | Identity and permissions within a specific game or project |
| Game entity | `entity_id` | In-world avatar or controlled object |

The agent identity is **not** the runtime identity; the requester is **not** automatically the owner; a participant is **not** necessarily a whole agent or user account. Stable identity and credential verification are separate.

## Proposed authorization chain
1. The owner publishes allowed agent services and explicit limits.
2. The requester submits an assignment with agreed scope, duration and applicable commercial terms.
3. The owner/platform authorizes a bounded delegation; payment status is handled outside universal MAP.
4. The runtime authenticates; the host independently checks delegation, participant role, game/project policies and session admission.
5. The agent acts only within the intersection of owner permission, delegation scope and host policy.
6. Expiry, revocation or task completion terminates delegated privileges, not the agent's durable identity.

A service assignment must not grant blanket access to private memories, third-party cloud credentials, development secrets or other games' hidden information. Memory access and transfer remain governed by separate universe/game/development scope rules.

## Deployment independence
MAP-compatible independent games and agents need not use Minglefield hosting, accounts, subscriptions or payment services. A portable MAP identity/delegation mechanism must not assume official account infrastructure. Trust federation, external identity mapping, cryptographic credentials and capability proof remain open.

## Proposed future schemas
- Agent descriptor: agent identity, declared capabilities, optional hosting/runtime information, supported MAP profiles.
- Delegation grant: issuer, subject agent, requester, scope, target game/project, expiry, revocation reference and authorization proof.
- Session join: authenticated principal, agent/participant binding and optional delegation reference.
- Revocation and audit events with privacy-preserving metadata.

## Open design decisions
Ownership transfer, organizational accounts, multiple operators, rental resale restrictions, provider terms, data processing roles, financial settlement, 5% platform participation and consumer rights require further governance/legal review. The 5% objective is a commercial contract matter, not a MAP core protocol fee.
