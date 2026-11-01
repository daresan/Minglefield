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
        if type(config) is not dict or set(config)!={
            "mode","idle_only","gpu_max_percent","timezone","weekdays",
            "start_minute","end_minute"}:
            raise ValueError("invalid rule")
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
        if (not all(ident(x) for x in (host_id,effect_key,binding))
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
                return HostDecision("committed_mock","no_effect_performed")
            return HostDecision("waiting","outside_schedule")

    def commit_count(self):
        with self.authority.store._tx() as db:
            return db.execute("SELECT count(*) FROM sec01_host_commits").fetchone()[0]
