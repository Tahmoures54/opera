"""OPERA Readiness / Certificate Engine.

Independent implementation of Mechanical Completion (MC), Ready-for-Commissioning
(RFC) and Ready-for-Start-Up (RFSU) evaluation gates.

Inspired by public OPERCOM / ICAPS handover concepts (system-subsystem approach,
punch clearance, check-sheet completion) but uses only OPERA models and
project-configurable rules. No proprietary ICAPS schema or form is copied.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from extensions import db
from models_commissioning import (
    CheckSheet,
    CheckSheetStatus,
    CheckSheetType,
    CommissioningSubsystem,
    CommissioningTask,
    CommissioningTaskStatus,
    PunchCategory,
    PunchItem,
    PunchStatus,
    WitnessPoint,
    WitnessStatus,
    WitnessType,
)


@dataclass
class ReadinessIssue:
    code: str
    severity: str  # BLOCKER | WARNING
    message: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None


@dataclass
class ReadinessResult:
    subsystem_id: int
    company_name: str
    is_ready_for_mc: bool = False
    is_ready_for_rfc: bool = False
    is_ready_for_rfsu: bool = False
    progress_percent: float = 0.0
    issues: List[ReadinessIssue] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def is_ready_for_rf(self) -> bool:
        """Deprecated compatibility alias for the RFC readiness flag."""
        return self.is_ready_for_rfc

    @is_ready_for_rf.setter
    def is_ready_for_rf(self, value: bool) -> None:
        self.is_ready_for_rfc = value

    def add_blocker(self, code: str, message: str, entity_type: str = None, entity_id: int = None):
        self.issues.append(ReadinessIssue(code, "BLOCKER", message, entity_type, entity_id))

    def add_warning(self, code: str, message: str, entity_type: str = None, entity_id: int = None):
        self.issues.append(ReadinessIssue(code, "WARNING", message, entity_type, entity_id))


def _open_blocking_punches(company_name: str, subsystem_id: int):
    """Punch A and B that are still open block MC / RFSU in typical OPERCOM practice."""
    return (
        PunchItem.query.filter_by(company_name=company_name, subsystem_id=subsystem_id)
        .filter(PunchItem.category.in_([PunchCategory.A, PunchCategory.B]))
        .filter(PunchItem.status.in_([PunchStatus.OPEN, PunchStatus.IN_PROGRESS]))
        .all()
    )


def _unsigned_required_sheets(company_name: str, subsystem_id: int, sheet_types: List[CheckSheetType]):
    return (
        CheckSheet.query.filter_by(company_name=company_name, subsystem_id=subsystem_id)
        .filter(CheckSheet.sheet_type.in_(sheet_types))
        .filter(CheckSheet.status != CheckSheetStatus.SIGNED_OFF)
        .all()
    )


def _open_hold_points(company_name: str, subsystem_id: int):
    return (
        WitnessPoint.query.filter_by(company_name=company_name, subsystem_id=subsystem_id)
        .filter(WitnessPoint.witness_type == WitnessType.HOLD)
        .filter(WitnessPoint.status != WitnessStatus.RELEASED)
        .filter(WitnessPoint.status != WitnessStatus.CANCELLED)
        .all()
    )


def calculate_subsystem_progress(company_name: str, subsystem_id: int) -> float:
    """Weighted progress combining CheckSheet weights and Task completion.

    - CheckSheets contribute their sheet_weight when SIGNED_OFF.
    - Tasks contribute estimated_man_hours when COMPLETED (fallback weight 1.0).
    Empty denominator returns 0.0 (never fabricates progress).
    """
    sheets = CheckSheet.query.filter_by(company_name=company_name, subsystem_id=subsystem_id).all()
    tasks = CommissioningTask.query.filter_by(company_name=company_name, subsystem_id=subsystem_id).all()

    total_weight = 0.0
    earned_weight = 0.0

    for s in sheets:
        w = float(s.sheet_weight or 1.0)
        total_weight += w
        if s.status == CheckSheetStatus.SIGNED_OFF:
            earned_weight += w

    for t in tasks:
        w = float(t.estimated_man_hours or 1.0)
        total_weight += w
        if t.status == CommissioningTaskStatus.COMPLETED:
            earned_weight += w

    if total_weight <= 0:
        return 0.0
    return round(100.0 * earned_weight / total_weight, 2)


def evaluate_subsystem_readiness(company_name: str, subsystem_id: int) -> ReadinessResult:
    """Evaluate MC / RFC / RFSU readiness for one subsystem.

    Rules (OPERA defaults, project-overridable later):
    - MC requires: all Pre-Comm A/B sheets signed-off, no open Punch A/B, no open Hold points.
    - RFC requires: MC conditions + all Comm C / Functional Test sheets signed-off.
    - RFSU requires: RFC conditions + no remaining open Punch A/B and all tasks COMPLETED or CANCELLED.
    """
    subsystem = CommissioningSubsystem.query.filter_by(
        id=subsystem_id, company_name=company_name
    ).first()
    if subsystem is None:
        raise ValueError(f"Subsystem {subsystem_id} not found in tenant {company_name}")

    result = ReadinessResult(subsystem_id=subsystem_id, company_name=company_name)
    result.progress_percent = calculate_subsystem_progress(company_name, subsystem_id)

    # --- Punch blockers ---
    blocking_punches = _open_blocking_punches(company_name, subsystem_id)
    for p in blocking_punches:
        result.add_blocker(
            "OPEN_PUNCH_AB",
            f"Open Punch {p.category.value}-{p.punch_number}: {p.title or p.description or ''}",
            entity_type="punch",
            entity_id=p.id,
        )

    # --- Hold points ---
    open_holds = _open_hold_points(company_name, subsystem_id)
    for h in open_holds:
        result.add_blocker(
            "OPEN_HOLD",
            f"Hold point not released: {h.title or h.id}",
            entity_type="witness",
            entity_id=h.id,
        )

    # --- Pre-commissioning sheets (MC) ---
    precomm_types = [CheckSheetType.PRE_COMM_A, CheckSheetType.PRE_COMM_B]
    unsigned_pre = _unsigned_required_sheets(company_name, subsystem_id, precomm_types)
    for s in unsigned_pre:
        result.add_blocker(
            "UNSIGNED_PRECOMM",
            f"Pre-commissioning sheet not signed-off: {s.sheet_number} (rev {s.revision})",
            entity_type="check_sheet",
            entity_id=s.id,
        )

    # --- Commissioning sheets (RFC) ---
    comm_types = [CheckSheetType.COMM_C, CheckSheetType.FUNCTIONAL_TEST]
    unsigned_comm = _unsigned_required_sheets(company_name, subsystem_id, comm_types)
    for s in unsigned_comm:
        result.add_blocker(
            "UNSIGNED_COMM",
            f"Commissioning sheet not signed-off: {s.sheet_number} (rev {s.revision})",
            entity_type="check_sheet",
            entity_id=s.id,
        )

    # --- Tasks still active (RFSU) ---
    incomplete_tasks = (
        CommissioningTask.query.filter_by(company_name=company_name, subsystem_id=subsystem_id)
        .filter(CommissioningTask.status.notin_([
            CommissioningTaskStatus.COMPLETED,
            CommissioningTaskStatus.CANCELLED,
        ]))
        .all()
    )
    for t in incomplete_tasks:
        result.add_warning(
            "INCOMPLETE_TASK",
            f"Task not completed: {t.task_number} ({t.status.value})",
            entity_type="task",
            entity_id=t.id,
        )

    # Final gates
    has_punch_blockers = any(i.code == "OPEN_PUNCH_AB" for i in result.issues)
    has_hold_blockers = any(i.code == "OPEN_HOLD" for i in result.issues)
    has_precomm_blockers = any(i.code == "UNSIGNED_PRECOMM" for i in result.issues)
    has_comm_blockers = any(i.code == "UNSIGNED_COMM" for i in result.issues)
    has_task_warnings = any(i.code == "INCOMPLETE_TASK" for i in result.issues)

    result.is_ready_for_mc = not (has_punch_blockers or has_hold_blockers or has_precomm_blockers)
    result.is_ready_for_rf = result.is_ready_for_mc and not has_comm_blockers
    result.is_ready_for_rfsu = result.is_ready_for_rf and not has_task_warnings and not has_punch_blockers

    result.metrics = {
        "open_punch_ab_count": len(blocking_punches),
        "open_hold_count": len(open_holds),
        "unsigned_precomm_count": len(unsigned_pre),
        "unsigned_comm_count": len(unsigned_comm),
        "incomplete_task_count": len(incomplete_tasks),
        "progress_percent": result.progress_percent,
    }
    return result
