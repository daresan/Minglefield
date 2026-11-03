"""Pure, fail-closed P1.4f.3 preview assessment classifiers.

The caller must authenticate provenance; payload flags are never evidence by themselves.
No I/O, installation, or trust promotion is performed here.
"""


def assess_compatibility(contract=None, *, trusted_contract=False,
                         release_bound=False, target_facts_verified=False,
                         requirements_satisfied=None):
    if trusted_contract is not True or release_bound is not True:
        return {"state": "unknown", "reason": "no_verified_compatibility_contract",
                "requires_manual_review": True}
    if not isinstance(contract, dict) or contract.get("contract_version") != "0.1":
        return {"state": "unknown", "reason": "invalid_compatibility_contract",
                "requires_manual_review": True}
    if target_facts_verified is not True or type(requirements_satisfied) is not bool:
        return {"state": "unknown", "reason": "target_compatibility_not_verified",
                "requires_manual_review": True}
    if not requirements_satisfied:
        return {"state": "incompatible", "reason": "requirements_not_satisfied",
                "requires_manual_review": True}
    return {"state": "compatible", "reason": "verified_requirements_satisfied",
            "requires_manual_review": False}


def assess_migration(plan=None, *, trusted_plan=False, release_bound=False,
                     prerequisites_verified=False, recovery_verified=False):
    if trusted_plan is not True or release_bound is not True:
        return {"state": "unknown", "reason": "no_verified_migration_plan",
                "requires_manual_review": True}
    if not isinstance(plan, dict) or plan.get("plan_version") != "0.1":
        return {"state": "unknown", "reason": "invalid_migration_plan",
                "requires_manual_review": True}
    if prerequisites_verified is not True or recovery_verified is not True:
        return {"state": "unknown", "reason": "migration_prerequisites_or_recovery_unverified",
                "requires_manual_review": True}
    return {"state": "review_required", "reason": "migration_plan_requires_owner_approval",
            "requires_manual_review": True}
