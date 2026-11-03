"""P1.4f.4 journal state vocabulary; no executor or file mutation exists yet."""


def initial_journal_state():
    return "prepared"


def recovery_classification(state):
    """An interrupted operation is never automatically replayed."""
    if state == "prepared":
        return {"state": state, "auto_retry_allowed": False,
                "recovery_action": "explicit_cancel_or_review"}
    if state in ("applying", "rollback_required"):
        return {"state": "manual_recovery_required",
                "auto_retry_allowed": False,
                "recovery_action": "inspect_files_and_journal"}
    if state in ("committed", "rolled_back"):
        return {"state": state, "auto_retry_allowed": False,
                "recovery_action": "none"}
    return {"state": "manual_recovery_required",
            "auto_retry_allowed": False,
            "recovery_action": "unknown_journal_state"}
