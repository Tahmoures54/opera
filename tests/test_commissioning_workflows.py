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



def test_rejection_reissue_requires_fresh_signatures_and_qc(client, app, opera_setup):
    from models_commissioning import CommissioningAuditLog, CommissioningSignature

    manager_id = opera_setup["manager"]
    _login_id(client, manager_id)
    response = client.post(
        f"/commissioning/projects/{opera_setup['project']}/checksheets/new",
        data={
            "subsystem_id": opera_setup["subsystem"],
            "sheet_type": CheckSheetType.COMM_C.value,
            "title": "Reissue workflow test",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        sheet = CheckSheet.query.filter_by(project_id=opera_setup["project"]).one()
        sheet_id = sheet.id
        item = CheckSheetItem(
            company_name="Contractor A", check_sheet_id=sheet.id, sequence=1,
            description="Verify pressure test", expected_result="Within limits",
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id

    assert client.post(f"/commissioning/checksheets/{sheet_id}/issue").status_code == 302
    assert client.post(
        f"/commissioning/checksheets/{sheet_id}/items/{item_id}/result",
        data={"actual_result": "Within limits", "result_status": "OK"},
    ).status_code == 302

    # The contractor cannot sign until an independent QC verifier has approved the item.
    assert client.post(f"/commissioning/checksheets/{sheet_id}/sign").status_code == 409

    _login_id(client, opera_setup["qc"])
    assert client.post(f"/commissioning/checksheets/{sheet_id}/items/{item_id}/verify").status_code == 302

    _login_id(client, opera_setup["client"])
    assert client.post(f"/commissioning/checksheets/{sheet_id}/sign").status_code == 302
    assert client.post(
        f"/commissioning/checksheets/{sheet_id}/reject",
        data={"reason": "Additional evidence required"},
    ).status_code == 302

    with app.app_context():
        sheet = db.session.get(CheckSheet, sheet_id)
        assert sheet.status is CheckSheetStatus.REJECTED
        assert sheet.signed_by_client_id is None
        assert sheet.signed_by_contractor_id is None
        assert sheet.signed_at is None
        assert sheet.rejection_reason == "Additional evidence required"
        assert CommissioningSignature.query.filter_by(
            company_name="Contractor A", entity_type="CheckSheet", entity_id=sheet_id
        ).count() == 1

    rejected_detail = client.get(f"/commissioning/checksheets/{sheet_id}")
    assert rejected_detail.status_code == 200
    assert "Reissue check sheet" in rejected_detail.get_data(as_text=True)

    _login_id(client, manager_id)
    assert client.post(
        f"/commissioning/checksheets/{sheet_id}/items/{item_id}/result",
        data={"actual_result": "Reworked within limits", "result_status": "OK"},
    ).status_code == 302
    with app.app_context():
        sheet = db.session.get(CheckSheet, sheet_id)
        item = CheckSheetItem.query.filter_by(id=item_id, check_sheet_id=sheet_id).one()
        assert sheet.status is CheckSheetStatus.REJECTED
        assert item.verified_by_id is None

    assert client.post(f"/commissioning/checksheets/{sheet_id}/issue").status_code == 302
    with app.app_context():
        sheet = db.session.get(CheckSheet, sheet_id)
        assert sheet.status is CheckSheetStatus.ISSUED
        assert sheet.rejection_reason is None
        assert sheet.signed_by_client_id is None

    _login_id(client, opera_setup["qc"])
    assert client.post(f"/commissioning/checksheets/{sheet_id}/items/{item_id}/verify").status_code == 302
    _login_id(client, manager_id)
    assert client.post(f"/commissioning/checksheets/{sheet_id}/sign").status_code == 302
    _login_id(client, opera_setup["client"])
    assert client.post(f"/commissioning/checksheets/{sheet_id}/sign").status_code == 302

    with app.app_context():
        sheet = db.session.get(CheckSheet, sheet_id)
        assert sheet.status is CheckSheetStatus.SIGNED_OFF
        assert sheet.signed_by_contractor_id == manager_id
        assert sheet.signed_by_client_id == opera_setup["client"]
        assert CommissioningSignature.query.filter_by(
            company_name="Contractor A", entity_type="CheckSheet", entity_id=sheet_id
        ).count() == 3
        assert CommissioningAuditLog.query.filter_by(
            company_name="Contractor A", entity_type="CheckSheet",
            entity_id=sheet_id, action="CHECKSHEET_REJECTED",
        ).count() == 1


def test_checksheet_revision_history_is_visible_and_latest_revision_is_enforced(client, app, opera_setup):
    from models_commissioning import CheckSheetRevision

    manager_id = opera_setup["manager"]
    with app.app_context():
        manager = db.session.get(User, manager_id)
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="FLOW-01-C-REV-00001", sheet_type=CheckSheetType.COMM_C,
            title="Revision history test", status=CheckSheetStatus.DRAFT,
            created_by_id=manager.id,
        )
        db.session.add(sheet)
        db.session.commit()
        sheet.status = CheckSheetStatus.SIGNED_OFF
        db.session.commit()
        sheet_id = sheet.id

    _login_id(client, manager_id)
    response = client.post(
        f"/commissioning/checksheets/{sheet_id}/revise",
        data={"reason": "Updated acceptance criteria"},
    )
    assert response.status_code == 302
    with app.app_context():
        revisions = CheckSheetRevision.query.filter_by(
            company_name="Contractor A", sheet_number="FLOW-01-C-REV-00001"
        ).all()
        assert len(revisions) == 1
        new_sheet_id = revisions[0].new_check_sheet_id

    stale_response = client.post(
        f"/commissioning/checksheets/{sheet_id}/revise",
        data={"reason": "Attempt from stale revision"},
    )
    assert stale_response.status_code == 409

    response = client.get(f"/commissioning/checksheets/{new_sheet_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Revision history" in html
    assert "Updated acceptance criteria" in html
    assert "Rev 1" in html


def test_checksheet_result_form_posts_enum_values(client, app, opera_setup):
    manager_id = opera_setup["manager"]
    with app.app_context():
        manager = db.session.get(User, manager_id)
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="FLOW-01-C-UI-00001", sheet_type=CheckSheetType.COMM_C,
            title="Result form values", status=CheckSheetStatus.ISSUED,
            created_by_id=manager.id,
        )
        db.session.add(sheet)
        db.session.flush()
        db.session.add(CheckSheetItem(
            company_name="Contractor A", check_sheet_id=sheet.id, sequence=1,
            description="Check valve", expected_result="Opens freely",
        ))
        db.session.commit()
        sheet_id = sheet.id
    _login_id(client, manager_id)
    response = client.get(f"/commissioning/checksheets/{sheet_id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'option value="OK"' in html
    assert 'option value="NOK"' in html
    assert 'option value="NA"' in html
