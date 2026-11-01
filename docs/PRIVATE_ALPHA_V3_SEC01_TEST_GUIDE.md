# Private Alpha v3 and SEC-01 mock bridge — developer test increment

**Status:** Isolated local simulator; no external effects, real admission server, ComfyUI job or Tailscale Serve access. The most recent user-confirmed full test baseline was **286/286** before this increment. New tests still require Windows validation.

## Equal user/agent ID strings

`user.charlie` is allowed to name both a **user** and an **agent**. The strings are not principals by themselves: authorization must always carry the identity kind and the authenticated owner. New regression tests cover identical IDs, a second isolated user with no cross-user job visibility, and session revocation on user disablement. This **does not** establish a complete multi-agent delegation model.

## Alpha v3 local UI feedback

The local web page now distinguishes active/unknown/expired session status. After a newly redeemed invitation, it displays a locally estimated remaining lifetime; after a manually pasted existing session token, the expiry is unknown until the server denies it. Any HTTP 401 must clear the active browser token, with a clear re-login explanation. **Do not use the browser-reported remaining lifetime as authorization evidence.** The real server always enforces its own session expiry. No credentials are persisted in browser storage or exported to logs.

## SEC-01 simulated proof-game boundary

The separate `sec01_mock_proof_game_bridge.py` does not install admission receipts or issue capabilities. It verifies the mock HMAC envelope, then calls the game-owned mock transaction. A valid proof **without an independently installed trusted fixture receipt** must be rejected. With a receipt installed, the game database records at most one mock effect for the exact binding. Tests include HMAC tampering, wrong adapter audience, expiry, changed fixture binding, repeated calls and parallel calls.

**Critical unresolved distinction:** the fixture receipt is not authenticated or linked to B2 revocation state, and the HMAC secret is shared rather than appropriate for third-party game developers. This simulation cannot justify the security of external real effects or immediate revocation. SEC-01 remains CRITICAL/OPEN.

## Local validation (Windows PowerShell, repository root)

```powershell
git pull --ff-only
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_typed_identity.py" -v
python -B -m unittest discover -s tests/conformance -p "test_sec01_mock_proof_game_bridge.py" -v
python -B -m unittest discover -s tests/conformance -p "test_private_alpha_browser_enrollment.py" -v
python -B -m unittest discover -s tests/conformance -p "test_*.py"
python -B tests/conformance/validate_map_v01.py
git diff --check
git status --short
```

Expected: **3 typed-identity tests, 5 SEC-01 bridge tests, 1 UI smoke test and 295 conformance tests** if no other tests were added. These are expectations, not already verified outcomes.

For the UI restart the existing **loopback-only** gateway:

```powershell
$alphaDb = "$env:LOCALAPPDATA\Minglefield\private-alpha.sqlite"
python -B server/private_alpha_gateway.py --auth-db $alphaDb --port 8767
```

Use an **unredeemed** invite for a new browser registration; existing redeemed user identities cannot simply redeem again. Do not delete an existing SQLite database to work around session expiration. Refer to [PRIVATE_ALPHA_AUTH_V1_WALKTHROUGH_DE.md](PRIVATE_ALPHA_AUTH_V1_WALKTHROUGH_DE.md) for separate PowerShell windows and the difference between an invitation and a session bearer.

## Next security gates

Before Serve: proper remote identity and session lifecycle, origin/CSRF protection, durable rate limits, audit, account recovery, invitation expiry/abuse handling, administrator controls and negative tests for proxy trust boundaries. Before real effects: authoritative revocation/admission ordering, secure issuer authentication and audience-specific signing, game receipt authenticity/dedupe, outcomes and failure evidence, SEC-01 through SEC-09 review and explicit approval.
