"""Opt-in B2 schema v2 migration. No worker execution or state transitions.

Call only after initializing the legacy policy/session stores and B1 ActionService.
The migration is atomic and preserves B1 jobs, session references and audit events.
"""
import sqlite3


def migrate_b2(database):
    db = sqlite3.connect(str(database), timeout=10, isolation_level=None)
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("BEGIN IMMEDIATE")
        version = db.execute(
            "SELECT version FROM action_schema WHERE singleton=1").fetchone()
        if version is None or version[0] not in (1, 2):
            raise ValueError("unsupported or missing B1 action schema")
        if version[0] == 2:
            db.commit()
            return
        columns = {row[1] for row in db.execute("PRAGMA table_info(action_jobs)")}
        if "session_token_hash" not in columns:
            db.execute("ALTER TABLE action_jobs ADD COLUMN session_token_hash TEXT")
        # Rename and copy rather than dropping the parent table; preserve FK targets.
        db.execute("""CREATE TABLE action_jobs_v2 (
            job_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
            agent_id TEXT NOT NULL, delegation_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
            request_json TEXT NOT NULL, cost_minor INTEGER NOT NULL CHECK(cost_minor>=0),
            pricing_revision TEXT NOT NULL, policy_revision INTEGER NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('queued','claimed','denied')),
            created_at REAL NOT NULL, session_token_hash TEXT,
            claimed_by TEXT, claim_token_hash TEXT,
            UNIQUE(user_id,delegation_id,idempotency_key),
            FOREIGN KEY(user_id) REFERENCES auth_principals(user_id),
            FOREIGN KEY(agent_id) REFERENCES agents(agent_id),
            FOREIGN KEY(delegation_id) REFERENCES grants(delegation_id))""")
        db.execute("""INSERT INTO action_jobs_v2
            (job_id,user_id,agent_id,delegation_id,idempotency_key,fingerprint,
             request_json,cost_minor,pricing_revision,policy_revision,state,
             created_at,session_token_hash)
            SELECT job_id,user_id,agent_id,delegation_id,idempotency_key,
                   fingerprint,request_json,cost_minor,pricing_revision,
                   policy_revision,state,created_at,session_token_hash
            FROM action_jobs""")
        db.execute("""CREATE TABLE action_audit_v2 (
            event_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
            actor_user_id TEXT NOT NULL, event_type TEXT NOT NULL
                CHECK(event_type IN ('job.queued','job.claimed','job.denied')),
            created_at REAL NOT NULL,
            FOREIGN KEY(job_id) REFERENCES action_jobs_v2(job_id))""")
        db.execute("""INSERT INTO action_audit_v2
            SELECT event_id,job_id,actor_user_id,event_type,created_at
            FROM action_audit""")
        db.execute("DROP TABLE action_audit")
        db.execute("DROP TABLE action_jobs")
        db.execute("ALTER TABLE action_jobs_v2 RENAME TO action_jobs")
        db.execute("ALTER TABLE action_audit_v2 RENAME TO action_audit")
        db.execute("CREATE INDEX action_jobs_claim_queue ON action_jobs(state,created_at,job_id)")
        db.execute("CREATE INDEX action_audit_job ON action_audit(job_id,created_at,event_id)")
        violations = db.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ValueError("B2 migration foreign key violations")
        db.execute("UPDATE action_schema SET version=2 WHERE singleton=1")
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
