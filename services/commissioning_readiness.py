"""OPERA Readiness / Certificate Engine.

Independent implementation of MC, RFC and RFSU gates. Project policy is
stored with the project and validated before use; no ICAPS proprietary schema
or acceptance rule is copied.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from extensions import db
from models_commissioning import (
    CheckSheet,
    CheckSheetStatus,
    CommissioningAttachment,
    CommissioningDocument,
    CommissioningDossierRequirement,
    CommissioningEquipment,
    CommissioningProject,
    CommissioningSubsystem,
    CommissioningSystem,
    CommissioningTask,
    CommissioningTaskStatus,
    DocumentStatus,
    PunchItem,
    PunchStatus,
    WitnessPoint,
    WitnessStatus,
    WitnessType,
)
from services.commissioning_readiness_policy import (
    DEFAULT_READINESS_POLICY,
    GATES,
    normalize_readiness_policy,
)


@dataclass
class ReadinessIssue:
    code: str
    severity: str  # BLOCKER | WARNING
    message: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    gate: Optional[str] = None


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
        """Deprecated compatibility alias for RFC readiness."""
        return self.is_ready_for_rfc

    @is_ready_for_rf.setter
    def is_ready_for_rf(self, value: bool) -> None:
        self.is_ready_for_rfc = value

    def add_blocker(self, code, message, entity_type=None, entity_id=None, gate=None):
        self.issues.append(ReadinessIssue(code, "BLOCKER", message, entity_type, entity_id, gate))

    def add_warning(self, code, message, entity_type=None, entity_id=None, gate=None):
        self.issues.append(ReadinessIssue(code, "WARNING", message, entity_type, entity_id, gate))


def calculate_subsystem_progress(company_name: str, subsystem_id: int) -> float:
    """Weighted progress from signed Check Sheets and completed Tasks.

    Empty denominators return 0.0. If every task has zero estimated hours,
    each task receives a unit weight rather than silently disappearing.
    """
    sheets = CheckSheet.query.filter_by(company_name=company_name, subsystem_id=subsystem_id).all()
    tasks = CommissioningTask.query.filter_by(company_name=company_name, subsystem_id=subsystem_id).all()

    total_weight = 0.0
    earned_weight = 0.0
    for sheet in sheets:
        weight = float(sheet.sheet_weight or 1.0)
        total_weight += weight
        if sheet.status == CheckSheetStatus.SIGNED_OFF:
            earned_weight += weight

    for task in tasks:
        weight = float(task.estimated_man_hours or 1.0)
        total_weight += weight
        if task.status == CommissioningTaskStatus.COMPLETED:
            earned_weight += weight

    if total_weight <= 0:
        return 0.0
    return round(100.0 * earned_weight / total_weight, 2)


def _load_project_policy(company_name: str, subsystem: CommissioningSubsystem):
    system = CommissioningSystem.query.filter_by(
        id=subsystem.system_id, company_name=company_name,
    ).first()
    if system is None:
        return DEFAULT_READINESS_POLICY, ["Subsystem system reference is missing"]
    project = CommissioningProject.query.filter_by(
        id=system.project_id, company_name=company_name,
    ).first()
    if project is None:
        return DEFAULT_READINESS_POLICY, ["Subsystem project reference is missing"]
    return normalize_readiness_policy(project.readiness_policy_json)


def _open_hold_points(company_name: str, subsystem_id: int):
    return (
        WitnessPoint.query.join(CheckSheet, CheckSheet.id == WitnessPoint.check_sheet_id)
        .filter(
            WitnessPoint.company_name == company_name,
            CheckSheet.company_name == company_name,
            CheckSheet.subsystem_id == subsystem_id,
            WitnessPoint.type == WitnessType.HOLD,
            WitnessPoint.status.notin_([WitnessStatus.RELEASED, WitnessStatus.CANCELLED]),
        )
        .all()
    )


def _document_requirement_shortfalls(company_name: str, subsystem: CommissioningSubsystem) -> List[str]:
    """Unmet project dossier document rules for one subsystem, using the dossier export rules.

    Only the latest revision of each document number counts. A rule passes when
    enough matching documents are approved (if required) and have evidence (if
    required). Projects without dossier rules are not affected.
    """
    system = CommissioningSystem.query.filter_by(id=subsystem.system_id, company_name=company_name).first()
    if system is None:
        return []
    rules = CommissioningDossierRequirement.query.filter_by(
        company_name=company_name, project_id=system.project_id, is_active=True,
    ).all()
    if not rules:
        return []

    documents = CommissioningDocument.query.filter_by(
        company_name=company_name, project_id=system.project_id, subsystem_id=subsystem.id,
    ).order_by(
        CommissioningDocument.document_number,
        CommissioningDocument.revision_sequence.desc(),
    ).all()
    latest = {}
    for document in documents:
        latest.setdefault(document.document_number, document)
    latest_documents = list(latest.values())

    evidence_ids = {
        row.entity_id for row in CommissioningAttachment.query.filter(
            CommissioningAttachment.company_name == company_name,
            CommissioningAttachment.entity_type == "CommissioningDocument",
            CommissioningAttachment.entity_id.in_([doc.id for doc in latest_documents] or [-1]),
        ).all()
    }

    shortfalls = []
    for rule in rules:
        matching = [
            doc for doc in latest_documents
            if doc.document_type.strip().casefold() == rule.document_type.strip().casefold()
            and (rule.discipline == "ANY" or doc.discipline.strip().casefold() == rule.discipline.strip().casefold())
        ]
        qualifying = [
            doc for doc in matching
            if (not rule.require_approved or doc.status == DocumentStatus.APPROVED)
            and (not rule.require_evidence or doc.id in evidence_ids)
        ]
        if len(qualifying) < rule.minimum_count:
            shortfalls.append(
                f"Dossier document requirement not met: {rule.document_type} / {rule.discipline} "
                f"({len(qualifying)} of {rule.minimum_count} qualifying)"
            )
    return shortfalls


def evaluate_subsystem_readiness(company_name: str, subsystem_id: int) -> ReadinessResult:
    """Evaluate project-configured MC, RFC and RFSU readiness for one subsystem.

    Policy controls blocking Punch categories, required Check Sheet types,
    Hold-point gates and the RFSU task-completion requirement. Defaults retain
    the previous OPERA A/B, Check Sheet and Hold-point behavior.
    """
    subsystem = CommissioningSubsystem.query.filter_by(
        id=subsystem_id, company_name=company_name
    ).first()
    if subsystem is None:
        raise ValueError(f"Subsystem {subsystem_id} not found in tenant {company_name}")

    result = ReadinessResult(subsystem_id=subsystem_id, company_name=company_name)
    result.progress_percent = calculate_subsystem_progress(company_name, subsystem_id)
    policy, policy_errors = _load_project_policy(company_name, subsystem)

    punches = (
        PunchItem.query.filter_by(company_name=company_name, subsystem_id=subsystem_id)
        .filter(PunchItem.status.in_([PunchStatus.OPEN, PunchStatus.IN_PROGRESS]))
        .all()
    )
    holds = _open_hold_points(company_name, subsystem_id)
    sheets = CheckSheet.query.filter_by(
        company_name=company_name, subsystem_id=subsystem_id,
    ).all()
    tasks = CommissioningTask.query.filter_by(
        company_name=company_name, subsystem_id=subsystem_id,
    ).all()

    mc_document_shortfalls = _document_requirement_shortfalls(company_name, subsystem)
    mc_blocking_equipment = []
    if policy["mc_blocking_equipment_statuses"]:
        mc_blocking_equipment = CommissioningEquipment.query.filter(
            CommissioningEquipment.company_name == company_name,
            CommissioningEquipment.subsystem_id == subsystem_id,
            CommissioningEquipment.status.in_(policy["mc_blocking_equipment_statuses"]),
        ).all()

    gate_ready = {}
    gate_metrics = {}

    for gate in GATES:
        gate_issue_count = 0
        if policy_errors:
            for error in policy_errors:
                result.add_blocker("INVALID_READINESS_POLICY", error, gate=gate)
                gate_issue_count += 1

        blocking_categories = set(policy["punch_blocking_categories"][gate])
        gate_punches = [p for p in punches if p.category.value in blocking_categories]
        for punch in gate_punches:
            result.add_blocker(
                "OPEN_BLOCKING_PUNCH",
                f"Open Punch {punch.category.value}-{punch.punch_number}: {punch.description or ''}",
                entity_type="punch", entity_id=punch.id, gate=gate,
            )
            gate_issue_count += 1

        gate_holds = holds if gate in policy["hold_point_blocking_gates"] else []
        for hold in gate_holds:
            result.add_blocker(
                "OPEN_HOLD",
                f"Hold point not released (witness record #{hold.id})",
                entity_type="witness", entity_id=hold.id, gate=gate,
            )
            gate_issue_count += 1

        required_types = set(policy["required_check_sheet_types"][gate])
        required_sheets = [s for s in sheets if s.sheet_type.value in required_types]
        unsigned_sheets = [s for s in required_sheets if s.status != CheckSheetStatus.SIGNED_OFF]
        for sheet in unsigned_sheets:
            result.add_blocker(
                "UNSIGNED_REQUIRED_CHECK_SHEET",
                f"Required Check Sheet not signed off: {sheet.sheet_number} (rev {sheet.revision})",
                entity_type="check_sheet", entity_id=sheet.id, gate=gate,
            )
            gate_issue_count += 1

        if policy["require_check_sheet_presence"] or gate in policy["presence_required_gates"]:
            present_types = {s.sheet_type.value for s in required_sheets}
            for missing_type in sorted(required_types - present_types):
                result.add_blocker(
                    "MISSING_REQUIRED_CHECK_SHEET",
                    f"Required Check Sheet type is not registered: {missing_type}",
                    gate=gate,
                )
                gate_issue_count += 1

        incomplete_tasks = [
            task for task in tasks
            if task.status not in (CommissioningTaskStatus.COMPLETED, CommissioningTaskStatus.CANCELLED)
        ]
        if gate == "RFSU" and policy["require_all_tasks_complete_for_rfsu"]:
            for task in incomplete_tasks:
                result.add_blocker(
                    "INCOMPLETE_TASK",
                    f"Task not completed: {task.task_number} ({task.status.value})",
                    entity_type="task", entity_id=task.id, gate=gate,
                )
                gate_issue_count += 1
        elif gate == "RFSU":
            for task in incomplete_tasks:
                result.add_warning(
                    "INCOMPLETE_TASK",
                    f"Task not completed: {task.task_number} ({task.status.value})",
                    entity_type="task", entity_id=task.id, gate=gate,
                )

        gate_task_count = len(incomplete_tasks) if gate == "RFSU" else 0
        if gate == "MC":
            mc_task_types = set(policy["mc_required_task_types"])
            mc_blocking_tasks = [
                task for task in incomplete_tasks
                if task.activity_type.value in mc_task_types
            ]
            for task in mc_blocking_tasks:
                result.add_blocker(
                    "INCOMPLETE_TASK",
                    f"MC task not completed: {task.task_number} ({task.activity_type.value}, {task.status.value})",
                    entity_type="task", entity_id=task.id, gate=gate,
                )
                gate_issue_count += 1
            gate_task_count = len(mc_blocking_tasks)
            for message in mc_document_shortfalls:
                result.add_blocker("MC_DOCUMENT_REQUIREMENT_UNMET", message, gate=gate)
                gate_issue_count += 1
            for equipment in mc_blocking_equipment:
                result.add_blocker(
                    "MC_EQUIPMENT_NOT_READY",
                    f"Equipment {equipment.tag_number} status is {equipment.status}",
                    entity_type="equipment", entity_id=equipment.id, gate=gate,
                )
                gate_issue_count += 1

        gate_ready[gate] = gate_issue_count == 0
        gate_metrics[gate] = {
            "blocking_punch_count": len(gate_punches),
            "blocking_hold_count": len(gate_holds),
            "unsigned_check_sheet_count": len(unsigned_sheets),
            "incomplete_task_count": gate_task_count,
            "required_check_sheet_count": len(required_sheets),
        }

    result.is_ready_for_mc = gate_ready["MC"]
    result.is_ready_for_rfc = gate_ready["RFC"]
    result.is_ready_for_rfsu = gate_ready["RFSU"]
    result.metrics = {
        "open_punch_ab_count": sum(1 for punch in punches if punch.category.value in {"A", "B"}),
        "open_hold_count": len(holds),
        "unsigned_precomm_count": sum(
            1 for sheet in sheets
            if sheet.sheet_type.value in {"PRE_COMM_A", "PRE_COMM_B"}
            and sheet.status != CheckSheetStatus.SIGNED_OFF
        ),
        "unsigned_comm_count": sum(
            1 for sheet in sheets
            if sheet.sheet_type.value in {"COMM_C", "FUNCTIONAL_TEST"}
            and sheet.status != CheckSheetStatus.SIGNED_OFF
        ),
        "incomplete_task_count": gate_metrics["RFSU"]["incomplete_task_count"],
        "progress_percent": result.progress_percent,
        "by_gate": gate_metrics,
    }
    return result
