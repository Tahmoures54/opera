"""Validation and defaults for project-specific commissioning readiness rules."""
from __future__ import annotations

from copy import deepcopy

from models_commissioning import CheckSheetType, CommissioningTaskType, PunchCategory

GATES = ("MC", "RFC", "RFSU")

DEFAULT_READINESS_POLICY = {
    "punch_blocking_categories": {
        "MC": ["A", "B"],
        "RFC": ["A", "B"],
        "RFSU": ["A", "B"],
    },
    "hold_point_blocking_gates": ["MC", "RFC", "RFSU"],
    "required_check_sheet_types": {
        "MC": ["PRE_COMM_A", "PRE_COMM_B"],
        "RFC": ["PRE_COMM_A", "PRE_COMM_B", "COMM_C", "FUNCTIONAL_TEST"],
        "RFSU": ["PRE_COMM_A", "PRE_COMM_B", "COMM_C", "FUNCTIONAL_TEST"],
    },
    "require_check_sheet_presence": False,
    "require_all_tasks_complete_for_rfsu": True,
    # Activity types whose incomplete tasks block MC. Empty by default so
    # existing projects keep their behaviour until the project opts in.
    "mc_required_task_types": [],
    # Gates that require at least one registered sheet of every selected type.
    # MC requires Pre-Comm presence by default; RFC and RFSU keep the previous behaviour.
    "presence_required_gates": ["MC"],
}


def normalize_readiness_policy(raw):
    """Return a fully populated policy and validation errors.

    Missing configuration preserves the historical OPERA defaults. Invalid
    persisted values are reported so readiness can fail closed.
    """
    policy = deepcopy(DEFAULT_READINESS_POLICY)
    if raw is None:
        return policy, []
    if not isinstance(raw, dict):
        return policy, ["Readiness policy must be a JSON object"]

    errors = []
    punch_values = {item.value for item in PunchCategory}
    sheet_values = {item.value for item in CheckSheetType}

    supplied_punch = raw.get("punch_blocking_categories", {})
    if not isinstance(supplied_punch, dict):
        errors.append("Punch blocking categories must be an object")
    else:
        for gate in GATES:
            if gate not in supplied_punch:
                continue
            values = supplied_punch[gate]
            if not isinstance(values, list) or any(not isinstance(value, str) or value not in punch_values for value in values):
                errors.append(f"Invalid Punch categories for {gate}")
            else:
                policy["punch_blocking_categories"][gate] = sorted(set(values))

    supplied_holds = raw.get("hold_point_blocking_gates", policy["hold_point_blocking_gates"])
    if not isinstance(supplied_holds, list) or any(not isinstance(value, str) or value not in GATES for value in supplied_holds):
        errors.append("Invalid Hold-point blocking gates")
    else:
        policy["hold_point_blocking_gates"] = sorted(set(supplied_holds))

    supplied_sheets = raw.get("required_check_sheet_types", {})
    if not isinstance(supplied_sheets, dict):
        errors.append("Required Check Sheet types must be an object")
    else:
        for gate in GATES:
            if gate not in supplied_sheets:
                continue
            values = supplied_sheets[gate]
            if not isinstance(values, list) or any(not isinstance(value, str) or value not in sheet_values for value in values):
                errors.append(f"Invalid required Check Sheet types for {gate}")
            else:
                policy["required_check_sheet_types"][gate] = sorted(set(values))

    if "presence_required_gates" in raw:
        supplied_presence = raw["presence_required_gates"]
        if not isinstance(supplied_presence, list) or any(
            not isinstance(value, str) or value not in GATES for value in supplied_presence
        ):
            errors.append("Invalid presence-required gates")
        else:
            policy["presence_required_gates"] = sorted(set(supplied_presence))

    task_values = {item.value for item in CommissioningTaskType}
    if "mc_required_task_types" in raw:
        supplied_tasks = raw["mc_required_task_types"]
        if not isinstance(supplied_tasks, list) or any(
            not isinstance(value, str) or value not in task_values for value in supplied_tasks
        ):
            errors.append("Invalid MC task types")
        else:
            policy["mc_required_task_types"] = sorted(set(supplied_tasks))

    for key in ("require_check_sheet_presence", "require_all_tasks_complete_for_rfsu"):
        if key in raw:
            if not isinstance(raw[key], bool):
                errors.append(f"{key} must be a boolean")
            else:
                policy[key] = raw[key]

    return policy, errors
