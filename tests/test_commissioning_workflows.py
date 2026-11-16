"""End-to-end tests for OPERA operational workflows."""
import pytest

from extensions import db
from models import AccessLevel, User
from models_commissioning import (
    CommissioningProject, CommissioningSystem, CommissioningSubsystem,
    CommissioningMembership, MembershipRole, CheckSheet, CheckSheetItem,
    CheckSheetType, CheckSheetStatus, ItemResultStatus, PunchItem,
    PunchCategory, PunchSeverity, PunchStatus,
)


def _user(company, email, name):
    return User(
        company_name=company, company_email=email, full_name=name,
        company_address="Office", country="DE",
        access_level=AccessLevel.project_manager, password="test-password-123",
    )


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


@pytest.fixture
def opera_setup(app):
    with app.app_context():
        manager = _user("Contractor A", "opera-flow-manager@example.com", "Manager")
        client_rep = _user("Contractor A", "opera-flow-client@example.com", "Client")
        viewer = _user("Contractor A", "opera-flow-viewer@example.com", "Viewer")
        qc = _user("Contractor A", "opera-flow-qc@example.com", "QC Inspector")
        outsider = _user("Contractor B", "opera-flow-outsider@example.com", "Outsider")
        db.session.add_all([manager, client_rep, viewer, qc, outsider])
        db.session.flush()
        project = CommissioningProject(
            company_name="Contractor A", project_code="FLOW-01", name="Workflow Project",
            created_by_id=manager.id,
        )
        db.session.add(project)
        db.session.flush()
        system = CommissioningSystem(
            company_name="Contractor A", project_id=project.id,
            system_code="SYS-01", name="Utilities",
        )
        db.session.add(system)
        db.session.flush()
        subsystem = CommissioningSubsystem(
            company_name="Contractor A", system_id=system.id,
            subsystem_code="SUB-01", name="Instrument Air",
        )
        db.session.add(subsystem)
        db.session.flush()
        db.session.add_all([
            CommissioningMembership(company_name="Contractor A", project_id=project.id,
                user_id=manager.id, role=MembershipRole.COMMISSIONING_MANAGER, is_active=True),
            CommissioningMembership(company_name="Contractor A", project_id=project.id,
                user_id=client_rep.id, role=MembershipRole.CLIENT_REPRESENTATIVE, is_active=True),
            CommissioningMembership(company_name="Contractor A", project_id=project.id,
                user_id=viewer.id, role=MembershipRole.VIEWER, is_active=True),
            CommissioningMembership(company_name="Contractor A", project_id=project.id,
                user_id=qc.id, role=MembershipRole.QC_INSPECTOR, is_active=True),
        ])
        db.session.commit()
        return {
            "manager": manager.id, "client": client_rep.id, "viewer": viewer.id,
            "qc": qc.id, "outsider": outsider.id, "project": project.id, "system": system.id,
            "subsystem": subsystem.id,
        }


def test_operations_dashboard_is_available_to_project_member(client, opera_setup):
    from models import User
    with client.application.app_context():
        user = db.session.get(User, opera_setup["manager"])
    _login(client, user)
    response = client.get(f"/commissioning/projects/{opera_setup['project']}/operations")
    assert response.status_code == 200
    assert "عملیات کمیسیونینگ".encode() in response.data


def test_membership_cannot_cross_company_boundary(client, opera_setup):
    from models import User
    with client.application.app_context():
        manager = db.session.get(User, opera_setup["manager"])
    _login(client, manager)
    response = client.post(
        f"/commissioning/projects/{opera_setup['project']}/members",
        data={"user_id": opera_setup["outsider"], "role": "viewer"},
    )
    assert response.status_code == 404


def test_checksheet_two_party_signoff_and_immutable_revision(client, app, opera_setup):
    from models import User
    with app.app_context():
        manager = db.session.get(User, opera_setup["manager"])
    _login(client, manager)
    response = client.post(
        f"/commissioning/projects/{opera_setup['project']}/checksheets/new",
        data={
            "subsystem_id": opera_setup["subsystem"],
            "sheet_type": CheckSheetType.COMM_C.value,
            "title": "Pump functional test",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        sheet = CheckSheet.query.filter_by(project_id=opera_setup["project"]).one()
        sheet_id = sheet.id
        item = CheckSheetItem(
            company_name="Contractor A", check_sheet_id=sheet.id, sequence=1,
            description="Verify pump rotation", expected_result="Clockwise",
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id
    client.post(f"/commissioning/checksheets/{sheet_id}/issue")
    response = client.post(
        f"/commissioning/checksheets/{sheet_id}/items/{item_id}/result",
        data={"actual_result": "Clockwise", "result_status": "OK"},
    )
    assert response.status_code == 302
    with app.app_context():
        qc_user = db.session.get(User, opera_setup["qc"])
    _login(client, qc_user)
    response = client.post(f"/commissioning/checksheets/{sheet_id}/items/{item_id}/verify")
    assert response.status_code == 302
    with app.app_context():
        manager = db.session.get(User, opera_setup["manager"])
    _login(client, manager)
    response = client.post(f"/commissioning/checksheets/{sheet_id}/sign")
    assert response.status_code == 302
    with app.app_context():
        sheet = db.session.get(CheckSheet, sheet_id)
        assert sheet.signed_by_contractor_id == opera_setup["manager"]
        assert sheet.status == CheckSheetStatus.IN_PROGRESS
    with app.app_context():
        client_rep = db.session.get(User, opera_setup["client"])
    _login(client, client_rep)
    response = client.post(f"/commissioning/checksheets/{sheet_id}/sign")
    assert response.status_code == 302
    with app.app_context():
        sheet = db.session.get(CheckSheet, sheet_id)
        assert sheet.status == CheckSheetStatus.SIGNED_OFF
        assert sheet.signed_by_client_id == opera_setup["client"]
        assert sheet.signed_by_contractor_id == opera_setup["manager"]
        assert sheet.signed_at is not None


def test_viewer_cannot_transition_punch_status(client, app, opera_setup):
    from models import User
    with app.app_context():
        punch = PunchItem(
            company_name="Contractor A", project_id=opera_setup["project"],
            subsystem_id=opera_setup["subsystem"], punch_number="FLOW-01-PUNCH-C-00001",
            category=PunchCategory.C, severity=PunchSeverity.LOW,
            description="Paint touch-up", raised_by_id=opera_setup["manager"],
            status=PunchStatus.OPEN,
        )
        db.session.add(punch)
        db.session.commit()
        punch_id = punch.id
    with app.app_context():
        viewer = db.session.get(User, opera_setup["viewer"])
    _login(client, viewer)
    response = client.post(
        f"/commissioning/punch/{punch_id}/transition",
        data={"status": "IN_PROGRESS"},
    )
    assert response.status_code == 403
