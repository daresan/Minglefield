# P1.4f.2g.2 — Integration verification evidence (draft)

This phase defines evidence requirements; it does not implement downloads, installation, or trusted attestations.

1. Source authorization comes from the validated curated registry or explicit project-scoped authorization. A lockfile URL is not an authorization.
2. Release identity must bind the selected version and asset to that authorized source. Tags and release notes alone are insufficient.
3. Artifact integrity requires hashing the exact downloaded bytes and comparing them with a digest independently obtained through the trusted release channel. A lockfile-provided digest alone proves nothing.
4. Installation verification additionally requires independently checking installed files or a trusted installer journal bound to project, paths and artifact digest. A successful download is not proof of installation.
5. Audit evidence must be recorded in an access-controlled runtime store; an editable report in the Game repository is not a security attestation.

States: `unknown` (insufficient evidence), `declared` (lockfile only), `integrity_verified` (authorized source, release identity and independently checked digest), `installation_verified` (additionally checked installed state), `invalid` (source, release, digest or installation conflict). Changes to installed files invalidate stale evidence. Updates fail closed until the independent checks pass.

The next phase connects read-only unified lock inspection and collision handling; installation and rollback follow after verification becomes operational. No general-purpose package manager is in scope. See `docs/GAME-DELIVERY-CONTINUITY.md` for the full P1.4f acceptance gate.
