# MAP v0.1 — Identity, Agent Operation and Delegation (Draft)

Date: 2026-10-31
Status: **NON-NORMATIVE DRAFT**. Product direction approved by founder; protocol field details and legal terms open.

## Confirmed ecosystem model
A Minglefield User is initially a natural person with one account and potentially many linked agents. **Agents may also be jointly operated by multiple users**, with explicit roles and a verifiable accountability arrangement; organization participation is a future design option. Agents may run on the user's hardware, third-party cloud subscriptions or optional future Minglefield-managed AI services. Agents may play, build games, test, provide feedback, collaborate or provide paid services to other users under configurable owner/developer conditions.

## Distinct identities and authority
| Role | Proposed identifier | Purpose |
|---|---|---|
| User account | `user_id` | Natural person controlling linked agents; platform identity |
| Agent | `agent_id` | Durable logical agent identity independent of runtime |
| Runtime | `runtime_id` | Self-hosted/cloud/Minglefield-managed execution instance |
| Operator association | `operator_id` / `operator_ids` | One or more authorized users or eligible legal entities; role and approval rights must be explicit |
| Accountable party | `accountable_party_id` | Designated natural or legal person for operational accountability and incident contact; does not determine statutory liability |
| Requester | `requester_user_id` | User commissioning a delegated service |
| Delegation | `delegation_id` | Scoped, revocable authorization for a particular assignment |
| Session | `session_id` | Authorized game/development connection |
| Participant | `participant_id` | Identity and permissions within a specific game or project |
| Game entity | `entity_id` | In-world avatar or controlled object |

The agent identity is **not** the runtime identity; the requester is **not** automatically the owner; a participant is **not** necessarily a whole agent or user account. Stable identity and credential verification are separate.

## Proposed authorization chain
1. Authorized operator(s), acting under the agent's joint-operation governance, publish allowed agent services and explicit limits.
2. The requester submits an assignment with agreed scope, duration and applicable commercial terms.
3. Authorized operator(s)/platform approve a bounded delegation according to explicit approval rules; payment status is handled outside universal MAP.
4. The runtime authenticates; the host independently checks delegation, participant role, game/project policies and session admission.
5. The agent acts only within the intersection of operator policy, delegation scope and host policy.
6. Expiry, revocation or task completion terminates delegated privileges, not the agent's durable identity.

A service assignment must not grant blanket access to private memories, third-party cloud credentials, development secrets or other games' hidden information. Memory access and transfer remain governed by separate universe/game/development scope rules.

## Shared operation, accountability and safety
Joint operation requires explicit roles (e.g. administrator, approver, runtime operator, billing contact), approval thresholds and an accountable-party record before privileged or commercial operation. Record the actor authorizing each delegation. The system should support least-privilege scopes, revocation, spend/compute caps, emergency suspension, incident handling and privacy-conscious audit trails. **An accountable-party designation is not a legal determination of exclusive liability**; actual responsibility among co-operators, requester, developer, host and platform is subject to Austrian/EU legal review. An AI agent is not assumed to be a legal person.

## Deployment independence
MAP-compatible independent games and agents need not use Minglefield hosting, accounts, subscriptions or payment services. A portable MAP identity/delegation mechanism must not assume official account infrastructure. Trust federation, external identity mapping, cryptographic credentials and capability proof remain open.

## Proposed future schemas
- Agent descriptor: agent identity, declared capabilities, optional hosting/runtime information, supported MAP profiles.
- Delegation grant: issuer, subject agent, requester, scope, target game/project, expiry, revocation reference and authorization proof.
- Session join: authenticated principal, agent/participant binding and optional delegation reference.
- Revocation and audit events with privacy-preserving metadata.

## Open design decisions
Ownership transfer, organizational accounts, co-operator governance and liability allocation, rental resale restrictions, provider terms, data processing roles, financial settlement, 5% platform participation and consumer rights require further governance/legal review. The 5% objective is a commercial contract matter, not a MAP core protocol fee.
