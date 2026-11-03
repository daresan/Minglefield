"""Durable, fail-closed cleanup progress records for an existing SQLite transaction.

The caller MUST hold a SQLite write transaction and validate owner, project,
operation, terminal install-journal state and plan digest independently.
No filesystem mutations or automatic crash replay are implemented here.
"""
import re

_NAME = re.compile(r"(?:blob-[0-9]{6}|manifest\.json)\Z")
_STATES = frozenset(("intent", "removed", "uncertain"))


def ensure_cleanup_progress_schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS sec01_game_install_cleanup_progress (
        operation_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        plan_sha256 TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('intent','removed','uncertain')),
        PRIMARY KEY(operation_id, filename)
    )""")


def begin_cleanup_file(db, operation_id, plan_sha256, filename):
    """Record intent before any deletion. An interrupted intent is uncertain."""
    if (not isinstance(operation_id, str) or not operation_id
            or not isinstance(plan_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", plan_sha256)
            or not isinstance(filename, str) or not _NAME.fullmatch(filename)):
        return {"state": "blocked", "reason": "invalid_cleanup_progress_key"}
    row = db.execute("""SELECT plan_sha256,state
        FROM sec01_game_install_cleanup_progress
        WHERE operation_id=? AND filename=?""",
        (operation_id, filename)).fetchone()
    if row is not None:
        if row[0] != plan_sha256:
            return {"state": "blocked", "reason": "cleanup_progress_plan_changed"}
        return {"state": "blocked", "reason": "cleanup_progress_already_recorded",
                "recorded_state": row[1]}
    db.execute("""INSERT INTO sec01_game_install_cleanup_progress
        (operation_id,filename,plan_sha256,state) VALUES(?,?,?,'intent')""",
        (operation_id, filename, plan_sha256))
    return {"state": "intent", "reason": "cleanup_intent_persist_pending_commit"}


def finish_cleanup_file(db, operation_id, plan_sha256, filename, *,
                        observed_deleted=False):
    """Only a trusted executor's successful native disposition may confirm.

    The caller must commit intent in a separate transaction BEFORE deletion.
    This function cannot independently attest a filesystem observation.
    """
    row = db.execute("""SELECT plan_sha256,state
        FROM sec01_game_install_cleanup_progress
        WHERE operation_id=? AND filename=?""",
        (operation_id, filename)).fetchone()
    if row is None or row[0] != plan_sha256 or row[1] != "intent":
        return {"state": "blocked", "reason": "cleanup_intent_not_current"}
    if observed_deleted is not True:
        db.execute("""UPDATE sec01_game_install_cleanup_progress
            SET state='uncertain' WHERE operation_id=? AND filename=?""",
            (operation_id, filename))
        return {"state": "uncertain", "reason": "manual_recovery_required"}
    db.execute("""UPDATE sec01_game_install_cleanup_progress
        SET state='removed' WHERE operation_id=? AND filename=?""",
        (operation_id, filename))
    return {"state": "removed", "reason": "native_disposition_reported"}


def inspect_cleanup_progress(db, operation_id, plan_sha256):
    """Read-only classification; no intent is ever automatically retried."""
    rows = db.execute("""SELECT filename,plan_sha256,state
        FROM sec01_game_install_cleanup_progress WHERE operation_id=?
        ORDER BY filename""", (operation_id,)).fetchall()
    if any(digest != plan_sha256 or state not in _STATES
           for _, digest, state in rows):
        return {"state": "blocked", "reason": "cleanup_progress_conflict"}
    uncertain = [name for name, _, state in rows if state != "removed"]
    return {"state": "manual_recovery_required" if uncertain else "recorded_snapshot",
            "reason": "unresolved_cleanup_intent" if uncertain else "progress_read_only",
            "removed_files": [name for name, _, state in rows if state == "removed"],
            "unresolved_files": uncertain, "auto_retry_allowed": False}
