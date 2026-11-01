# Private Alpha — Local gateway and Tailscale Serve rollout gates

Status: **simulation-only developer preview, NOT suitable for invited remote testers yet**. Applies to `server/private_alpha_gateway.py`. No public server or real ComfyUI action is enabled by this document.

## Local developer smoke test (current increment)

From the repository root in PowerShell:

```powershell
python -B server/private_alpha_gateway.py --port 8767
```

The process binds **only** `127.0.0.1:8767`. The console prints a randomly generated **test-only** token, which expires when the process exits. Open `http://127.0.0.1:8767/`, enter the token, click Connect and Simulate action. The only allowed action is `demo.echo`, whose result is `simulated_no_effect`. There are no GPU calls, external effects, ComfyUI jobs, B2 state changes, disk-backed user accounts or persistent jobs. The prototype can show two isolated identities under tests but starts with only one ephemeral local identity.

Focused tests:

```powershell
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_gateway.py" -v
python -B -m unittest discover -s tests/conformance -p "test_sec01_mock_game_adapter.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

The previous maintainer-confirmed suite contained **257 tests**; this increment adds 6 gateway and 5 mock game tests. **Expected 268**, pending local verification.

## Serve is chosen, but NOT switched on yet

Tailscale Serve shares a local service **privately to authorized tailnet peers**, in contrast to **Funnel**, which publishes it to the internet. Serve is a network transport/access layer, not proof of MAP application identity. Remote users must also authenticate as distinct Minglefield principals, with independent agents/delegations. Do not treat an inbound tailnet source IP or unverified proxy header as a user identity.

**Minimum Serve preflight:**

1. Install/upgrade Tailscale on both test computers to a current patched version; check `tailscale version`. Tailscale's October 26, 2026 Serve advisories list **1.104.4+** for their fixes. Keep automatic security updates enabled where practical.
2. Restrict Tailscale policy to the designated user/device and gateway HTTPS port; do not grant general access to the Windows workstation, RDP, SSH, ComfyUI or private file shares.
3. Use MagicDNS and tailnet HTTPS certificates. Prefer one dedicated Serve mount for this gateway. Do not configure Funnel; do not forward Unix sockets.
4. Restrict the local gateway and ComfyUI to loopback and enforce OS firewall/least privilege. Confirm no direct inbound ports from other interfaces.
5. **Before any Serve exposure:** implement robust individual login/invite workflow, token rotation/expiry, persistent account/agent authorization, endpoint rate controls, audit, CSRF/CORS/origin policy, process isolation and negative tests. The current ephemeral bearer-token gateway does **not** meet this gate.
6. Only then inspect existing state with `tailscale serve status`, configure (with locally verified CLI syntax) `tailscale serve --bg http://127.0.0.1:8767` and use `tailscale serve status` to obtain its actual tailnet HTTPS URL. To stop, consult `tailscale serve --help` and disable the configured mount; never infer whether Serve is running merely from the local process state.

The above command is **future rollout guidance**, not a command to run against the current unauthenticated-alpha implementation.

## Two-machine verification, before friends

- A: local loopback health, web UI and simulated job.
- B: independent second PC on a different network with a restrictive tailnet membership/access policy; test authorized access via HTTPS, and a nonmember's inability to access the service.
- C: create two distinct invited accounts with agents; verify cross-user jobs, agent listing, secret visibility and revocation behavior.
- D: test duplicate submissions, rate/size limits, expired credentials, revoked grants and restart recovery.
- E: stop gateway and confirm Serve no longer yields a working application; inspect logs for accidental token leakage.

For external users, invite only confirmed peers into the tailnet with least-privilege access. A tailnet invite is **not** a substitute for Minglefield invite enrollment.

## Separate SEC-01 mock effect boundary

`sec01_mock_game_adapter.py` models a game-owned SQLite transaction that refuses an effect without a previously installed **trusted fixture** admission receipt and refuses duplicate mock application. It is a pure isolated model, with no authenticated receipt, no real effects and no connection to B2 or the pilot gateway. The test-only `install_trusted_fixture_receipt` method must NEVER become a remotely callable production interface.

Even if a future remote admission service serializes current policy with new admissions, its receipt cannot automatically make a separate real game effect atomic. The game must ensure receipt verification, idempotent execution and no bypass paths, and failure/reconciliation semantics remain SEC-01/02/03 work.

## Privacy, licensing and release controls

No real testers' secrets or media in the public repo. README currently says license selection is pending, so define permitted clone/modify/test use before inviting contributors. No ComfyUI execution, arbitrary workflow upload, custom code nodes, file path control or real media generation is available from this prototype.

Security review and maintainer approval per fixed media action are mandatory before any real-media alpha gate.

## Auth v1: vollständige Windows-Schrittfolge

**Wichtig für neue Testende:** Die ausführliche deutschsprachige [Auth-v1-Anleitung mit ZWEI PowerShell-Fenstern](PRIVATE_ALPHA_AUTH_V1_WALKTHROUGH_DE.md) ist die maßgebliche Anleitung für Einladungen, Redeeming und Session-Login. Der Einladungscode gehört **nicht** ins Webclient-Feld; er wird im zweiten Terminal bei `Invitation secret:` eingegeben (unsichtbare Eingabe). Erst der anschließend ausgegebene `Session bearer` gehört auf die Webseite. Fenster A hält den laufenden Gateway; Fenster B dient der Administration; `$alphaDb` muss in beiden Terminals identisch gesetzt werden. Fehlersuche für HTTP 401, 15-Minuten-Sessionablauf, bereits eingelöste Einladungen und den alten Demo-Modus findet sich dort.

## Auth v1 local-only persistence (new, validation pending)

The optional SQLite `private_alpha_auth.py` store now supports operator-created, one-time expiring invitations, local-only redemption, server-generated 15-minute session bearer tokens, logout/revocation, user disablement, a single per-user demo agent and persistent **simulated** job records. It is an isolated prototype, **not** OAuth, real agent onboarding, or a production identity provider. No external effects are allowed.

From the repo root on the server computer, create a local database path **outside the Git checkout**:

```powershell
$alphaDb = "$env:LOCALAPPDATA\\Minglefield\\private-alpha.sqlite"
New-Item -ItemType Directory -Force (Split-Path $alphaDb) | Out-Null
python -B server/private_alpha_admin.py --db $alphaDb invite user.alice
python -B server/private_alpha_admin.py --db $alphaDb redeem --agent agent.alice
python -B server/private_alpha_gateway.py --auth-db $alphaDb --port 8767
```

The first command prints a **one-time invitation secret**. The redemption command prompts for that secret (hidden input) and prints a **test-only session bearer**. Copy only the session bearer into the local webclient. A second user can be provisioned using another invite and another unique agent ID. Sessions expire after 900 seconds; user disable and HTTP `POST /api/logout` revoke sessions. Job records and identities survive process restarts, unlike the original demo mode.

**Never commit the local SQLite file, invite secrets or session bearers. Do not share this version via Serve yet:** invite redemption is operator-managed; there is no validated end-user self-service login, credential refresh/recovery, sufficiently hardened audit/rate limiting, origin assurance or security review. A Tailscale invitation alone does not solve those gaps.

Focused tests:

```powershell
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_auth.py" -v
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_auth_gateway.py" -v
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_gateway.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

**Maintainer-confirmed Windows baseline: 278/278 conformance tests**, MAP v0.1 validator PASS and clean working tree. Subsequent UI/documentation adjustments require renewed local verification. SEC-01 and real media execution remain independently gated.


## Auth v2 local browser registration (2026-11-01; Windows validation pending)

With the **same** `--auth-db` mode, the local page now offers **Einladung einlösen**, **Connect**, **Logout**, and **Simulate action**. The operator still creates invitations locally, but the invited person can redeem the one-time invitation on the browser page while the browser is on the **same computer**. For existing v1 users, the existing valid session token can still be entered manually; previously redeemed invites cannot be reused.

In PowerShell terminal A, launch the gateway (database path must be the same as the admin terminal):

```powershell
$alphaDb = "$env:LOCALAPPDATA\Minglefield\private-alpha.sqlite"
python -B server/private_alpha_gateway.py --auth-db $alphaDb --port 8767
```

In a **separate** PowerShell terminal B:

```powershell
$alphaDb = "$env:LOCALAPPDATA\Minglefield\private-alpha.sqlite"
python -B server/private_alpha_admin.py --db $alphaDb invite user.test2
```

Open `http://127.0.0.1:8767/`; paste the **invitation** into the new **Einladungscode** input, enter a unique agent ID such as `agent.test2`, then click **Einladung einlösen**. On success the session is held **only in that browser tab's RAM**; click **Connect** to display agents and jobs. A page reload forgets it. **Logout** revokes the active session. A browser may also use the manual session-token field if one was issued by the older PowerShell `redeem` command.

The new `/api/redeem` endpoint intentionally requires loopback source and a loopback Host / same-origin Origin, plus a small per-process rate limit. These are **local development safeguards, not sufficient protections for remote exposure**. It is not a tailnet registration endpoint. Avoid exposing it through any proxy, including Serve, even to approved friends: production-grade invitation rate limiting, authenticated user lifecycle/recovery, CSRF/Origin/CORS policy, logging/auditing, persistent rate controls, and a threat review still remain. Secure remote invitation redemption must be designed separately.

Focused additions:

```powershell
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_browser_enrollment.py" -v
python -B -m unittest discover -s tests/conformance -p "test_sec01_mock_admission_proof.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

Last **confirmed** baseline: 278/278. New tests: four browser onboarding and four mock proof tests; **expected 286** before maintainer local confirmation.

## SEC-01 mock admission proof (not coupled to real effects)

`server/sec01_mock_admission_proof.py` uses a test-only HMAC-SHA256 proof over canonical JSON (issuer, audience, executor, job, request fingerprint, effect key, lifetime and nonce). It rejects modified content, wrong key/audience/context, unknown fields and expired proofs. It does **not** establish that an admission was actually committed. It is not connected to B2, the mock game adapter, or the Private Alpha gateway, and does not sign credentials usable by real developers. Real third-party adapters require separate issuer key management, authenticated trust distribution and an authoritative atomic admission protocol.

