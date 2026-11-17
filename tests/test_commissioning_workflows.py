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


def _login_id(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
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
    html = response.get_data(as_text=True)
    assert "Commissioning operations" in html
    title = html.split("<title>", 1)[1].split("</title>", 1)[0]
    assert "OPERA — Project operations" in title
    assert "Evidence for Punch" not in title
    assert "Evidence for Punch and handover packages" in html


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


def test_checksheet_evidence_upload_download_and_tenant_isolation(client, app, opera_setup, tmp_path):
    from io import BytesIO
    from models import User
    from models_commissioning import CommissioningAttachment

    app.config["OPERA_UPLOAD_DIR"] = str(tmp_path)
    with app.app_context():
        manager = db.session.get(User, opera_setup["manager"])
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="FLOW-01-C-00001", sheet_type=CheckSheetType.COMM_C,
            title="Evidence upload test", created_by_id=manager.id,
        )
        db.session.add(sheet)
        db.session.commit()
        sheet_id = sheet.id
        manager_id = manager.id
    _login_id(client, manager_id)
    assert client.get(f"/commissioning/checksheets/{sheet_id}").status_code == 200
    response = client.post(
        f"/commissioning/evidence/CheckSheet/{sheet_id}",
        data={"file": (BytesIO(b"%PDF-1.7\\nOPERA test evidence"), "گزارش-تست.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    with app.app_context():
        attachment = CommissioningAttachment.query.filter_by(
            company_name="Contractor A", entity_type="CheckSheet", entity_id=sheet_id
        ).one()
        attachment_id = attachment.id
        assert attachment.filename == "گزارش-تست.pdf"
        assert attachment.file_size > 0
        assert len(attachment.checksum) == 64
        stored_path = tmp_path / attachment.storage_key
        assert stored_path.is_file()
    response = client.get(f"/commissioning/evidence/{attachment_id}")
    assert response.status_code == 200
    assert response.data.startswith(b"%PDF-1.7")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    with app.app_context():
        outsider = db.session.get(User, opera_setup["outsider"])
        outsider_id = outsider.id
    _login_id(client, outsider_id)
    response = client.get(f"/commissioning/evidence/{attachment_id}")
    assert response.status_code == 404


def test_evidence_upload_rejects_mismatched_file_content(client, app, opera_setup, tmp_path):
    from io import BytesIO
    from models import User

    app.config["OPERA_UPLOAD_DIR"] = str(tmp_path)
    with app.app_context():
        manager = db.session.get(User, opera_setup["manager"])
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="FLOW-01-C-00002", sheet_type=CheckSheetType.COMM_C,
            title="Invalid evidence test", created_by_id=manager.id,
        )
        db.session.add(sheet)
        db.session.commit()
        sheet_id = sheet.id
        manager_id = manager.id
    _login_id(client, manager_id)
    response = client.post(
        f"/commissioning/evidence/CheckSheet/{sheet_id}",
        data={"file": (BytesIO(b"this is not a PDF"), "fake.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_viewer_cannot_upload_evidence(client, app, opera_setup, tmp_path):
    from io import BytesIO
    from models import User

    app.config["OPERA_UPLOAD_DIR"] = str(tmp_path)
    with app.app_context():
        viewer = db.session.get(User, opera_setup["viewer"])
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="FLOW-01-C-00003", sheet_type=CheckSheetType.COMM_C,
            title="Permission test", created_by_id=viewer.id,
        )
        db.session.add(sheet)
        db.session.commit()
        sheet_id = sheet.id
        viewer_id = viewer.id
    _login_id(client, viewer_id)
    response = client.post(
        f"/commissioning/evidence/CheckSheet/{sheet_id}",
        data={"file": (BytesIO(b"%PDF-1.7\\nrestricted"), "restricted.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 403


def test_signed_off_checksheet_rejects_new_evidence(client, app, opera_setup, tmp_path):
    from io import BytesIO
    from models import User

    app.config["OPERA_UPLOAD_DIR"] = str(tmp_path)
    with app.app_context():
        manager = db.session.get(User, opera_setup["manager"])
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="FLOW-01-C-00004", sheet_type=CheckSheetType.COMM_C,
            title="Signed-off evidence immutability", created_by_id=manager.id,
        )
        db.session.add(sheet)
        db.session.commit()
        sheet.status = CheckSheetStatus.SIGNED_OFF
        db.session.commit()
        sheet_id = sheet.id
        manager_id = manager.id
    _login_id(client, manager_id)
    response = client.post(
        f"/commissioning/evidence/CheckSheet/{sheet_id}",
        data={"file": (BytesIO(b"%PDF-1.7\\nlate evidence"), "late.pdf")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 409



def test_task_register_create_and_filter_is_project_scoped(client, app, opera_setup):
    from models import User
    from models_commissioning import (
        CommissioningTask, CommissioningTaskType, CheckSheet,
        CommissioningAuditLog,
    )
    with app.app_context():
        manager = db.session.get(User, opera_setup["manager"])
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="FLOW-01-CCK-00001", sheet_type=CheckSheetType.COMM_C,
            title="Instrument air conformity check",
        )
        db.session.add(sheet)
        db.session.commit()
        manager_id, sheet_id = manager.id, sheet.id
    _login_id(client, manager_id)
    url = f"/commissioning/projects/{opera_setup['project']}/tasks"
    response = client.get(url)
    assert response.status_code == 200
    assert b"Commissioning Task Register" in response.data
    response = client.post(url, data={
        "task_number": "FLOW-01-CCK-00001",
        "title": "Verify instrument air installation",
        "activity_type": CommissioningTaskType.CCK.value,
        "discipline": "Mechanical",
        "system_id": opera_setup["system"],
        "subsystem_id": opera_setup["subsystem"],
        "check_sheet_id": sheet_id,
        "progress_stage": "Pre-commissioning",
        "progress_substage": "Conformity Checks",
        "estimated_man_hours": "4.5",
        "spent_man_hours": "1.0",
        "planned_start_date": "2026-11-18",
        "planned_finish_date": "2026-11-19",
    })
    assert response.status_code == 302
    with app.app_context():
        task = CommissioningTask.query.filter_by(task_number="FLOW-01-CCK-00001").one()
        assert task.check_sheet_id == sheet_id
        assert task.activity_type is CommissioningTaskType.CCK
        assert CommissioningAuditLog.query.filter_by(
            entity_type="CommissioningTask", entity_id=task.id, action="TASK_CREATED"
        ).count() == 1
    response = client.get(url + "?activity_type=CCK&q=instrument")
    assert response.status_code == 200
    assert b"FLOW-01-CCK-00001" in response.data


def test_task_register_enforces_project_role_and_company_boundary(client, app, opera_setup):
    from models import User
    url = f"/commissioning/projects/{opera_setup['project']}/tasks"
    with app.app_context():
        viewer = db.session.get(User, opera_setup["viewer"])
        outsider = db.session.get(User, opera_setup["outsider"])
    _login(client, viewer)
    assert client.get(url).status_code == 200
    _login(client, outsider)
    assert client.get(url).status_code == 404
