"""SEC-01 host-admin scheduling and FINAL MOCK COMMIT policy.

Local-only SQLite simulator. Host admins own policy, not job requesters.
No actual effects, no network, no GPU polling. A supplied utilization value
is untrusted fixture telemetry; production requires host-owned measurement.
The online proof precheck happens BEFORE the commit transaction, so remote
revocation atomicity is NOT solved by this demonstration.
"""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from private_alpha_auth import ident

@dataclass(frozen=True)
class HostDecision:
    state: str
    reason: str

class HostCommitPolicy:
    def __init__(self, authority):
        self.authority=authority
        with authority.store._tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_owners(
                host_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_effect_definitions(
                host_id TEXT NOT NULL, effect_id TEXT NOT NULL,
                description TEXT NOT NULL, enabled INTEGER NOT NULL,
                PRIMARY KEY(host_id,effect_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_admins(
                host_id TEXT NOT NULL, admin_id TEXT NOT NULL,
                PRIMARY KEY(host_id,admin_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_rules(
                host_id TEXT NOT NULL, rule_id TEXT NOT NULL,
                priority INTEGER NOT NULL, enabled INTEGER NOT NULL,
                config TEXT NOT NULL, PRIMARY KEY(host_id,rule_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_approvals(
                host_id TEXT NOT NULL, effect_key TEXT NOT NULL,
                approved_by TEXT NOT NULL, PRIMARY KEY(host_id,effect_key))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_commits(
                effect_key TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                binding TEXT NOT NULL, rule_id TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_active_slots(
                effect_key TEXT PRIMARY KEY, host_id TEXT NOT NULL)""")

    def claim_local_host(self, host_id, owner_id):
        """Only invoke after gateway-local bootstrap proof AND live Alpha session."""
        if not ident(host_id) or not ident(owner_id):
            return HostDecision("denied","invalid_host")
        with self.authority.store._tx() as db:
            if db.execute("""SELECT 1 FROM alpha_users WHERE user_id=? AND disabled=0""",
                          (owner_id,)).fetchone() is None:
                return HostDecision("denied","invalid_owner")
            old=db.execute("""SELECT owner_id FROM sec01_host_owners
                WHERE host_id=?""",(host_id,)).fetchone()
            if old is not None:
                return HostDecision("claimed" if old==(owner_id,) else "denied",
                    "already_owned" if old==(owner_id,) else "host_owned_by_other_user")
            host=db.execute("""SELECT operator_id FROM alpha_executor_hosts
                WHERE host_id=?""",(host_id,)).fetchone()
            if host is not None and host[0]!=owner_id:
                return HostDecision("denied","existing_host_requires_operator_migration")
            if host is None:
                db.execute("""INSERT INTO alpha_executor_hosts VALUES(?,?,1)""",
                           (host_id,owner_id))
            db.execute("""INSERT INTO sec01_host_owners VALUES(?,?)""",
                       (host_id,owner_id))
            return HostDecision("claimed","local_host_claimed_no_effect")

    def define_effect(self, host_id, owner_id, effect_id, description, enabled):
        """Metadata only. No arbitrary commands, paths, endpoints or execution."""
        if (not ident(host_id) or not ident(owner_id) or not ident(effect_id)
                or type(description) is not str or len(description)>256
                or type(enabled) is not bool):
            return HostDecision("denied","invalid_effect_definition")
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,owner_id):
                return HostDecision("denied","not_host_owner")
            db.execute("""INSERT INTO sec01_host_effect_definitions VALUES(?,?,?,?)
                ON CONFLICT(host_id,effect_id) DO UPDATE SET
                description=excluded.description,enabled=excluded.enabled""",
                (host_id,effect_id,description,int(enabled)))
            return HostDecision("saved","effect_metadata_only")

    def manual_start_mock(self, host_id, owner_id, effect_id):
        """Explicit manual request recorded only as intent; NEVER executes."""
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,owner_id):
                return HostDecision("denied","not_host_owner")
            row=db.execute("""SELECT enabled FROM sec01_host_effect_definitions
                WHERE host_id=? AND effect_id=?""",(host_id,effect_id)).fetchone()
            if row!=(1,):
                return HostDecision("denied","effect_unavailable")
            return HostDecision("requested_mock","manual_intent_only_no_execution")

    def add_admin_fixture(self, host_id, admin_id):
        """Trusted LOCAL provisioning; never expose to a requester."""
        if not ident(host_id) or not ident(admin_id):
            raise ValueError("invalid administrator")
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM alpha_executor_hosts WHERE host_id=?",
                          (host_id,)).fetchone() is None:
                raise ValueError("unknown host")
            db.execute("INSERT INTO sec01_host_admins VALUES(?,?)",
                       (host_id,admin_id))

    @staticmethod
    def _validate(config):
        if type(config) is not dict or not {"mode","idle_only","gpu_max_percent","timezone","weekdays","start_minute","end_minute"} <= set(config) or set(config)-{"mode","idle_only","gpu_max_percent","timezone","weekdays","start_minute","end_minute","max_parallel_effects"}: 
            raise ValueError("invalid rule")
        limit=config.get("max_parallel_effects")
        if limit is not None and (type(limit) is not int or not 1<=limit<=1024):
            raise ValueError("invalid parallel limit")
        if config["mode"] not in ("automatic","manual"):
            raise ValueError("invalid mode")
        if type(config["idle_only"]) is not bool:
            raise ValueError("invalid idle policy")
        gpu=config["gpu_max_percent"]
        if gpu is not None and (type(gpu) is not int or not 0<=gpu<=100):
            raise ValueError("invalid GPU threshold")
        days=config["weekdays"]
        if (type(days) is not list or not days or len(set(map(str,days)))!=len(days)
                or any(type(d) is not int or not 0<=d<=6 for d in days)):
            raise ValueError("invalid weekdays")
        for key in ("start_minute","end_minute"):
            val=config[key]
            if type(val) is not int or not 0<=val<=1440:
                raise ValueError("invalid time window")
        if config["start_minute"]>=config["end_minute"]:
            raise ValueError("time windows cannot cross midnight")
        try:
            ZoneInfo(config["timezone"])
        except (TypeError,ZoneInfoNotFoundError,ValueError):
            raise ValueError("invalid timezone")

    def _admin(self, db, host_id, admin_id):
        return db.execute("""SELECT 1 FROM sec01_host_admins
            WHERE host_id=? AND admin_id=?""",(host_id,admin_id)).fetchone() is not None

    def upsert_rule(self, host_id, admin_id, rule_id, *, priority, enabled, config):
        if (not all(ident(x) for x in (host_id,admin_id,rule_id))
                or type(priority) is not int or priority<0
                or type(enabled) is not bool):
            return HostDecision("denied","invalid_rule")
        try:
            self._validate(config)
        except ValueError:
            return HostDecision("denied","invalid_rule")
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,admin_id):
                return HostDecision("denied","not_host_admin")
            db.execute("""INSERT INTO sec01_host_rules VALUES(?,?,?,?,?)
                ON CONFLICT(host_id,rule_id) DO UPDATE SET
                priority=excluded.priority,enabled=excluded.enabled,
                config=excluded.config""",
                (host_id,rule_id,priority,int(enabled),
                 json.dumps(config,sort_keys=True)))
            return HostDecision("saved","rule_saved")

    def delete_rule(self, host_id, admin_id, rule_id):
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,admin_id):
                return HostDecision("denied","not_host_admin")
            count=db.execute("""DELETE FROM sec01_host_rules
                WHERE host_id=? AND rule_id=?""",(host_id,rule_id)).rowcount
            return HostDecision("deleted" if count else "denied",
                                "rule_deleted" if count else "rule_missing")

    def approve(self, host_id, admin_id, effect_key):
        if not all(ident(x) for x in (host_id,admin_id,effect_key)):
            return HostDecision("denied","invalid_approval")
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,admin_id):
                return HostDecision("denied","not_host_admin")
            db.execute("""INSERT INTO sec01_host_approvals VALUES(?,?,?)
                ON CONFLICT(host_id,effect_key) DO NOTHING""",
                (host_id,effect_key,admin_id))
            return HostDecision("approved","mock_approval_recorded")

    def decide(self, *, host_id, effect_key, binding, now,
               gpu_percent=None, running_effects=None):
        """Mock commit only. Telemetry and clock must be trusted by real host."""
        if (not ident(host_id) or not ident(effect_key)
                or type(binding) is not str or not 1<=len(binding)<=4096
                or type(now) is not int):
            return HostDecision("denied","invalid_intent")
        with self.authority.store._tx() as db:
            old=db.execute("""SELECT host_id,binding FROM sec01_host_commits
                WHERE effect_key=?""",(effect_key,)).fetchone()
            if old is not None:
                return HostDecision("duplicate" if old==(host_id,binding) else "denied",
                    "historical_mock_commit" if old==(host_id,binding)
                    else "idempotency_binding_mismatch")
            host=db.execute("""SELECT active FROM alpha_executor_hosts
                WHERE host_id=?""",(host_id,)).fetchone()
            if host!=(1,):
                return HostDecision("denied","host_unavailable")
            admission=db.execute("""SELECT binding FROM alpha_sec01_admissions
                WHERE effect_key=?""",(effect_key,)).fetchone()
            if admission is None or admission[0]!=binding:
                return HostDecision("denied","admission_binding_missing")
            try:
                job,fingerprint,requester,agent,owner,executor,assigned_host,action=json.loads(binding)
            except (ValueError,TypeError):
                return HostDecision("denied","invalid_admission_binding")
            if assigned_host!=host_id or action!="demo.echo":
                return HostDecision("denied","admission_host_mismatch")
            agent_row=db.execute("""SELECT a.user_id,a.disabled,u.disabled
                FROM alpha_agents a JOIN alpha_users u ON u.user_id=a.user_id
                WHERE a.agent_id=?""",(agent,)).fetchone()
            if agent_row!=(owner,0,0):
                return HostDecision("denied","agent_or_owner_revoked")
            requester_row=db.execute("SELECT disabled FROM alpha_users WHERE user_id=?",
                (requester,)).fetchone()
            if requester_row!=(0,):
                return HostDecision("denied","requester_revoked")
            if requester!=owner and db.execute("""SELECT revoked FROM alpha_agent_grants
                WHERE agent_id=? AND grantee_user_id=? AND action='demo.echo'""",
                (agent,requester)).fetchone()!=(0,):
                return HostDecision("denied","grant_revoked")
            host_operator=db.execute("""SELECT operator_id FROM alpha_executor_hosts
                WHERE host_id=?""",(host_id,)).fetchone()
            if host_operator!=(executor,):
                return HostDecision("denied","executor_host_mismatch")
            if db.execute("""SELECT enabled FROM alpha_agent_host_assignments
                WHERE agent_id=? AND host_id=?""",(agent,host_id)).fetchone()!=(1,):
                return HostDecision("denied","host_assignment_revoked")
            rules=db.execute("""SELECT rule_id,config FROM sec01_host_rules
                WHERE host_id=? AND enabled=1 ORDER BY priority,rule_id""",
                (host_id,)).fetchall()
            if not rules:
                return HostDecision("waiting","no_enabled_rule")
            for rule_id,encoded in rules:
                config=json.loads(encoded)
                local=datetime.fromtimestamp(now,timezone.utc).astimezone(
                    ZoneInfo(config["timezone"]))
                minute=local.hour*60+local.minute
                if (local.weekday() not in config["weekdays"]
                        or not config["start_minute"]<=minute<config["end_minute"]):
                    continue
                limit=config.get("max_parallel_effects")
                if limit is not None:
                    active=db.execute("""SELECT COUNT(*) FROM sec01_host_active_slots
                        WHERE host_id=?""",(host_id,)).fetchone()[0]
                    if active>=limit:
                        return HostDecision("waiting","parallel_limit_reached")
                if config["idle_only"]:
                    if type(running_effects) is not int or running_effects<0:
                        return HostDecision("waiting","telemetry_unavailable")
                    if running_effects!=0:
                        return HostDecision("waiting","host_busy")
                threshold=config["gpu_max_percent"]
                if threshold is not None:
                    if (type(gpu_percent) not in (int,float)
                            or not 0<=gpu_percent<=100):
                        return HostDecision("waiting","telemetry_unavailable")
                    if gpu_percent>=threshold:
                        return HostDecision("waiting","gpu_threshold_not_met")
                if config["mode"]=="manual" and db.execute(
                    """SELECT 1 FROM sec01_host_approvals
                    WHERE host_id=? AND effect_key=?""",
                    (host_id,effect_key)).fetchone() is None:
                    return HostDecision("waiting","manual_approval_required")
                db.execute("INSERT INTO sec01_host_commits VALUES(?,?,?,?)",
                           (effect_key,host_id,binding,rule_id))
                db.execute("INSERT INTO sec01_host_active_slots VALUES(?,?)",
                           (effect_key,host_id))
                return HostDecision("committed_mock","no_effect_performed")
            return HostDecision("waiting","outside_schedule")

    def finish_mock(self, host_id, admin_id, effect_key):
        """Trusted local completion simulation; no actual process is stopped."""
        if not all(ident(x) for x in (host_id,admin_id,effect_key)):
            return HostDecision("denied","invalid_completion")
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,admin_id):
                return HostDecision("denied","not_host_admin")
            count=db.execute("""DELETE FROM sec01_host_active_slots
                WHERE host_id=? AND effect_key=?""",(host_id,effect_key)).rowcount
            return HostDecision("finished_mock" if count else "denied",
                                "slot_released" if count else "slot_missing")

    def active_count(self, host_id):
        with self.authority.store._tx() as db:
            return db.execute("""SELECT COUNT(*) FROM sec01_host_active_slots
                WHERE host_id=?""",(host_id,)).fetchone()[0]

    def list_hosts(self, admin_id):
        """Only hosts administered by this authenticated Alpha user."""
        if not ident(admin_id):
            return []
        with self.authority.store._tx() as db:
            hosts=db.execute("""SELECT h.host_id,h.active FROM alpha_executor_hosts h
                WHERE EXISTS(SELECT 1 FROM sec01_host_admins a
                    WHERE a.host_id=h.host_id AND a.admin_id=?)
                  OR EXISTS(SELECT 1 FROM sec01_host_owners o
                    WHERE o.host_id=h.host_id AND o.owner_id=?)
                ORDER BY h.host_id""",(admin_id,admin_id)).fetchall()
            result=[]
            for host_id,active in hosts:
                rules=db.execute("""SELECT rule_id,priority,enabled,config
                    FROM sec01_host_rules WHERE host_id=?
                    ORDER BY priority,rule_id""",(host_id,)).fetchall()
                slots=db.execute("""SELECT effect_key FROM sec01_host_active_slots
                    WHERE host_id=? ORDER BY effect_key""",(host_id,)).fetchall()
                effects=db.execute("""SELECT effect_id,description,enabled\n                    FROM sec01_host_effect_definitions WHERE host_id=?\n                    ORDER BY effect_id""",(host_id,)).fetchall()\n                result.append(dict(host_id=host_id,active=bool(active),\n                    effects=[dict(effect_id=e,description=d,enabled=bool(on))\n                             for e,d,on in effects],
                    active_effects=len(slots),slots=[x[0] for x in slots],
                    rules=[dict(rule_id=rid,priority=priority,enabled=bool(enabled),
                                config=json.loads(cfg))
                           for rid,priority,enabled,cfg in rules]))
            return result

    def restart_recovery_snapshot(self, host_id, admin_id):
        """Crash-safe conservative policy: all retained slots remain blocked.

        A restart NEVER converts a historical mock commit into a new one.
        Recovery is observational until an admin explicitly resolves a slot.
        """
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,admin_id):
                return None
            rows=db.execute("""SELECT effect_key FROM sec01_host_active_slots
                WHERE host_id=? ORDER BY effect_key""",(host_id,)).fetchall()
            return [dict(effect_key=key,state="uncertain_after_restart",
                         auto_retry_allowed=False) for (key,) in rows]

    def lifecycle(self, host_id, admin_id):
        """Read-only local mock lifecycle, scoped to a host admin."""
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,admin_id):
                return None
            rows=db.execute("""SELECT c.effect_key,c.rule_id,
                CASE WHEN s.effect_key IS NULL THEN 'finished_mock'
                     ELSE 'reserved_mock' END
                FROM sec01_host_commits c
                LEFT JOIN sec01_host_active_slots s ON s.effect_key=c.effect_key
                WHERE c.host_id=? ORDER BY c.effect_key""",(host_id,)).fetchall()
            return [dict(effect_key=key,rule_id=rid,state=state)
                    for key,rid,state in rows]

    def commit_count(self):
        with self.authority.store._tx() as db:
            return db.execute("SELECT count(*) FROM sec01_host_commits").fetchone()[0]
