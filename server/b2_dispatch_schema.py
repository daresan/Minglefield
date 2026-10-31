"""Explicit atomic B2.3a schema v3 -> v4 migration; no dispatcher or effects."""
import sqlite3


def migrate_b2_dispatch(database):
    db = sqlite3.connect(str(database), timeout=10, isolation_level=None)
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("BEGIN IMMEDIATE")
        version = db.execute("SELECT version FROM action_schema WHERE singleton=1").fetchone()
        if version not in ((3,), (4,)):
            raise ValueError("dispatch migration requires action schema v3 or v4")
        if version == (4,):
            _validate_v4(db)
            db.commit()
            return
        db.execute("""CREATE TABLE action_jobs_v4 (
            job_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
            agent_id TEXT NOT NULL, delegation_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
            request_json TEXT NOT NULL, cost_minor INTEGER NOT NULL CHECK(cost_minor>=0),
            pricing_revision TEXT NOT NULL, policy_revision INTEGER NOT NULL,
            state TEXT NOT NULL CHECK(state IN
                ('queued','claimed','ready','denied','dispatch_committed',
                 'succeeded','failed','outcome_unknown')),
            created_at REAL NOT NULL, session_token_hash TEXT,
            claimed_by TEXT, claim_token_hash TEXT,
            effect_idempotency_key TEXT UNIQUE,
            dispatch_fingerprint TEXT,
            adapter_id TEXT, adapter_version TEXT, dispatched_at REAL,
            UNIQUE(user_id,delegation_id,idempotency_key),
            FOREIGN KEY(user_id) REFERENCES auth_principals(user_id),
            FOREIGN KEY(agent_id) REFERENCES agents(agent_id),
            FOREIGN KEY(delegation_id) REFERENCES grants(delegation_id),
            CHECK (
                (state IN ('queued','claimed','ready','denied')
                 AND effect_idempotency_key IS NULL AND dispatch_fingerprint IS NULL
                 AND adapter_id IS NULL AND adapter_version IS NULL AND dispatched_at IS NULL)
                OR
                (state IN ('dispatch_committed','succeeded','failed','outcome_unknown')
                 AND effect_idempotency_key IS NOT NULL AND dispatch_fingerprint IS NOT NULL
                 AND adapter_id IS NOT NULL AND adapter_version IS NOT NULL
                 AND dispatched_at IS NOT NULL)
            ))""")
        db.execute("""INSERT INTO action_jobs_v4
            (job_id,user_id,agent_id,delegation_id,idempotency_key,fingerprint,
             request_json,cost_minor,pricing_revision,policy_revision,state,
             created_at,session_token_hash,claimed_by,claim_token_hash)
            SELECT job_id,user_id,agent_id,delegation_id,idempotency_key,fingerprint,
             request_json,cost_minor,pricing_revision,policy_revision,state,
             created_at,session_token_hash,claimed_by,claim_token_hash FROM action_jobs""")
        db.execute("""CREATE TABLE action_audit_v4 (
            event_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
            actor_user_id TEXT NOT NULL,
            event_type TEXT NOT NULL CHECK(event_type IN
                ('job.queued','job.claimed','job.ready','job.denied',
                 'job.dispatch_committed','job.succeeded','job.failed','job.outcome_unknown')),
            created_at REAL NOT NULL,
            FOREIGN KEY(job_id) REFERENCES action_jobs_v4(job_id))""")
        db.execute("INSERT INTO action_audit_v4 SELECT * FROM action_audit")
        db.execute("DROP TABLE action_audit")
        db.execute("DROP TABLE action_jobs")
        db.execute("ALTER TABLE action_jobs_v4 RENAME TO action_jobs")
        db.execute("ALTER TABLE action_audit_v4 RENAME TO action_audit")
        db.execute("CREATE INDEX action_jobs_claim_queue ON action_jobs(state,created_at,job_id)")
        db.execute("CREATE INDEX action_audit_job ON action_audit(job_id,created_at,event_id)")
        _validate_v4(db)
        db.execute("UPDATE action_schema SET version=4 WHERE singleton=1")
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def _validate_v4(db):
    jobs = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='action_jobs'").fetchone()
    audit = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='action_audit'").fetchone()
    columns = {row[1] for row in db.execute("PRAGMA table_info(action_jobs)")}
    required = {"effect_idempotency_key","dispatch_fingerprint","adapter_id",
                "adapter_version","dispatched_at","session_token_hash","claim_token_hash"}
    if (not jobs or not audit or not required <= columns
            or "dispatch_committed" not in jobs[0]
            or "outcome_unknown" not in jobs[0]
            or "job.dispatch_committed" not in audit[0]
            or "job.outcome_unknown" not in audit[0]
            or db.execute("PRAGMA foreign_key_check").fetchone() is not None):
        raise ValueError("unsupported or incomplete action schema v4")
