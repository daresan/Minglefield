"""SEC-01 game-side reference transaction simulation, not a real adapter.

This is deliberately NOT networked. A trusted fixture installs an admission
receipt; a game-side transaction consumes it at most once and records a mock
effect. Receipt authenticity and distributed ordering remain unsolved.
"""
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GameApply:
    state: str
    reason: str


class MockTransactionalGame:
    def __init__(self, database):
        self.database = str(Path(database))
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_game_receipts (
                effect_key TEXT PRIMARY KEY, binding TEXT NOT NULL,
                audience TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_game_effects (
                effect_key TEXT PRIMARY KEY, binding TEXT NOT NULL,
                audience TEXT NOT NULL)""")
            db.commit()

    def install_trusted_fixture_receipt(self, *, effect_key, binding, audience):
        """TEST-ONLY: simulates a previously authenticated admission receipt.

        Never expose this method over a network or to an untrusted caller.
        """
        if not all(type(v) is str and 0 < len(v) <= 256
                   for v in (effect_key, binding, audience)):
            raise ValueError("invalid fixture receipt")
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""INSERT INTO sec01_game_receipts VALUES (?,?,?)""",
                       (effect_key, binding, audience))
            db.commit()

    def apply(self, *, effect_key, binding, audience):
        """Atomic mock receipt consumption and mock-effect record, no effects."""
        if not all(type(v) is str and 0 < len(v) <= 256
                   for v in (effect_key, binding, audience)):
            return GameApply("denied", "invalid_binding")
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            db.execute("BEGIN IMMEDIATE")
            receipt = db.execute("""SELECT binding,audience FROM sec01_game_receipts
                WHERE effect_key=?""", (effect_key,)).fetchone()
            if receipt is None:
                return GameApply("denied", "missing_admission_receipt")
            if receipt != (binding, audience):
                return GameApply("denied", "receipt_binding_mismatch")
            existing = db.execute("""SELECT binding,audience FROM sec01_game_effects
                WHERE effect_key=?""", (effect_key,)).fetchone()
            if existing is not None:
                return GameApply("duplicate", "historical_mock_effect_only")
            db.execute("""INSERT INTO sec01_game_effects VALUES (?,?,?)""",
                       (effect_key, binding, audience))
            db.commit()
            return GameApply("applied_mock", "mock_transaction_only")

    def effect_count(self):
        with closing(sqlite3.connect(self.database, timeout=10)) as db:
            return db.execute("SELECT COUNT(*) FROM sec01_game_effects").fetchone()[0]
