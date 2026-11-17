"""OPERA commissioning domain models.

All records are tenant-scoped by the OPERA company boundary.
Workflow transitions and cross-tenant authorization are enforced by services
and blueprints; database constraints additionally protect tenant-local keys.
"""
from datetime import datetime
import enum

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.orm import synonym
from extensions import db


def _enum(enum_class, name, length=None):
    options = {
        "name": name,
        "native_enum": False,
        "values_callable": lambda values: [item.value for item in values],
        "validate_strings": True,
    }
    if length is not None:
        options["length"] = length
    return db.Enum(enum_class, **options)


class ProjectStatus(enum.Enum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CommissioningTaskType(enum.Enum):
    CCK = "CCK"  # Conformity Check
    STS = "STS"  # Static Test
    PIP = "PIP"  # Piping Test
    PRC = "PRC"  # Preliminary Check
    FTS = "FTS"  # Functional Test
    OTS = "OTS"  # Operational Test
    PVP = "PVP"  # Piping & Vessel Preparation


class CommissioningTaskStatus(enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CheckSheetType(enum.Enum):
    PRE_COMM_A = "PRE_COMM_A"
    PRE_COMM_B = "PRE_COMM_B"
    COMM_C = "COMM_C"
    FUNCTIONAL_TEST = "FUNCTIONAL_TEST"


class CheckSheetStatus(enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    IN_PROGRESS = "IN_PROGRESS"
    SIGNED_OFF = "SIGNED_OFF"
    REJECTED = "REJECTED"


class ItemResultStatus(enum.Enum):
    PENDING = "PENDING"
    OK = "OK"
    NOK = "NOK"
    NA = "NA"


class DocumentStatus(enum.Enum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class PunchCategory(enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class PunchStatus(enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"
    VERIFIED = "VERIFIED"
    WAIVED = "WAIVED"


class PunchSeverity(enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WitnessType(enum.Enum):
    WITNESS = "WITNESS"
    HOLD = "HOLD"
    REVIEW = "REVIEW"


class WitnessStatus(enum.Enum):
    PLANNED = "PLANNED"
    NOTIFIED = "NOTIFIED"
    ATTENDED = "ATTENDED"
    RELEASED = "RELEASED"
    CANCELLED = "CANCELLED"


class HandoverStatus(enum.Enum):
    DRAFT = "DRAFT"
    MC_PENDING = "MC_PENDING"
    MC_CERTIFIED = "MC_CERTIFIED"
    RFC_PENDING = "RFC_PENDING"
    RF_PENDING = "RFC_PENDING"  # Backward-compatible Python alias
    RFC_CERTIFIED = "RFC_CERTIFIED"
    RF_CERTIFIED = "RFC_CERTIFIED"  # Backward-compatible Python alias
    RFSU = "RFSU"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class MembershipRole(enum.Enum):
    COMMISSIONING_MANAGER = "commissioning_manager"
    COMMISSIONING_ENGINEER = "commissioning_engineer"
    QC_INSPECTOR = "qc_inspector"
    CLIENT_REPRESENTATIVE = "client_representative"
    OPERATIONS_LEAD = "operations_lead"
    VIEWER = "viewer"


class CommissioningProject(db.Model):
    __tablename__ = "commissioning_project"
    __table_args__ = (
        UniqueConstraint("company_name", "project_code", name="uq_comm_project_company_code"),
        UniqueConstraint("id", "company_name", name="uq_comm_project_id_company"),
        Index("ix_comm_project_company_status", "company_name", "status"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    client = db.Column(db.String(200))
    contractor = db.Column(db.String(200))
    start_date = db.Column(db.Date)
    target_end_date = db.Column(db.Date)
    status = db.Column(_enum(ProjectStatus, "commissioning_project_status"), nullable=False, default=ProjectStatus.PLANNING)
    description = db.Column(db.Text)
    readiness_policy_json = db.Column(db.JSON, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommissioningSystem(db.Model):
    __tablename__ = "commissioning_system"
    __table_args__ = (
        UniqueConstraint("company_name", "project_id", "system_code", name="uq_comm_system_code"),
        ForeignKeyConstraint(["project_id", "company_name"], ["commissioning_project.id", "commissioning_project.company_name"], name="fk_comm_system_project_tenant"),
        UniqueConstraint("id", "company_name", name="uq_comm_system_id_company"),
        CheckConstraint("weight_percent >= 0 AND weight_percent <= 100", name="ck_comm_system_weight"),
        Index("ix_comm_system_company_project", "company_name", "project_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    system_code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    p_and_id_ref = db.Column(db.String(200))
    weight_percent = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(30), nullable=False, default="ACTIVE")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommissioningSubsystem(db.Model):
    __tablename__ = "commissioning_subsystem"
    __table_args__ = (
        UniqueConstraint("company_name", "system_id", "subsystem_code", name="uq_comm_subsystem_code"),
        ForeignKeyConstraint(["system_id", "company_name"], ["commissioning_system.id", "commissioning_system.company_name"], name="fk_comm_subsystem_system_tenant"),
        UniqueConstraint("id", "company_name", name="uq_comm_subsystem_id_company"),
        CheckConstraint("weight_percent >= 0 AND weight_percent <= 100", name="ck_comm_subsystem_weight"),
        Index("ix_comm_subsystem_company_system", "company_name", "system_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    system_id = db.Column(db.Integer, db.ForeignKey("commissioning_system.id", ondelete="RESTRICT"), nullable=False)
    subsystem_code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    weight_percent = db.Column(db.Float, nullable=False, default=0.0)
    mc_target_date = db.Column(db.Date)
    rf_target_date = db.Column(db.Date)
    status = db.Column(db.String(30), nullable=False, default="ACTIVE")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommissioningEquipment(db.Model):
    __tablename__ = "commissioning_equipment"
    __table_args__ = (
        UniqueConstraint("company_name", "project_id", "tag_number", name="uq_comm_equipment_tag"),
        UniqueConstraint("id", "company_name", name="uq_comm_equipment_id_company"),
        ForeignKeyConstraint(["project_id", "company_name"], ["commissioning_project.id", "commissioning_project.company_name"], name="fk_comm_equipment_project_tenant"),
        ForeignKeyConstraint(["subsystem_id", "company_name"], ["commissioning_subsystem.id", "commissioning_subsystem.company_name"], name="fk_comm_equipment_subsystem_tenant"),
        Index("ix_comm_equipment_company_subsystem", "company_name", "subsystem_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    subsystem_id = db.Column(db.Integer, db.ForeignKey("commissioning_subsystem.id", ondelete="RESTRICT"), nullable=False)
    tag_number = db.Column(db.String(100), nullable=False)
    equipment_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    manufacturer = db.Column(db.String(150))
    model_number = db.Column(db.String(100))
    serial_no = db.Column(db.String(100))
    specs_json = db.Column(db.JSON)
    status = db.Column(db.String(30), nullable=False, default="ACTIVE")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)



class CommissioningTask(db.Model):
    """Project task register aligned to the documented ICAPS task branch concepts.

    Activity codes are evidenced in the available project ICAPS manual; the
    model is an independent OPERA implementation, not a copied ICAPS schema.
    """
    __tablename__ = "commissioning_task"
    __table_args__ = (
        UniqueConstraint("company_name", "task_number", name="uq_comm_task_number"),
        UniqueConstraint("id", "company_name", name="uq_comm_task_id_company"),
        ForeignKeyConstraint(["project_id", "company_name"], ["commissioning_project.id", "commissioning_project.company_name"], name="fk_comm_task_project_tenant"),
        ForeignKeyConstraint(["system_id", "company_name"], ["commissioning_system.id", "commissioning_system.company_name"], name="fk_comm_task_system_tenant"),
        ForeignKeyConstraint(["subsystem_id", "company_name"], ["commissioning_subsystem.id", "commissioning_subsystem.company_name"], name="fk_comm_task_subsystem_tenant"),
        ForeignKeyConstraint(["equipment_id", "company_name"], ["commissioning_equipment.id", "commissioning_equipment.company_name"], name="fk_comm_task_equipment_tenant"),
        ForeignKeyConstraint(["check_sheet_id", "company_name"], ["commissioning_check_sheet.id", "commissioning_check_sheet.company_name"], name="fk_comm_task_check_sheet_tenant"),
        CheckConstraint("estimated_man_hours >= 0", name="ck_comm_task_estimated_hours_nonnegative"),
        CheckConstraint("spent_man_hours >= 0", name="ck_comm_task_spent_hours_nonnegative"),
        Index("ix_comm_task_company_project_status", "company_name", "project_id", "status"),
        Index("ix_comm_task_company_subsystem_type", "company_name", "subsystem_id", "activity_type"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    system_id = db.Column(db.Integer, db.ForeignKey("commissioning_system.id", ondelete="RESTRICT"), nullable=False)
    subsystem_id = db.Column(db.Integer, db.ForeignKey("commissioning_subsystem.id", ondelete="RESTRICT"), nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey("commissioning_equipment.id", ondelete="RESTRICT"))
    check_sheet_id = db.Column(db.Integer, db.ForeignKey("commissioning_check_sheet.id", ondelete="RESTRICT"))
    task_number = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    activity_type = db.Column(_enum(CommissioningTaskType, "commissioning_task_type"), nullable=False)
    discipline = db.Column(db.String(80), nullable=False)
    progress_stage = db.Column(db.String(80))
    progress_substage = db.Column(db.String(80))
    assigned_group = db.Column(db.String(120))
    estimated_man_hours = db.Column(db.Float, nullable=False, default=0.0)
    spent_man_hours = db.Column(db.Float, nullable=False, default=0.0)
    planned_start_date = db.Column(db.Date)
    planned_finish_date = db.Column(db.Date)
    actual_start_date = db.Column(db.Date)
    actual_finish_date = db.Column(db.Date)
    status = db.Column(_enum(CommissioningTaskStatus, "commissioning_task_status"), nullable=False, default=CommissioningTaskStatus.NOT_STARTED)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommissioningTaskDependency(db.Model):
    """Finish-to-start predecessor link between tasks in the same project."""
    __tablename__ = "commissioning_task_dependency"
    __table_args__ = (
        UniqueConstraint("company_name", "predecessor_task_id", "successor_task_id",
                         name="uq_comm_task_dependency_pair"),
        ForeignKeyConstraint(["project_id", "company_name"],
                             ["commissioning_project.id", "commissioning_project.company_name"],
                             name="fk_comm_task_dependency_project_tenant"),
        ForeignKeyConstraint(["predecessor_task_id", "company_name"],
                             ["commissioning_task.id", "commissioning_task.company_name"],
                             name="fk_comm_task_dependency_predecessor_tenant"),
        ForeignKeyConstraint(["successor_task_id", "company_name"],
                             ["commissioning_task.id", "commissioning_task.company_name"],
                             name="fk_comm_task_dependency_successor_tenant"),
        CheckConstraint("predecessor_task_id != successor_task_id",
                        name="ck_comm_task_dependency_not_self"),
        CheckConstraint("lag_days >= 0", name="ck_comm_task_dependency_lag_nonnegative"),
        CheckConstraint("dependency_type = 'FINISH_TO_START'",
                        name="ck_comm_task_dependency_type_fs_only"),
        Index("ix_comm_task_dependency_project_successor",
              "company_name", "project_id", "successor_task_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    predecessor_task_id = db.Column(db.Integer, db.ForeignKey("commissioning_task.id", ondelete="RESTRICT"), nullable=False)
    successor_task_id = db.Column(db.Integer, db.ForeignKey("commissioning_task.id", ondelete="RESTRICT"), nullable=False)
    dependency_type = db.Column(db.String(20), nullable=False, default="FINISH_TO_START")
    lag_days = db.Column(db.Integer, nullable=False, default=0)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CheckSheet(db.Model):
    __tablename__ = "commissioning_check_sheet"
    __table_args__ = (
        UniqueConstraint("company_name", "sheet_number", "revision", name="uq_comm_check_sheet_revision"),
        UniqueConstraint("id", "company_name", name="uq_comm_check_sheet_id_company"),
        CheckConstraint("revision >= 0", name="ck_comm_check_revision_nonnegative"),
        CheckConstraint("sheet_weight > 0", name="ck_comm_check_sheet_weight_positive"),
        ForeignKeyConstraint(["project_id", "company_name"], ["commissioning_project.id", "commissioning_project.company_name"], name="fk_comm_check_project_tenant"),
        ForeignKeyConstraint(["system_id", "company_name"], ["commissioning_system.id", "commissioning_system.company_name"], name="fk_comm_check_system_tenant"),
        ForeignKeyConstraint(["subsystem_id", "company_name"], ["commissioning_subsystem.id", "commissioning_subsystem.company_name"], name="fk_comm_check_subsystem_tenant"),
        ForeignKeyConstraint(["equipment_id", "company_name"], ["commissioning_equipment.id", "commissioning_equipment.company_name"], name="fk_comm_check_equipment_tenant"),
        ForeignKeyConstraint(["supersedes_id", "company_name"], ["commissioning_check_sheet.id", "commissioning_check_sheet.company_name"], name="fk_comm_check_supersedes_tenant"),
        Index("ix_comm_check_company_project_status", "company_name", "project_id", "status"),
        Index("ix_comm_check_company_subsystem_type", "company_name", "subsystem_id", "sheet_type"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    system_id = db.Column(db.Integer, db.ForeignKey("commissioning_system.id", ondelete="RESTRICT"), nullable=False)
    subsystem_id = db.Column(db.Integer, db.ForeignKey("commissioning_subsystem.id", ondelete="RESTRICT"), nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey("commissioning_equipment.id", ondelete="RESTRICT"))
    sheet_number = db.Column(db.String(100), nullable=False)
    sheet_type = db.Column(_enum(CheckSheetType, "commissioning_check_sheet_type"), nullable=False)
    revision = db.Column(db.Integer, nullable=False, default=0)
    supersedes_id = db.Column(db.Integer, db.ForeignKey("commissioning_check_sheet.id", ondelete="RESTRICT"))
    sheet_weight = db.Column(db.Float, nullable=False, default=1.0)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(_enum(CheckSheetStatus, "commissioning_check_sheet_status"), nullable=False, default=CheckSheetStatus.DRAFT)
    issued_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    issued_at = db.Column(db.DateTime)
    signed_by_client_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    signed_by_contractor_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    signed_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CheckSheetItem(db.Model):
    __tablename__ = "commissioning_check_sheet_item"
    __table_args__ = (
        UniqueConstraint("company_name", "check_sheet_id", "sequence", name="uq_comm_check_item_sequence"),
        CheckConstraint("sequence >= 1", name="ck_comm_check_item_sequence_positive"),
        UniqueConstraint("id", "company_name", name="uq_comm_check_item_id_company"),
        ForeignKeyConstraint(["check_sheet_id", "company_name"], ["commissioning_check_sheet.id", "commissioning_check_sheet.company_name"], name="fk_comm_check_item_sheet_tenant"),
        Index("ix_comm_check_item_company_sheet", "company_name", "check_sheet_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    check_sheet_id = db.Column(db.Integer, db.ForeignKey("commissioning_check_sheet.id", ondelete="RESTRICT"), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    expected_result = db.Column(db.Text)
    actual_result = db.Column(db.Text)
    result_status = db.Column(_enum(ItemResultStatus, "commissioning_item_result_status"), nullable=False, default=ItemResultStatus.PENDING)
    witness_required = db.Column(db.Boolean, nullable=False, default=False)
    operator_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    verified_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    verified_at = db.Column(db.DateTime)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CheckSheetRevision(db.Model):
    __tablename__ = "commissioning_check_sheet_revision"
    __table_args__ = (UniqueConstraint("company_name", "sheet_number", "revision_number", name="uq_comm_revision_number"),
        ForeignKeyConstraint(["previous_check_sheet_id", "company_name"], ["commissioning_check_sheet.id", "commissioning_check_sheet.company_name"], name="fk_comm_revision_previous_tenant"),
        ForeignKeyConstraint(["new_check_sheet_id", "company_name"], ["commissioning_check_sheet.id", "commissioning_check_sheet.company_name"], name="fk_comm_revision_new_tenant"))
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    sheet_number = db.Column(db.String(100), nullable=False)
    previous_check_sheet_id = db.Column(db.Integer, db.ForeignKey("commissioning_check_sheet.id", ondelete="RESTRICT"), nullable=False)
    new_check_sheet_id = db.Column(db.Integer, db.ForeignKey("commissioning_check_sheet.id", ondelete="RESTRICT"), nullable=False)
    revision_number = db.Column(db.Integer, nullable=False)
    revision_reason = db.Column(db.Text, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class PunchItem(db.Model):
    __tablename__ = "commissioning_punch_item"
    __table_args__ = (
        UniqueConstraint("company_name", "punch_number", name="uq_comm_punch_number"),
        UniqueConstraint("id", "company_name", name="uq_comm_punch_id_company"),
        ForeignKeyConstraint(["project_id", "company_name"], ["commissioning_project.id", "commissioning_project.company_name"], name="fk_comm_punch_project_tenant"),
        ForeignKeyConstraint(["subsystem_id", "company_name"], ["commissioning_subsystem.id", "commissioning_subsystem.company_name"], name="fk_comm_punch_subsystem_tenant"),
        ForeignKeyConstraint(["equipment_id", "company_name"], ["commissioning_equipment.id", "commissioning_equipment.company_name"], name="fk_comm_punch_equipment_tenant"),
        ForeignKeyConstraint(["check_sheet_id", "company_name"], ["commissioning_check_sheet.id", "commissioning_check_sheet.company_name"], name="fk_comm_punch_sheet_tenant"),
        Index("ix_comm_punch_company_raised_at", "company_name", "raised_at"),
        Index("ix_comm_punch_company_project_status", "company_name", "project_id", "status"),
        Index("ix_comm_punch_company_category_status", "company_name", "category", "status"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    subsystem_id = db.Column(db.Integer, db.ForeignKey("commissioning_subsystem.id", ondelete="RESTRICT"), nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey("commissioning_equipment.id", ondelete="RESTRICT"))
    check_sheet_id = db.Column(db.Integer, db.ForeignKey("commissioning_check_sheet.id", ondelete="RESTRICT"))
    punch_number = db.Column(db.String(100), nullable=False)
    category = db.Column(_enum(PunchCategory, "commissioning_punch_category"), nullable=False)
    severity = db.Column(_enum(PunchSeverity, "commissioning_punch_severity"), nullable=False, default=PunchSeverity.MEDIUM)
    description = db.Column(db.Text, nullable=False)
    raised_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    raised_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    target_closure_date = db.Column(db.Date)
    corrective_action = db.Column(db.Text)
    status = db.Column(_enum(PunchStatus, "commissioning_punch_status"), nullable=False, default=PunchStatus.OPEN)
    closed_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    closed_at = db.Column(db.DateTime)
    verified_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    verified_at = db.Column(db.DateTime)
    waived_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    waived_at = db.Column(db.DateTime)
    waiver_reason = db.Column(db.Text)
    photos_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class PunchHistory(db.Model):
    __tablename__ = "commissioning_punch_history"
    __table_args__ = (Index("ix_comm_punch_history_company_item", "company_name", "punch_item_id"),
        ForeignKeyConstraint(["punch_item_id", "company_name"], ["commissioning_punch_item.id", "commissioning_punch_item.company_name"], name="fk_comm_punch_history_item_tenant"))
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    punch_item_id = db.Column(db.Integer, db.ForeignKey("commissioning_punch_item.id", ondelete="RESTRICT"), nullable=False)
    old_status = db.Column(_enum(PunchStatus, "commissioning_punch_old_status"))
    new_status = db.Column(_enum(PunchStatus, "commissioning_punch_new_status"), nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class WitnessPoint(db.Model):
    __tablename__ = "commissioning_witness_point"
    __table_args__ = (Index("ix_comm_witness_company_schedule", "company_name", "scheduled_at"),
        ForeignKeyConstraint(["project_id", "company_name"], ["commissioning_project.id", "commissioning_project.company_name"], name="fk_comm_witness_project_tenant"),
        ForeignKeyConstraint(["check_sheet_id", "company_name"], ["commissioning_check_sheet.id", "commissioning_check_sheet.company_name"], name="fk_comm_witness_sheet_tenant"),
        ForeignKeyConstraint(["check_sheet_item_id", "company_name"], ["commissioning_check_sheet_item.id", "commissioning_check_sheet_item.company_name"], name="fk_comm_witness_item_tenant"))
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    check_sheet_id = db.Column(db.Integer, db.ForeignKey("commissioning_check_sheet.id", ondelete="RESTRICT"), nullable=False)
    check_sheet_item_id = db.Column(db.Integer, db.ForeignKey("commissioning_check_sheet_item.id", ondelete="RESTRICT"))
    type = db.Column(_enum(WitnessType, "commissioning_witness_type"), nullable=False)
    notified_party = db.Column(db.String(200))
    scheduled_at = db.Column(db.DateTime, nullable=False)
    attended_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    attended_at = db.Column(db.DateTime)
    result = db.Column(db.String(30))
    remarks = db.Column(db.Text)
    released_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    released_at = db.Column(db.DateTime)
    status = db.Column(_enum(WitnessStatus, "commissioning_witness_status"), nullable=False, default=WitnessStatus.PLANNED)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class HandoverPackage(db.Model):
    __tablename__ = "commissioning_handover_package"
    __table_args__ = (
        UniqueConstraint("company_name", "package_number", name="uq_comm_handover_package_number"),
        UniqueConstraint("id", "company_name", name="uq_comm_handover_id_company"),
        ForeignKeyConstraint(["project_id", "company_name"], ["commissioning_project.id", "commissioning_project.company_name"], name="fk_comm_handover_project_tenant"),
        ForeignKeyConstraint(["subsystem_id", "company_name"], ["commissioning_subsystem.id", "commissioning_subsystem.company_name"], name="fk_comm_handover_subsystem_tenant"),
        Index("ix_comm_handover_company_subsystem_status", "company_name", "subsystem_id", "status"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    subsystem_id = db.Column(db.Integer, db.ForeignKey("commissioning_subsystem.id", ondelete="RESTRICT"), nullable=False)
    package_number = db.Column(db.String(100), nullable=False)
    mc_certificate_number = db.Column(db.String(100))
    rfc_certificate_number = db.Column("rf_certificate_number", db.String(100))
    rf_certificate_number = synonym("rfc_certificate_number")
    mc_certificate_date = db.Column(db.Date)
    rfc_certificate_date = db.Column("rf_certificate_date", db.Date)
    rf_certificate_date = synonym("rfc_certificate_date")
    mc_issued_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    rfc_issued_by_id = db.Column("rf_issued_by_id", db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    rf_issued_by_id = synonym("rfc_issued_by_id")
    accepted_by_operations = db.Column(db.Boolean, nullable=False, default=False)
    operations_accepted_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    operations_accepted_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    documents_json = db.Column(db.JSON)
    status = db.Column(_enum(HandoverStatus, "commissioning_handover_status", length=30), nullable=False, default=HandoverStatus.DRAFT)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommissioningCertificate(db.Model):
    """Immutable MC/RFC certificate and issue-time evidence snapshot."""
    __tablename__ = "commissioning_certificate"
    __table_args__ = (
        UniqueConstraint("company_name", "certificate_number",
                         name="uq_comm_certificate_company_number"),
        UniqueConstraint("company_name", "package_id", "certificate_type",
                         name="uq_comm_certificate_package_type"),
        ForeignKeyConstraint(["project_id", "company_name"],
                             ["commissioning_project.id", "commissioning_project.company_name"],
                             name="fk_comm_certificate_project_tenant"),
        ForeignKeyConstraint(["subsystem_id", "company_name"],
                             ["commissioning_subsystem.id", "commissioning_subsystem.company_name"],
                             name="fk_comm_certificate_subsystem_tenant"),
        ForeignKeyConstraint(["package_id", "company_name"],
                             ["commissioning_handover_package.id", "commissioning_handover_package.company_name"],
                             name="fk_comm_certificate_package_tenant"),
        CheckConstraint("certificate_type IN ('MC', 'RFC')",
                        name="ck_comm_certificate_type"),
        Index("ix_comm_certificate_company_project_date",
              "company_name", "project_id", "certificate_date"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    subsystem_id = db.Column(db.Integer, db.ForeignKey("commissioning_subsystem.id", ondelete="RESTRICT"), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey("commissioning_handover_package.id", ondelete="RESTRICT"), nullable=False)
    certificate_type = db.Column(db.String(3), nullable=False)
    certificate_number = db.Column(db.String(100), nullable=False)
    certificate_date = db.Column(db.Date, nullable=False)
    issued_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    issued_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    snapshot_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CommissioningDocument(db.Model):
    """One controlled revision of a project engineering document."""
    __tablename__ = "commissioning_document"
    __table_args__ = (
        UniqueConstraint("company_name", "project_id", "document_number", "revision_sequence",
                         name="uq_comm_document_revision_sequence"),
        UniqueConstraint("company_name", "project_id", "document_number", "revision",
                         name="uq_comm_document_revision"),
        UniqueConstraint("id", "company_name", name="uq_comm_document_id_company"),
        ForeignKeyConstraint(["project_id", "company_name"],
                             ["commissioning_project.id", "commissioning_project.company_name"],
                             name="fk_comm_document_project_tenant"),
        ForeignKeyConstraint(["system_id", "company_name"],
                             ["commissioning_system.id", "commissioning_system.company_name"],
                             name="fk_comm_document_system_tenant"),
        ForeignKeyConstraint(["subsystem_id", "company_name"],
                             ["commissioning_subsystem.id", "commissioning_subsystem.company_name"],
                             name="fk_comm_document_subsystem_tenant"),
        ForeignKeyConstraint(["equipment_id", "company_name"],
                             ["commissioning_equipment.id", "commissioning_equipment.company_name"],
                             name="fk_comm_document_equipment_tenant"),
        ForeignKeyConstraint(["supersedes_id", "company_name"],
                             ["commissioning_document.id", "commissioning_document.company_name"],
                             name="fk_comm_document_supersedes_tenant"),
        CheckConstraint("revision_sequence >= 1", name="ck_comm_document_revision_sequence"),
        Index("ix_comm_document_company_project_status", "company_name", "project_id", "status"),
        Index("ix_comm_document_company_number", "company_name", "document_number"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    system_id = db.Column(db.Integer, db.ForeignKey("commissioning_system.id", ondelete="RESTRICT"))
    subsystem_id = db.Column(db.Integer, db.ForeignKey("commissioning_subsystem.id", ondelete="RESTRICT"))
    equipment_id = db.Column(db.Integer, db.ForeignKey("commissioning_equipment.id", ondelete="RESTRICT"))
    document_number = db.Column(db.String(120), nullable=False)
    revision = db.Column(db.String(20), nullable=False, default="A")
    revision_sequence = db.Column(db.Integer, nullable=False, default=1)
    supersedes_id = db.Column(db.Integer, db.ForeignKey("commissioning_document.id", ondelete="RESTRICT"))
    title = db.Column(db.String(250), nullable=False)
    document_type = db.Column(db.String(80), nullable=False)
    discipline = db.Column(db.String(80), nullable=False)
    purpose = db.Column(db.String(80))
    status = db.Column(_enum(DocumentStatus, "commissioning_document_status"),
                       nullable=False, default=DocumentStatus.DRAFT)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    submitted_at = db.Column(db.DateTime)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommissioningDocumentReview(db.Model):
    """Append-only review decision for a specific document revision."""
    __tablename__ = "commissioning_document_review"
    __table_args__ = (
        ForeignKeyConstraint(["document_id", "company_name"],
                             ["commissioning_document.id", "commissioning_document.company_name"],
                             name="fk_comm_document_review_document_tenant"),
        Index("ix_comm_document_review_company_document", "company_name", "document_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey("commissioning_document.id", ondelete="RESTRICT"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    decision = db.Column(db.String(20), nullable=False)
    comments = db.Column(db.Text)
    decided_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CommissioningDossierRequirement(db.Model):
    """Project-level mandatory engineering-document index for each subsystem dossier."""
    __tablename__ = "commissioning_dossier_requirement"
    __table_args__ = (
        UniqueConstraint("company_name", "project_id", "document_type", "discipline",
                         name="uq_comm_dossier_requirement_scope"),
        ForeignKeyConstraint(["project_id", "company_name"],
                             ["commissioning_project.id", "commissioning_project.company_name"],
                             name="fk_comm_dossier_requirement_project_tenant"),
        CheckConstraint("minimum_count >= 1 AND minimum_count <= 1000",
                        name="ck_comm_dossier_requirement_minimum"),
        CheckConstraint("length(trim(document_type)) > 0",
                        name="ck_comm_dossier_requirement_type"),
        CheckConstraint("length(trim(discipline)) > 0",
                        name="ck_comm_dossier_requirement_discipline"),
        Index("ix_comm_dossier_requirement_project_active",
              "company_name", "project_id", "is_active"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    document_type = db.Column(db.String(80), nullable=False)
    discipline = db.Column(db.String(80), nullable=False, default="ANY")
    minimum_count = db.Column(db.Integer, nullable=False, default=1)
    require_approved = db.Column(db.Boolean, nullable=False, default=True)
    require_evidence = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommissioningPreservationPlan(db.Model):
    """Equipment preservation schedule based only on approved project/OEM instructions."""
    __tablename__ = "commissioning_preservation_plan"
    __table_args__ = (
        UniqueConstraint("company_name", "project_id", "plan_number",
                         name="uq_comm_preservation_plan_number"),
        UniqueConstraint("id", "company_name", name="uq_comm_preservation_plan_id_company"),
        ForeignKeyConstraint(["project_id", "company_name"],
                             ["commissioning_project.id", "commissioning_project.company_name"],
                             name="fk_comm_preservation_plan_project_tenant"),
        ForeignKeyConstraint(["equipment_id", "company_name"],
                             ["commissioning_equipment.id", "commissioning_equipment.company_name"],
                             name="fk_comm_preservation_plan_equipment_tenant"),
        CheckConstraint("interval_days > 0 AND interval_days <= 3650",
                        name="ck_comm_preservation_interval"),
        CheckConstraint("length(trim(plan_number)) > 0",
                        name="ck_comm_preservation_plan_number"),
        CheckConstraint("length(trim(procedure_reference)) > 0",
                        name="ck_comm_preservation_procedure_reference"),
        CheckConstraint("status IN ('ACTIVE','ACTION_REQUIRED','SUSPENDED','CLOSED')",
                        name="ck_comm_preservation_status"),
        Index("ix_comm_preservation_due", "company_name", "project_id", "status", "next_due_date"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey("commissioning_equipment.id", ondelete="RESTRICT"), nullable=False)
    plan_number = db.Column(db.String(80), nullable=False)
    activity = db.Column(db.String(200), nullable=False)
    procedure_reference = db.Column(db.String(150), nullable=False)
    procedure_revision = db.Column(db.String(50), nullable=False)
    interval_days = db.Column(db.Integer, nullable=False)
    next_due_date = db.Column(db.Date, nullable=False)
    last_performed_at = db.Column(db.Date)
    responsible_company = db.Column(db.String(150))
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    status = db.Column(db.String(30), nullable=False, default="ACTIVE")
    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    inspections = db.relationship(
        "CommissioningPreservationInspection", back_populates="plan",
        order_by="CommissioningPreservationInspection.performed_at.desc()",
        lazy="select",
    )


class CommissioningPreservationInspection(db.Model):
    """Append-only preservation inspection record with procedure/interval snapshot."""
    __tablename__ = "commissioning_preservation_inspection"
    __table_args__ = (
        UniqueConstraint("id", "company_name", name="uq_comm_preservation_inspection_id_company"),
        ForeignKeyConstraint(["project_id", "company_name"],
                             ["commissioning_project.id", "commissioning_project.company_name"],
                             name="fk_comm_preservation_inspection_project_tenant"),
        ForeignKeyConstraint(["plan_id", "company_name"],
                             ["commissioning_preservation_plan.id", "commissioning_preservation_plan.company_name"],
                             name="fk_comm_preservation_inspection_plan_tenant"),
        CheckConstraint("result IN ('COMPLIANT','NON_COMPLIANT','NOT_APPLICABLE')",
                        name="ck_comm_preservation_inspection_result"),
        CheckConstraint("interval_days_snapshot > 0",
                        name="ck_comm_preservation_inspection_interval"),
        Index("ix_comm_preservation_inspection_plan_date",
              "company_name", "plan_id", "performed_at"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("commissioning_preservation_plan.id", ondelete="RESTRICT"), nullable=False)
    performed_at = db.Column(db.Date, nullable=False)
    result = db.Column(db.String(30), nullable=False)
    findings = db.Column(db.Text)
    corrective_action = db.Column(db.Text)
    procedure_reference_snapshot = db.Column(db.String(150), nullable=False)
    procedure_revision_snapshot = db.Column(db.String(50), nullable=False)
    interval_days_snapshot = db.Column(db.Integer, nullable=False)
    next_due_date_after = db.Column(db.Date)
    performed_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    plan = db.relationship("CommissioningPreservationPlan", back_populates="inspections")


class ProgressSnapshot(db.Model):
    __tablename__ = "commissioning_progress_snapshot"
    __table_args__ = (
        UniqueConstraint("company_name", "project_id", "system_id", "subsystem_id", "snapshot_date", name="uq_comm_progress_snapshot_scope_date"),
        CheckConstraint("percent_complete >= 0 AND percent_complete <= 100", name="ck_comm_progress_percent_range"),
        CheckConstraint("weighted_percent >= 0 AND weighted_percent <= 100", name="ck_comm_progress_weighted_range"),
        CheckConstraint("task_percent_complete >= 0 AND task_percent_complete <= 100",
                        name="ck_comm_progress_task_percent_range"),
        CheckConstraint("task_weighted_percent >= 0 AND task_weighted_percent <= 100",
                        name="ck_comm_progress_task_weighted_range"),
        CheckConstraint("task_estimated_hours >= 0 AND task_completed_hours >= 0",
                        name="ck_comm_progress_task_hours_nonnegative"),
        ForeignKeyConstraint(["project_id", "company_name"], ["commissioning_project.id", "commissioning_project.company_name"], name="fk_comm_progress_project_tenant"),
        ForeignKeyConstraint(["system_id", "company_name"], ["commissioning_system.id", "commissioning_system.company_name"], name="fk_comm_progress_system_tenant"),
        ForeignKeyConstraint(["subsystem_id", "company_name"], ["commissioning_subsystem.id", "commissioning_subsystem.company_name"], name="fk_comm_progress_subsystem_tenant"),
        Index("ix_comm_progress_company_project_date", "company_name", "project_id", "snapshot_date"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    system_id = db.Column(db.Integer, db.ForeignKey("commissioning_system.id", ondelete="RESTRICT"))
    subsystem_id = db.Column(db.Integer, db.ForeignKey("commissioning_subsystem.id", ondelete="RESTRICT"))
    snapshot_date = db.Column(db.Date, nullable=False)
    percent_complete = db.Column(db.Float, nullable=False, default=0.0)
    weighted_percent = db.Column(db.Float, nullable=False, default=0.0)
    punch_open_count = db.Column(db.Integer, nullable=False, default=0)
    punch_closed_count = db.Column(db.Integer, nullable=False, default=0)
    checksheet_total = db.Column(db.Integer, nullable=False, default=0)
    checksheet_signed_off = db.Column(db.Integer, nullable=False, default=0)
    task_total = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    task_completed = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    task_percent_complete = db.Column(db.Float, nullable=False, default=0.0, server_default="0")
    task_weighted_percent = db.Column(db.Float, nullable=False, default=0.0, server_default="0")
    task_estimated_hours = db.Column(db.Float, nullable=False, default=0.0, server_default="0")
    task_completed_hours = db.Column(db.Float, nullable=False, default=0.0, server_default="0")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CommissioningAuditLog(db.Model):
    __tablename__ = "commissioning_audit_log"
    __table_args__ = (Index("ix_comm_audit_company_entity", "company_name", "entity_type", "entity_id"),)
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(80), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    before_json = db.Column(db.JSON)
    after_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CommissioningAttachment(db.Model):
    __tablename__ = "commissioning_attachment"
    __table_args__ = (Index("ix_comm_attachment_company_entity", "company_name", "entity_type", "entity_id"),)
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    storage_key = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(120), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)
    checksum = db.Column(db.String(64), nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CommissioningSignature(db.Model):
    __tablename__ = "commissioning_signature"
    __table_args__ = (Index("ix_comm_signature_company_entity", "company_name", "entity_type", "entity_id"),)
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    signature_type = db.Column(db.String(50), nullable=False)
    signer_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    verification_method = db.Column(db.String(30), nullable=False)
    verification_reference = db.Column(db.String(100))
    signed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    signature_metadata_json = db.Column(db.JSON)


class CommissioningMembership(db.Model):
    __tablename__ = "commissioning_membership"
    __table_args__ = (
        UniqueConstraint("company_name", "project_id", "user_id", name="uq_comm_membership_project_user"),
        ForeignKeyConstraint(["project_id", "company_name"], ["commissioning_project.id", "commissioning_project.company_name"], name="fk_comm_membership_project_tenant"),
        Index("ix_comm_membership_company_project_role", "company_name", "project_id", "role"),
    )
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("commissioning_project.id", ondelete="RESTRICT"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False)
    role = db.Column(_enum(MembershipRole, "commissioning_membership_role"), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


# Signed-off check sheets and their items are immutable through ORM operations.
from sqlalchemy import event, inspect as sa_inspect, select
from sqlalchemy.orm import Session


@event.listens_for(Session, "before_flush")
def _protect_signed_check_sheets(session, flush_context, instances):
    """Enforce sign-off immutability against the persisted state, not a mutable status field."""
    pending = set(session.new).union(session.dirty).union(session.deleted)
    changed_sheets = [obj for obj in pending if isinstance(obj, CheckSheet)]
    persisted_statuses = {}
    existing_ids = [obj.id for obj in changed_sheets if obj not in session.new and obj.id is not None]
    if existing_ids:
        persisted_statuses = dict(
            session.execute(
                select(CheckSheet.id, CheckSheet.status).where(CheckSheet.id.in_(existing_ids))
            ).all()
        )

    signed_sheet_ids = {
        sheet_id for sheet_id, status in persisted_statuses.items()
        if status == CheckSheetStatus.SIGNED_OFF
    }
    signoff_fields = {
        "status", "signed_by_client_id", "signed_by_contractor_id",
        "signed_at", "updated_at",
    }

    for sheet in changed_sheets:
        if sheet in session.new:
            if sheet.status == CheckSheetStatus.SIGNED_OFF:
                raise ValueError("New check sheets must start as DRAFT; use the sign-off workflow.")
            continue

        persisted_status = persisted_statuses.get(sheet.id)
        if persisted_status == CheckSheetStatus.SIGNED_OFF:
            signed_sheet_ids.add(sheet.id)
            if sheet in session.deleted or session.is_modified(sheet, include_collections=True):
                raise ValueError("Signed-off check sheets are immutable; create a new revision.")
            continue

        if sheet.status == CheckSheetStatus.SIGNED_OFF:
            changed_attributes = {
                attribute.key
                for attribute in sa_inspect(sheet).attrs
                if attribute.history.has_changes()
            }
            if "status" not in changed_attributes or not changed_attributes.issubset(signoff_fields):
                raise ValueError("Check sheet content must be finalized before sign-off.")
            signed_sheet_ids.add(sheet.id)

    changed_items = [obj for obj in pending if isinstance(obj, CheckSheetItem)]
    parent_ids = set()
    for item in changed_items:
        if item.check_sheet_id is not None:
            parent_ids.add(item.check_sheet_id)
        parent_ids.update(
            parent_id for parent_id in sa_inspect(item).attrs.check_sheet_id.history.deleted
            if parent_id is not None
        )

    if parent_ids:
        parent_statuses = session.execute(
            select(CheckSheet.id, CheckSheet.status).where(CheckSheet.id.in_(parent_ids))
        ).all()
        signed_sheet_ids.update(
            sheet_id for sheet_id, status in parent_statuses
            if status == CheckSheetStatus.SIGNED_OFF
        )

    for item in changed_items:
        item_parent_ids = {item.check_sheet_id} if item.check_sheet_id is not None else set()
        item_parent_ids.update(
            parent_id for parent_id in sa_inspect(item).attrs.check_sheet_id.history.deleted
            if parent_id is not None
        )
        if item_parent_ids.intersection(signed_sheet_ids):
            raise ValueError("Items on a signed-off check sheet are immutable; create a new revision.")

@event.listens_for(Session, "before_flush")
def _protect_commissioning_evidence(session, flush_context, instances):
    """Keep audit events, signatures, and Punch history append-only."""
    protected = (CommissioningAuditLog, CommissioningSignature, PunchHistory, CheckSheetRevision, CommissioningAttachment, CommissioningDocumentReview, CommissioningCertificate)
    if any(isinstance(obj, protected) for obj in set(session.dirty).union(session.deleted)):
        raise ValueError("Commissioning audit evidence is append-only.")
