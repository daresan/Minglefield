"""SEC-01 isolated SQLite effect-acceptance simulation. Never invokes effects.

This models a *single* authoritative acceptance database, not a distributed
authorization protocol or a B2 integration. Callers/capabilities are not authenticated.
"""
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from sec01_fencing_sim import FenceDecision


def _valid(epoch, effect_key, binding):
    return (type(epoch) is int and 0 <= epoch < 2**63 - 1
            and isinstance(effect_key, str) and bool(effect_key)
            and isinstance(binding, tuple) and bool(binding)
            and all(isinstance(v, str) and bool(v) for v in binding))


class SQLiteEffectBoundary:
    """SQLite BEGIN IMMEDIATE serializes revoke and accept across connections."""

    def __init__(self, database):
        self.database = str(Path(database))
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_authority (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                epoch INTEGER NOT NULL CHECK(epoch >= 0),
                revoked INTEGER NOT NULL CHECK(revoked IN (0,1)))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_acceptance (
                effect_key TEXT PRIMARY KEY, binding_json TEXT NOT NULL)""")
            db.execute("""INSERT OR IGNORE INTO sec01_authority
                (singleton,epoch,revoked) VALUES (1,0,0)""")
            db.commit()

    def capability_epoch(self):
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            row = db.execute(
                "SELECT epoch FROM sec01_authority WHERE singleton=1").fetchone()
            if not row or type(row[0]) is not int:
                raise RuntimeError("invalid authority state")
            return row[0]

    def revoke(self):
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT epoch FROM sec01_authority WHERE singleton=1").fetchone()
            if not row or type(row[0]) is not int or row[0] >= 2**63 - 2:
                raise RuntimeError("invalid authority epoch")
            db.execute("""UPDATE sec01_authority SET epoch=?,revoked=1
                WHERE singleton=1""", (row[0] + 1,))
            db.commit()

    def accept(self, *, epoch, effect_key, binding):
        if not _valid(epoch, effect_key, binding):
            return FenceDecision(False, "invalid_capability")
        encoded = json.dumps(binding, ensure_ascii=True, separators=(",", ":"))
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT binding_json FROM sec01_acceptance WHERE effect_key=?",
                (effect_key,)).fetchone()
            if old is not None:
                if old[0] != encoded:
                    return FenceDecision(False, "idempotency_binding_mismatch")
                return FenceDecision(True, "already_accepted_no_new_effect")
            current = db.execute(
                "SELECT epoch,revoked FROM sec01_authority WHERE singleton=1").fetchone()
            if (current is None or type(current[0]) is not int
                    or current[1] != 0 or epoch != current[0]):
                return FenceDecision(False, "revoked_or_stale_epoch")
            db.execute("""INSERT INTO sec01_acceptance(effect_key,binding_json)
                VALUES (?,?)""", (effect_key, encoded))
            db.commit()
            return FenceDecision(True, "accepted_once")

    def accepted_count(self):
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            return db.execute("SELECT COUNT(*) FROM sec01_acceptance").fetchone()[0]
