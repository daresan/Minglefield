# Minglefield Private Alpha — zero-budget pilot plan (draft)

Status: **planning only, not deployed or production-approved**. This does not authorize external effects under the existing SEC-01–SEC-09 B2 release gates. Branch: `wip/map-v04-security-hardening`.

## Goal and audience

A small, personally invited pilot where nonprofessional/hobby-vibe-coder users can sign in, register and manage their own agents, grant narrowly scoped actions, see job outcomes, and provide feedback. The maintainer hosts the service and optionally controlled ComfyUI workloads on their own Windows/GPU host. A second computer on a separate network is available for independent external-network testing. Maintain private pilot credentials and data **outside the public repository**.

The existing public README explicitly states foundation status: no playable release, production SDK, public registration or marketplace. This plan does not relabel existing B2 simulation as a production backend.

## Access recommendation

**Stage 0 (private integration):** local HTTP loopback + Tailscale Serve, updated client and restrictive tailnet policy. Tailscale Funnel is **public internet exposure**, not an invitation or authentication control. Never publish ComfyUI, SQLite files, development servers, debugging endpoints or administrator ports with Funnel.

**Stage 1 (invited web alpha):** Cloudflare Tunnel + Cloudflare Access (or equivalent managed identity-gated edge), an allowlist of invited testers, plus independent **Minglefield application authentication/authorization**. Requires a compatible domain and attention to provider quotas/terms; no provider is a substitute for secure application authorization. Cloudflare Free Access capacity and Tailscale plans must be rechecked before deployment. A public hostname behind Access must expose only a purpose-built API/UI gateway.

Tailscale security bulletins as of 2026-11-01 include 2026 Serve/Funnel and SSH fixes. Patch to an appropriate current release, disable unnecessary Serve/SSH/funneling features and avoid relying on forwarded headers for principal identity unless verified by a trusted ingress. Apply host firewall restrictions, least-privilege service accounts and version-pinned dependencies.

## Reference pilot topology

```text
invited browser/CLI/agent --> HTTPS identity-gated ingress --> Minglefield API gateway
                                                    |
                                  users / agents / delegations / quotas
                                                    |
                              trusted admission + durable jobs (DESIGN GATE)
                                                    |
                                   internal worker queue and adapter contracts
                                                    |
                              isolated local ComfyUI worker --> local ComfyUI API
                                                    |
                                 controlled output storage / job result links
```

Run logical components on one computer for the first round with separate accounts/processes, loopback-only service ports and separate data directories. Prefer using a separate host/VM for ingress and a GPU host for the ComfyUI worker as exposure increases. GPU and personal workstations must not expose local filesystem access to remote users.

**Security invariant:** an edge allowlist only controls who reaches the gateway; each request is also checked against its **own** Minglefield user, agent, grant, action, target and quota. Do not delegate browser login credentials to autonomous agents. Agents use separately scoped, revocable credentials; never accept an agent's asserted user/role as authority.

## Proposed minimal user-facing pilot

1. Admin-invited test users only. Accounts with secure login, individual identities and revocable sessions.
2. User-owned or explicitly consented agent registration/linking, operator approval, selected scopes, suspension, visibility of allowed activities.
3. A modest web UI: login; agent list; action catalog; controlled request form; job queue/status/results; report feedback.
4. Example API client that can be cloned **once license and participation rights are published**; no blanket access to another user's agents or memory.
5. Admin moderation, manual job disable/pause, usage quotas and a kill switch; comprehensible audit trail and issue reporting.

## Controlled real-effects strategy (separate security workstream)

First approved effects, when SEC release gates are satisfied, should be **reversible, low-impact, private, bounded job creation** rather than game-world currency, purchases, arbitrary file writes or shell execution.

Suggested staged adapters:
- `media.image.generate.v1`: fixed vetted workflow, restricted prompt parameters, fixed output format/resolution and resource caps.
- `media.audio.generate.v1`: fixed workflow, size/duration caps and isolated outputs.
- `media.character3d.generate.v1`: later gated beta, constrained inputs and signed/validated output artifacts (GLB etc.).
- `media.video.animate.v1`: later, resource-intensive 10-second target, carefully bound resolution/codec/bitrate/upload sizes, and postprocessing limits.

These names are **illustrative internal action contract proposals**, not public MAP wire schema commitments. Do not accept arbitrary ComfyUI JSON graphs, path literals, custom Python nodes, model downloads or executable files from users. The worker submits only trusted templates with parameterized allowlisted values. Keep ComfyUI loopback-only, isolate GPU execution, scan/validate uploads and media containers, cap disk/GPU/time concurrency, and expire outputs. Treat uploaded images/video/audio as sensitive user data; define retention and consent.

An independent security review and explicit maintainer approval must precede enabling any real media effects. Existing SEC-01 remote admission remains an architectural draft; SEC-02/03/04/06 and other findings remain open. There is no claim that running a 'private alpha' removes these blockers.

## Two-device test matrix

| Trial | Client path | Must prove |
| --- | --- | --- |
| A | API gateway from local loopback | health/read-only, registration/login in dedicated pilot build |
| B | Same PC to external HTTPS hostname | TLS, reverse-proxy routing, auth gate and CORS/cookies |
| C | Second PC, different ISP/mobile hotspot, no VPN | internet path, remote authentication, upload/download and timeout handling |
| D | Second PC joined to restrictive tailnet via Serve | private network and access policy; no unwanted local port access |
| E | Two independent test users/agents | no cross-user job, result, memory, secret or agent access |
| F | Session/grant revocation while a request is queued or committed | deny **new** admission; exact uncertainty semantics preserved |
| G | Restart and simulated power loss | durable jobs, no automatic replay of uncertain effects |
| H | Denial/rate/size pressure | global per-user/per-agent concurrency, byte limits, 429/413 handling |
| I | Nontechnical participant browser + hobby-coded client | clear onboarding, docs, easy recovery/feedback |

On a single PC, connecting to the public hostname is useful, but it is **not equivalent** to trial C from an independent network.

## Release stages

**Gate A: LAN/private read-only pilot.** No external effects. Deliver secure test service, health, invite-only login, agent view, simulation-only actions, browser client, audit, test suite and negative tests.

**Gate B: external private alpha.** External HTTPS Access gate, individual Minglefield identities, no administrative/public ComfyUI endpoints, tested account isolation, revocation and resource controls. Initially simulation-only.

**Gate C: limited real-media pilot.** Separate approval per fixed ComfyUI action; authenticate worker/admission, durable dedupe and result evidence, strict resources/parameter contracts, output retention/consent, and stop control. Start with one image workflow and single concurrent GPU job; advance only after verified rejection/uncertain-outcome tests.

**Gate D: invited friend trial.** Simple onboarding and feedback, dedicated pilot docs, revoked invitation tests, two-user privacy tests, safe data deletion and explicit consent.

## Important preflight

- Public GitHub visibility is not sufficient re-use rights: README currently says license selection pending. Choose and publish the relevant code/docs licenses or establish explicit pilot authorization before inviting contributors to clone/modify.
- Decide whether pilot identity relies on third-party OAuth/Access or a trusted identity provider; do not implement DIY password reset as a first feature.
- Verify Windows GPU resource consumption, outbound provider rules, security updates, storage backups, admin emergency shutdown, and whether serving user-submitted media has content/moderation/privacy obligations.
- Confirm provider free-tier limits, hostname/domain setup and relevant use terms before publishing.
- Keep the public repository free of access tokens, HMAC keys, account lists, workflow secrets, submitted media and private user logs.

## Immediate next development increment

Deliver an **isolated, local-only, simulation-only vertical slice** with a private-alpha gateway and minimal web client, invite-only user fixture, read-only agent list, simulated job submission/status and safe audit. No tunnel/public listener or real ComfyUI adapter enabled in this initial increment. Add separate negative tests for multi-user isolation, revoked invite/session, missing scopes, replay and rate limits. After passing local tests, test first over Serve and only then through an identity-gated external HTTPS endpoint.

Decision record: user prefers SEC-01 Variant 2 remote authoritative admission. This plan preserves it, while recognizing that remote admission **alone is not** an atomic game-side effect transaction.
