"""Isolated SEC-01 multi-authority SQLite fencing simulation.

No B2 integration, external effects, credential authentication or network guarantees.
All authority writes and acceptance share ONE SQLite database/transaction order.
"""
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from sec01_fencing_sim import FenceDecision

KINDS = ("session", "grant", "agent", "principal")
MAX_EPOCH = 2**63 - 2


@dataclass(frozen=True)
class AuthoritySnapshot:
    identities: tuple
    epochs: tuple


class SQLiteAuthorityFence:
    def __init__(self, database):
        self.database = str(Path(database))
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_authorities (
                kind TEXT NOT NULL, identity TEXT NOT NULL,
                epoch INTEGER NOT NULL CHECK(epoch >= 0),
                active INTEGER NOT NULL CHECK(active IN (0,1)),
                PRIMARY KEY(kind,identity))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_admissions (
                effect_key TEXT PRIMARY KEY, binding TEXT NOT NULL)""")
            db.commit()

    @staticmethod
    def _identities(identities):
        return (type(identities) is tuple and len(identities) == len(KINDS)
                and all(type(v) is str and bool(v) and len(v) <= 128
                        for v in identities))

    @staticmethod
    def _binding(binding):
        return (type(binding) is tuple and bool(binding)
                and all(type(v) is str and bool(v) for v in binding))

    def provision(self, identities):
        """Trusted fixture provisioning; never reactivates an existing identity."""
        if not self._identities(identities):
            raise ValueError("invalid authority identities")
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            db.execute("BEGIN IMMEDIATE")
            for kind, identity in zip(KINDS, identities):
                db.execute("""INSERT OR IGNORE INTO sec01_authorities
                    (kind,identity,epoch,active) VALUES (?,?,0,1)""",
                    (kind, identity))
            db.commit()

    def snapshot(self, identities):
        """Snapshot is NOT an authenticated bearer capability."""
        if not self._identities(identities):
            raise ValueError("invalid authority identities")
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            db.execute("BEGIN IMMEDIATE")
            rows = [db.execute("""SELECT epoch,active FROM sec01_authorities
                WHERE kind=? AND identity=?""", (kind, identity)).fetchone()
                for kind, identity in zip(KINDS, identities)]
            if any(row is None or row[1] != 1 for row in rows):
                raise ValueError("inactive or missing authority")
            result = AuthoritySnapshot(identities, tuple(row[0] for row in rows))
            db.commit()
            return result

    def invalidate(self, kind, identity, *, revoke=True):
        """Models revocation or agent-policy change, even if authority stays active."""
        if kind not in KINDS or type(identity) is not str or not identity:
            raise ValueError("invalid authority")
        if type(revoke) is not bool:
            raise ValueError("invalid revocation flag")
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT epoch FROM sec01_authorities
                WHERE kind=? AND identity=?""", (kind, identity)).fetchone()
            if row is None or type(row[0]) is not int or row[0] >= MAX_EPOCH:
                raise ValueError("unknown or exhausted authority")
            db.execute("""UPDATE sec01_authorities SET epoch=?, active=?
                WHERE kind=? AND identity=?""",
                (row[0] + 1, 0 if revoke else 1, kind, identity))
            db.commit()

    def accept(self, *, snapshot, effect_key, binding):
        if (type(snapshot) is not AuthoritySnapshot
                or not self._identities(snapshot.identities)
                or type(snapshot.epochs) is not tuple
                or len(snapshot.epochs) != len(KINDS)
                or any(type(v) is not int or not 0 <= v <= MAX_EPOCH
                       for v in snapshot.epochs)
                or type(effect_key) is not str or not effect_key
                or not self._binding(binding)):
            return FenceDecision(False, "invalid_capability")
        # Include authority identity and epochs in the immutable idempotency binding.
        encoded = json.dumps([snapshot.identities, snapshot.epochs, binding],
                             separators=(",", ":"), ensure_ascii=True)
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("""SELECT binding FROM sec01_admissions
                WHERE effect_key=?""", (effect_key,)).fetchone()
            if previous is not None:
                if previous[0] != encoded:
                    return FenceDecision(False, "idempotency_binding_mismatch")
                return FenceDecision(True, "already_accepted_no_new_effect")
            for kind, identity, epoch in zip(
                    KINDS, snapshot.identities, snapshot.epochs):
                current = db.execute("""SELECT epoch,active FROM sec01_authorities
                    WHERE kind=? AND identity=?""", (kind, identity)).fetchone()
                if current != (epoch, 1):
                    return FenceDecision(False, "authority_revoked_or_changed")
            db.execute("""INSERT INTO sec01_admissions(effect_key,binding)
                VALUES (?,?)""", (effect_key, encoded))
            db.commit()
            return FenceDecision(True, "accepted_once")

    def accepted_count(self):
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            return db.execute("SELECT COUNT(*) FROM sec01_admissions").fetchone()[0]
