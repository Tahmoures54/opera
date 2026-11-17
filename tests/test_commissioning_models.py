"""Model and tenant-key tests for the OPERA foundation."""
import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models_commissioning import (
    CommissioningProject, CommissioningSystem, CommissioningSubsystem,
    CommissioningEquipment, CommissioningTask, CommissioningTaskType, CommissioningTaskStatus, CheckSheet, CheckSheetItem, CheckSheetType,
    CheckSheetStatus, ItemResultStatus, PunchItem, PunchCategory,
    PunchSeverity, PunchStatus, CommissioningMembership, MembershipRole,
)


@pytest.fixture(autouse=True)
def _application_context(app):
    with app.app_context():
        yield


def _project(company, code="PRJ-01"):
    project = CommissioningProject(company_name=company, project_code=code, name="Demo project")
    db.session.add(project)
    db.session.flush()
    return project


def test_opera_tables_are_registered(app):
    expected = {
        "commissioning_project", "commissioning_system", "commissioning_subsystem",
        "commissioning_equipment", "commissioning_task", "commissioning_check_sheet",
        "commissioning_check_sheet_item", "commissioning_check_sheet_revision",
        "commissioning_punch_item", "commissioning_punch_history",
        "commissioning_witness_point", "commissioning_handover_package",
        "commissioning_progress_snapshot", "commissioning_audit_log",
        "commissioning_attachment", "commissioning_signature", "commissioning_membership",
    }
    assert expected.issubset(db.metadata.tables)


def test_project_code_is_unique_per_company(app):
    _project("Contractor A")
    _project("Contractor B")
    db.session.commit()
    with pytest.raises(IntegrityError):
        _project("Contractor A")
    db.session.rollback()


def test_structure_and_checksheet_tenant_fields(app):
    project = _project("Contractor A")
    system = CommissioningSystem(company_name=project.company_name, project_id=project.id, system_code="SYS-01", name="Utilities", weight_percent=50)
    db.session.add(system)
    db.session.flush()
    subsystem = CommissioningSubsystem(company_name=project.company_name, system_id=system.id, subsystem_code="SUB-01", name="Instrument Air", weight_percent=100)
    db.session.add(subsystem)
    db.session.flush()
    equipment = CommissioningEquipment(company_name=project.company_name, project_id=project.id, subsystem_id=subsystem.id, tag_number="K-1001", equipment_type="Compressor")
    db.session.add(equipment)
    db.session.flush()
    sheet = CheckSheet(company_name=project.company_name, project_id=project.id, system_id=system.id, subsystem_id=subsystem.id, equipment_id=equipment.id, sheet_number="PRJ-01-COMM_C-00001", sheet_type=CheckSheetType.COMM_C, title="Compressor functional check", status=CheckSheetStatus.DRAFT)
    db.session.add(sheet)
    db.session.flush()
    item = CheckSheetItem(company_name=project.company_name, check_sheet_id=sheet.id, sequence=1, description="Verify rotation", result_status=ItemResultStatus.PENDING)
    db.session.add(item)
    db.session.commit()
    assert sheet.company_name == item.company_name == "Contractor A"


def test_membership_roles_are_project_scoped(app):
    project = _project("Contractor A")
    # The FK target is intentionally an existing MaterialHub user record.
    from models import User, AccessLevel
    user = User(company_name="Contractor A", company_email="opera-test@example.com", full_name="OPERA Tester", company_address="Office", country="DE", access_level=AccessLevel.project_manager, password="test-password-123")
    db.session.add(user)
    db.session.flush()
    membership = CommissioningMembership(company_name="Contractor A", project_id=project.id, user_id=user.id, role=MembershipRole.COMMISSIONING_MANAGER)
    db.session.add(membership)
    db.session.commit()
    assert membership.role is MembershipRole.COMMISSIONING_MANAGER


def test_punch_requires_tenant_scoped_number(app):
    project = _project("Contractor A")
    system = CommissioningSystem(company_name=project.company_name, project_id=project.id, system_code="SYS", name="System")
    db.session.add(system)
    db.session.flush()
    subsystem = CommissioningSubsystem(company_name=project.company_name, system_id=system.id, subsystem_code="SUB", name="Subsystem")
    db.session.add(subsystem)
    db.session.flush()
    from models import User, AccessLevel
    user = User(company_name="Contractor A", company_email="punch-test@example.com", full_name="Punch Tester", company_address="Office", country="DE", access_level=AccessLevel.project_manager, password="test-password-123")
    db.session.add(user)
    db.session.flush()
    punch = PunchItem(company_name="Contractor A", project_id=project.id, subsystem_id=subsystem.id, punch_number="PRJ-01-PUNCH-A-00001", category=PunchCategory.A, severity=PunchSeverity.HIGH, description="Missing support", raised_by_id=user.id, status=PunchStatus.OPEN)
    db.session.add(punch)
    db.session.commit()
    assert punch.status is PunchStatus.OPEN


def test_signed_off_check_sheet_items_are_immutable(app):
    project = _project("Contractor A")
    system = CommissioningSystem(company_name=project.company_name, project_id=project.id, system_code="SYS", name="System")
    db.session.add(system)
    db.session.flush()
    subsystem = CommissioningSubsystem(company_name=project.company_name, system_id=system.id, subsystem_code="SUB", name="Subsystem")
    db.session.add(subsystem)
    db.session.flush()
    sheet = CheckSheet(company_name=project.company_name, project_id=project.id, system_id=system.id, subsystem_id=subsystem.id, sheet_number="PRJ-01-PRE_COMM_A-00001", sheet_type=CheckSheetType.PRE_COMM_A, title="Signed sheet", status=CheckSheetStatus.DRAFT)
    db.session.add(sheet)
    db.session.flush()
    item = CheckSheetItem(company_name=project.company_name, check_sheet_id=sheet.id, sequence=1, description="Inspect", result_status=ItemResultStatus.OK)
    db.session.add(item)
    db.session.commit()
    sheet.status = CheckSheetStatus.SIGNED_OFF
    db.session.commit()
    item.actual_result = "Changed after sign-off"
    with pytest.raises(ValueError, match="immutable"):
        db.session.commit()
    db.session.rollback()


def test_hierarchy_has_composite_tenant_foreign_keys(app):
    constraints = db.metadata.tables["commissioning_check_sheet"].foreign_key_constraints
    assert any(constraint.name == "fk_comm_check_project_tenant" for constraint in constraints)
    assert any(constraint.name == "fk_comm_check_subsystem_tenant" for constraint in constraints)


def test_signed_off_check_sheet_metadata_is_immutable(app):
    project = _project("Contractor A")
    system = CommissioningSystem(company_name=project.company_name, project_id=project.id, system_code="SYS", name="System")
    db.session.add(system)
    db.session.flush()
    subsystem = CommissioningSubsystem(company_name=project.company_name, system_id=system.id, subsystem_code="SUB", name="Subsystem")
    db.session.add(subsystem)
    db.session.flush()
    sheet = CheckSheet(company_name="Contractor A", project_id=project.id, system_id=system.id, subsystem_id=subsystem.id, sheet_number="PRJ-01-COMM_C-00001", sheet_type=CheckSheetType.COMM_C, title="Final", status=CheckSheetStatus.DRAFT)
    db.session.add(sheet)
    db.session.commit()
    sheet.status = CheckSheetStatus.SIGNED_OFF
    db.session.commit()
    sheet.title = "Changed after sign-off"
    with pytest.raises(ValueError, match="immutable"):
        db.session.commit()
    db.session.rollback()


def test_commissioning_task_register_links_project_system_subsystem_and_equipment(app):
    project = _project("Contractor A", code="TASK-01")
    system = CommissioningSystem(company_name=project.company_name, project_id=project.id, system_code="SYS-01", name="Utilities")
    db.session.add(system)
    db.session.flush()
    subsystem = CommissioningSubsystem(company_name=project.company_name, system_id=system.id, subsystem_code="SUB-01", name="Instrument Air")
    db.session.add(subsystem)
    db.session.flush()
    equipment = CommissioningEquipment(company_name=project.company_name, project_id=project.id, subsystem_id=subsystem.id, tag_number="K-1001", equipment_type="Compressor")
    db.session.add(equipment)
    db.session.flush()
    task = CommissioningTask(
        company_name=project.company_name, project_id=project.id, system_id=system.id,
        subsystem_id=subsystem.id, equipment_id=equipment.id, task_number="TASK-01-CCK-0001",
        title="Verify equipment installation", activity_type=CommissioningTaskType.CCK,
        discipline="Mechanical", progress_stage="Pre-commissioning",
        progress_substage="Conformity Checks", estimated_man_hours=3.5,
        spent_man_hours=0, status=CommissioningTaskStatus.NOT_STARTED,
    )
    db.session.add(task)
    db.session.commit()
    assert task.equipment_id == equipment.id
    assert task.activity_type is CommissioningTaskType.CCK
    assert task.status is CommissioningTaskStatus.NOT_STARTED


def test_commissioning_task_rejects_negative_man_hours(app):
    project = _project("Contractor A", code="TASK-02")
    system = CommissioningSystem(company_name=project.company_name, project_id=project.id, system_code="SYS-01", name="Utilities")
    db.session.add(system)
    db.session.flush()
    subsystem = CommissioningSubsystem(company_name=project.company_name, system_id=system.id, subsystem_code="SUB-01", name="Instrument Air")
    db.session.add(subsystem)
    db.session.flush()
    task = CommissioningTask(
        company_name=project.company_name, project_id=project.id, system_id=system.id,
        subsystem_id=subsystem.id, task_number="TASK-02-STS-0001", title="Pressure test",
        activity_type=CommissioningTaskType.STS, discipline="Piping",
        estimated_man_hours=-1, spent_man_hours=0,
    )
    db.session.add(task)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_signed_off_check_sheet_cannot_be_reopened_to_edit_items(app):
    project = _project("Contractor A", "IMMUTABLE-01")
    system = CommissioningSystem(
        company_name=project.company_name, project_id=project.id,
        system_code="SYS", name="System",
    )
    db.session.add(system)
    db.session.flush()
    subsystem = CommissioningSubsystem(
        company_name=project.company_name, system_id=system.id,
        subsystem_code="SUB", name="Subsystem",
    )
    db.session.add(subsystem)
    db.session.flush()
    sheet = CheckSheet(
        company_name=project.company_name, project_id=project.id,
        system_id=system.id, subsystem_id=subsystem.id,
        sheet_number="IMMUTABLE-01-C-00001", sheet_type=CheckSheetType.COMM_C,
        title="Immutable signed sheet", status=CheckSheetStatus.DRAFT,
    )
    db.session.add(sheet)
    db.session.flush()
    item = CheckSheetItem(
        company_name=project.company_name, check_sheet_id=sheet.id,
        sequence=1, description="Original inspection item",
        result_status=ItemResultStatus.OK,
    )
    db.session.add(item)
    db.session.commit()

    sheet.status = CheckSheetStatus.SIGNED_OFF
    db.session.commit()

    sheet.status = CheckSheetStatus.DRAFT
    item.description = "Attempted post-sign-off edit"
    with pytest.raises(ValueError, match="immutable"):
        db.session.commit()
    db.session.rollback()

    assert db.session.get(CheckSheet, sheet.id).status is CheckSheetStatus.SIGNED_OFF
    assert db.session.get(CheckSheetItem, item.id).description == "Original inspection item"


def _signed_sheet_with_item():
    project = _project("Contractor A", "IMMUTABLE-EXTRA")
    system = CommissioningSystem(
        company_name=project.company_name, project_id=project.id,
        system_code="SYS", name="System",
    )
    db.session.add(system)
    db.session.flush()
    subsystem = CommissioningSubsystem(
        company_name=project.company_name, system_id=system.id,
        subsystem_code="SUB", name="Subsystem",
    )
    db.session.add(subsystem)
    db.session.flush()
    sheet = CheckSheet(
        company_name=project.company_name, project_id=project.id,
        system_id=system.id, subsystem_id=subsystem.id,
        sheet_number="IMMUTABLE-EXTRA-COMC-00001",
        sheet_type=CheckSheetType.COMM_C, title="Signed sheet",
        status=CheckSheetStatus.DRAFT,
    )
    db.session.add(sheet)
    db.session.flush()
    item = CheckSheetItem(
        company_name=project.company_name, check_sheet_id=sheet.id,
        sequence=1, description="Original inspection item",
    )
    db.session.add(item)
    db.session.commit()
    sheet.status = CheckSheetStatus.SIGNED_OFF
    db.session.commit()
    return sheet.id, item.id, project.id, system.id, subsystem.id


def test_signed_off_sheet_content_and_item_deletion_are_immutable(app):
    from models_commissioning import CheckSheetRevision

    sheet_id, item_id, _, _, _ = _signed_sheet_with_item()
    sheet = db.session.get(CheckSheet, sheet_id)
    sheet.title = "Attempted post-sign-off edit"
    with pytest.raises(ValueError, match="immutable"):
        db.session.commit()
    db.session.rollback()

    item = db.session.get(CheckSheetItem, item_id)
    db.session.delete(item)
    with pytest.raises(ValueError, match="immutable"):
        db.session.commit()
    db.session.rollback()

    assert db.session.get(CheckSheet, sheet_id).status is CheckSheetStatus.SIGNED_OFF
    assert db.session.get(CheckSheetItem, item_id) is not None
    assert CheckSheetRevision.query.count() == 0


def test_signed_off_item_cannot_be_moved_to_another_check_sheet(app):
    sheet_id, item_id, project_id, system_id, subsystem_id = _signed_sheet_with_item()
    draft_sheet = CheckSheet(
        company_name="Contractor A", project_id=project_id,
        system_id=system_id, subsystem_id=subsystem_id,
        sheet_number="IMMUTABLE-EXTRA-COMC-00002",
        sheet_type=CheckSheetType.COMM_C, title="Draft destination",
        status=CheckSheetStatus.DRAFT,
    )
    db.session.add(draft_sheet)
    db.session.flush()
    item = db.session.get(CheckSheetItem, item_id)
    item.check_sheet_id = draft_sheet.id
    with pytest.raises(ValueError, match="signed-off"):
        db.session.commit()
    db.session.rollback()

    item = db.session.get(CheckSheetItem, item_id)
    assert item.check_sheet_id == sheet_id
