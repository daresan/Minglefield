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
    if state in ("committed", "rolled_back", "cancelled"):
        return {"state": state, "auto_retry_allowed": False,
                "recovery_action": "none"}
    return {"state": "manual_recovery_required",
            "auto_retry_allowed": False,
            "recovery_action": "unknown_journal_state"}


# Explicit transition policy for the future durable executor. No transition here
# changes files or database state. An interrupted write must never auto-commit.
_ALLOWED_TRANSITIONS = {
    "prepared": frozenset({"applying", "cancelled"}),
    "applying": frozenset({"committed", "rollback_required"}),
    "rollback_required": frozenset({"rolled_back", "manual_recovery_required"}),
    "manual_recovery_required": frozenset({"rolled_back"}),
    "committed": frozenset(),
    "rolled_back": frozenset(),
    "cancelled": frozenset(),
}


def inspect_journal_transition(current_state, requested_state, *,
                               owner_authorized=False, plan_verified=False):
    """Pure state-machine guard; executor must atomically persist transitions.

    Applying and committing additionally require independently reverified plan
    evidence. Unknown states and transitions fail closed.
    """
    def blocked(reason):
        return {"state": "blocked", "reason": reason,
                "mutation_performed": False}
    if current_state not in _ALLOWED_TRANSITIONS:
        return blocked("unknown_current_journal_state")
    if requested_state not in _ALLOWED_TRANSITIONS[current_state]:
        return blocked("invalid_journal_transition")
    if owner_authorized is not True:
        return blocked("owner_authorization_required")
    if requested_state in ("applying", "committed") and plan_verified is not True:
        return blocked("verified_plan_required")
    return {"state": "transition_permitted", "from": current_state,
            "to": requested_state, "mutation_performed": False}
