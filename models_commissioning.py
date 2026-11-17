"""OPERA commissioning domain models.

All records are tenant-scoped by the OPERA company boundary.
Workflow transitions and cross-tenant authorization are enforced by services
and blueprints; database constraints additionally protect tenant-local keys.
"""
from datetime import datetime
import enum

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint
from extensions import db


def _enum(enum_class, name):
    return db.Enum(
        enum_class,
        name=name,
        native_enum=False,
        values_callable=lambda values: [item.value for item in values],
        validate_strings=True,
    )


class ProjectStatus(enum.Enum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
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
    RF_PENDING = "RF_PENDING"
    RF_CERTIFIED = "RF_CERTIFIED"
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
    rf_certificate_number = db.Column(db.String(100))
    mc_certificate_date = db.Column(db.Date)
    rf_certificate_date = db.Column(db.Date)
    mc_issued_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    rf_issued_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    accepted_by_operations = db.Column(db.Boolean, nullable=False, default=False)
    operations_accepted_by_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"))
    operations_accepted_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    documents_json = db.Column(db.JSON)
    status = db.Column(_enum(HandoverStatus, "commissioning_handover_status"), nullable=False, default=HandoverStatus.DRAFT)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProgressSnapshot(db.Model):
    __tablename__ = "commissioning_progress_snapshot"
    __table_args__ = (
        UniqueConstraint("company_name", "project_id", "system_id", "subsystem_id", "snapshot_date", name="uq_comm_progress_snapshot_scope_date"),
        CheckConstraint("percent_complete >= 0 AND percent_complete <= 100", name="ck_comm_progress_percent_range"),
        CheckConstraint("weighted_percent >= 0 AND weighted_percent <= 100", name="ck_comm_progress_weighted_range"),
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
    protected = (CommissioningAuditLog, CommissioningSignature, PunchHistory, CheckSheetRevision, CommissioningAttachment)
    if any(isinstance(obj, protected) for obj in set(session.dirty).union(session.deleted)):
        raise ValueError("Commissioning audit evidence is append-only.")
