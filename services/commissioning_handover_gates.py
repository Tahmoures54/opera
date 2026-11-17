"""Thin integration layer between Handover transitions and the Readiness Engine.

Use these helpers inside blueprints/commissioning/workflow.py::transition_handover
to keep gate logic centralized and consistent with OPERCOM-style rules.
"""
from __future__ import annotations

from flask import abort

from services.commissioning_readiness import evaluate_subsystem_readiness, ReadinessResult


def _format_blockers(result: ReadinessResult, gate: str, limit: int = 8) -> str:
    blockers = [i for i in result.issues if i.severity == "BLOCKER" and i.gate == gate]
    if not blockers:
        return ""
    messages = "; ".join(i.message for i in blockers[:limit])
    if len(blockers) > limit:
        messages += f" (+{len(blockers) - limit} more)"
    return messages


def require_ready_for_mc(company_name: str, subsystem_id: int) -> ReadinessResult:
    """Abort with 409 if the subsystem is not ready for Mechanical Completion."""
    result = evaluate_subsystem_readiness(company_name, subsystem_id)
    if not result.is_ready_for_mc:
        msg = _format_blockers(result, "MC") or "Subsystem is not ready for MC"
        abort(409, description=f"MC certification blocked: {msg}")
    return result


def require_ready_for_rfc(company_name: str, subsystem_id: int) -> ReadinessResult:
    """Abort with 409 if the subsystem is not ready for Ready-for-Commissioning."""
    result = evaluate_subsystem_readiness(company_name, subsystem_id)
    if not result.is_ready_for_rfc:
        msg = _format_blockers(result, "RFC") or "Subsystem is not ready for RFC"
        abort(409, description=f"RFC certification blocked: {msg}")
    return result


def require_ready_for_rfsu(company_name: str, subsystem_id: int) -> ReadinessResult:
    """Abort with 409 if the subsystem is not ready for Ready-for-Start-Up."""
    result = evaluate_subsystem_readiness(company_name, subsystem_id)
    if not result.is_ready_for_rfsu:
        msg = _format_blockers(result, "RFSU") or "Subsystem is not ready for RFSU"
        # Also surface warnings for incomplete tasks
        warnings = [i.message for i in result.issues if i.severity == "WARNING" and i.gate == "RFSU"]
        if warnings:
            msg += " | Warnings: " + "; ".join(warnings[:5])
        abort(409, description=f"RFSU blocked: {msg}")
    return result


# Backward-compatible import for integrations that used the legacy RF name.
require_ready_for_rf = require_ready_for_rfc
