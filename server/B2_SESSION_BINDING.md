# B2 session binding — implementation decision

Status: approved design direction, not yet implemented.

The current `auth_sessions.token_hash` is the primary key for a session.
`SessionStore.issue()` creates a new session row; it does not rotate an
existing row in place. Revocation marks the individual session revoked.

## Required change

Persist the verified submitting session's token hash in a nullable
`action_jobs.session_token_hash` column. Populate it from the session row
inside the existing B1 submission transaction, never from an untrusted
worker argument. Do not persist bearer tokens.

The B2 worker must recheck that exact session for existence, expiry,
revocation, disabled principal and matching user, agent and delegation.
A fresh session must not revive a job associated with a revoked or
expired session.

Existing B1 jobs have NULL session references. They remain preserved
and cannot be claimed until a separately reviewed reconciliation path
exists. An idempotent replay must not rebind them.

## Migration and verification

Use an additive, repeatable migration for the nullable column without
changing the B1 queued-only state constraint yet. Preserve all job,
audit and reservation records. Cover fresh databases, populated legacy
databases, restart, idempotent replay, revoked session and expired
session with regression tests.

The default 900-second session TTL means delayed jobs may become
ineligible. Long-running job authorization is a separate future design.

This change does not authorize external execution or alter MAP v0.1
wire schemas.
