"""End-to-end tests for OPERA operational workflows."""
from datetime import date, datetime, timedelta
import json

import pytest

from extensions import db
from models import AccessLevel, User
from models_commissioning import (
    CommissioningProject, CommissioningSystem, CommissioningSubsystem, CommissioningEquipment,
    CommissioningMembership, MembershipRole, CheckSheet, CheckSheetItem,
    CheckSheetType, CheckSheetStatus, ItemResultStatus, PunchItem,
    PunchCategory, PunchSeverity, PunchStatus, CommissioningTask,
    CommissioningTaskType, CommissioningTaskStatus, CommissioningTaskDependency, ProgressSnapshot, CommissioningAuditLog,
    CommissioningDocument, CommissioningDocumentReview, CommissioningDossierRequirement, CommissioningAttachment, DocumentStatus,
    CommissioningPreservationPlan, CommissioningPreservationInspection, CommissioningCheckSheetTemplate,
    CommissioningDossierRevision, CommissioningDossierReview, DossierRevisionStatus, DossierReviewDecision,
    HandoverPackage, HandoverStatus, CommissioningCertificate,
    WitnessPoint, WitnessType, WitnessStatus, PunchHistory,
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


def test_witness_hold_lifecycle_requires_notification_release_and_cancellation_reasons(client, app, opera_setup):
    from models import User

    with app.app_context():
        manager = db.session.get(User, opera_setup["manager"])
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="FLOW-01-WIT-00001", sheet_type=CheckSheetType.COMM_C,
            title="Witness lifecycle test", created_by_id=manager.id,
        )
        db.session.add(sheet)
        db.session.commit()
        sheet_id = sheet.id
        manager_id = manager.id
        qc_id = opera_setup["qc"]
        project_id = opera_setup["project"]

    _login_id(client, manager_id)
    base = f"/commissioning/projects/{project_id}/witness"
    response = client.post(base, data={
        "check_sheet_id": sheet_id, "type": WitnessType.HOLD.value,
        "notified_party": "Client QC", "scheduled_at": "2026-11-18T10:00",
    })
    assert response.status_code == 302
    with app.app_context():
        witness = WitnessPoint.query.filter_by(check_sheet_id=sheet_id).one()
        witness_id = witness.id
        assert witness.status == WitnessStatus.PLANNED
        assert witness.notified_at is None

    transition = f"/commissioning/witness/{witness_id}/transition"
    response = client.post(transition, data={"status": "NOTIFIED"})
    assert response.status_code == 302
    with app.app_context():
        witness = db.session.get(WitnessPoint, witness_id)
        assert witness.status == WitnessStatus.NOTIFIED
        assert witness.notified_at is not None

    _login_id(client, qc_id)
    response = client.post(transition, data={"status": "ATTENDED", "result": "ACCEPTED"})
    assert response.status_code == 302
    with app.app_context():
        witness = db.session.get(WitnessPoint, witness_id)
        assert witness.status == WitnessStatus.ATTENDED
        assert witness.attended_by_id == qc_id
        assert witness.attended_at is not None

    _login_id(client, qc_id)
    response = client.post(transition, data={
        "status": "RELEASED", "remarks": "QC cannot release own witness point.",
    })
    assert response.status_code == 403

    _login_id(client, manager_id)
    response = client.post(transition, data={"status": "RELEASED"})
    assert response.status_code == 400
    response = client.post(transition, data={
        "status": "RELEASED", "remarks": "Hold point inspected and released against approved procedure.",
    })
    assert response.status_code == 302
    with app.app_context():
        witness = db.session.get(WitnessPoint, witness_id)
        assert witness.status == WitnessStatus.RELEASED
        assert witness.released_by_id == manager_id
        assert witness.released_at is not None
        assert witness.remarks.startswith("Hold point inspected")
        events = CommissioningAuditLog.query.filter_by(
            entity_type="WitnessPoint", entity_id=witness_id,
            action="WITNESS_STATUS_CHANGED",
        ).order_by(CommissioningAuditLog.id).all()
        assert [event.after_json["status"] for event in events] == [
            "NOTIFIED", "ATTENDED", "RELEASED",
        ]
        assert events[0].after_json["notified_at"]
        assert events[1].after_json["attended_by_id"] == qc_id
        assert events[2].after_json["released_by_id"] == manager_id
        assert events[2].after_json["remarks"].startswith("Hold point inspected")

    response = client.post(base, data={
        "check_sheet_id": sheet_id, "type": WitnessType.HOLD.value,
        "notified_party": "Client QC", "scheduled_at": "2026-11-19T09:00",
    })
    assert response.status_code == 302
    with app.app_context():
        hold_point = WitnessPoint.query.filter_by(
            check_sheet_id=sheet_id, type=WitnessType.HOLD,
            status=WitnessStatus.PLANNED,
        ).one()
        hold_id = hold_point.id
    response = client.post(
        f"/commissioning/witness/{hold_id}/transition",
        data={"status": "CANCELLED", "remarks": "Attempted cancellation"},
    )
    assert response.status_code == 409
    with app.app_context():
        hold_point = db.session.get(WitnessPoint, hold_id)
        assert hold_point.status == WitnessStatus.PLANNED

    response = client.post(base, data={
        "check_sheet_id": sheet_id, "type": WitnessType.REVIEW.value,
        "notified_party": "Engineering", "scheduled_at": "2026-11-19T10:00",
    })
    assert response.status_code == 302
    with app.app_context():
        cancel_point = WitnessPoint.query.filter_by(
            check_sheet_id=sheet_id, type=WitnessType.REVIEW,
        ).one()
        cancel_id = cancel_point.id
    cancel_url = f"/commissioning/witness/{cancel_id}/transition"
    response = client.post(cancel_url, data={"status": "CANCELLED"})
    assert response.status_code == 400
    response = client.post(cancel_url, data={
        "status": "CANCELLED", "remarks": "Procedure superseded; replacement point scheduled.",
    })
    assert response.status_code == 302
    with app.app_context():
        cancel_point = db.session.get(WitnessPoint, cancel_id)
        assert cancel_point.status == WitnessStatus.CANCELLED
        assert cancel_point.remarks.startswith("Procedure superseded")


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
    _login_id(client, opera_setup["viewer"])
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


def test_task_lifecycle_transitions_are_controlled_and_audited(client, app, opera_setup):
    from models import User
    with app.app_context():
        manager_id = opera_setup["manager"]
    _login_id(client, manager_id)
    project_id = opera_setup["project"]
    created = client.post(
        f"/commissioning/projects/{project_id}/tasks",
        data={
            "task_number": "FLOW-TASK-001", "title": "Verify instrument air package",
            "activity_type": CommissioningTaskType.CCK.value, "discipline": "Instrumentation",
            "system_id": opera_setup["system"], "subsystem_id": opera_setup["subsystem"],
            "estimated_man_hours": "4",
        },
    )
    assert created.status_code == 302
    with app.app_context():
        task = CommissioningTask.query.filter_by(task_number="FLOW-TASK-001").one()
        task_id = task.id
    base = f"/commissioning/projects/{project_id}/tasks/{task_id}/transition"

    invalid = client.post(base, data={"status": CommissioningTaskStatus.COMPLETED.value})
    assert invalid.status_code == 409

    ready = client.post(base, data={"status": CommissioningTaskStatus.READY.value})
    assert ready.status_code == 302
    started = client.post(base, data={"status": CommissioningTaskStatus.IN_PROGRESS.value})
    assert started.status_code == 302

    missing_reason = client.post(base, data={"status": CommissioningTaskStatus.BLOCKED.value})
    assert missing_reason.status_code == 400
    blocked = client.post(base, data={
        "status": CommissioningTaskStatus.BLOCKED.value, "reason": "Awaiting isolation certificate",
    })
    assert blocked.status_code == 302

    resumed = client.post(base, data={"status": CommissioningTaskStatus.IN_PROGRESS.value})
    assert resumed.status_code == 302
    completed = client.post(base, data={"status": CommissioningTaskStatus.COMPLETED.value})
    assert completed.status_code == 302

    with app.app_context():
        task = db.session.get(CommissioningTask, task_id)
        events = CommissioningAuditLog.query.filter_by(
            company_name="Contractor A", entity_type="CommissioningTask",
            entity_id=task_id, action="TASK_STATUS_CHANGED",
        ).all()
        assert task.status == CommissioningTaskStatus.COMPLETED
        assert task.actual_start_date is not None
        assert task.actual_finish_date is not None
        assert len(events) == 5
        assert any((event.after_json or {}).get("reason") == "Awaiting isolation certificate" for event in events)


def test_task_lifecycle_requires_manager_permission(client, app, opera_setup):
    from models import User
    with app.app_context():
        task = CommissioningTask(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            task_number="FLOW-TASK-002", title="Viewer cannot execute", discipline="Mechanical",
            activity_type=CommissioningTaskType.STS,
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id
    _login_id(client, opera_setup["viewer"])
    response = client.post(
        f"/commissioning/projects/{opera_setup['project']}/tasks/{task_id}/transition",
        data={"status": CommissioningTaskStatus.READY.value},
    )
    assert response.status_code == 403



def test_document_register_upload_submit_approve_and_create_revision(client, app, opera_setup, tmp_path):
    from io import BytesIO
    app.config["OPERA_UPLOAD_DIR"] = str(tmp_path)
    project_id = opera_setup["project"]
    _login_id(client, opera_setup["manager"])
    created = client.post(
        f"/commissioning/projects/{project_id}/documents",
        data={
            "document_number": "FLOW-ME-DWG-001",
            "title": "Instrument air package general arrangement",
            "document_type": "GA Drawing",
            "discipline": "Mechanical",
            "purpose": "For Approval",
            "system_id": opera_setup["system"],
            "subsystem_id": opera_setup["subsystem"],
        },
    )
    assert created.status_code == 302
    with app.app_context():
        document = CommissioningDocument.query.filter_by(
            document_number="FLOW-ME-DWG-001", revision="A",
        ).one()
        document_id = document.id
    uploaded = client.post(
        f"/commissioning/evidence/CommissioningDocument/{document_id}",
        data={"file": (BytesIO(b"%PDF-1.7\\nOPERA controlled drawing"), "drawing.pdf")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 302
    submitted = client.post(f"/commissioning/documents/{document_id}/submit")
    assert submitted.status_code == 302
    _login_id(client, opera_setup["client"])
    approved = client.post(
        f"/commissioning/documents/{document_id}/decision",
        data={"decision": "APPROVE", "comments": "Reviewed and accepted."},
    )
    assert approved.status_code == 302
    with app.app_context():
        document = db.session.get(CommissioningDocument, document_id)
        assert document.status == DocumentStatus.APPROVED
        assert document.approved_by_id == opera_setup["client"]
        review = CommissioningDocumentReview.query.filter_by(document_id=document_id).one()
        assert review.decision == "APPROVE"
    _login_id(client, opera_setup["manager"])
    revised = client.post(f"/commissioning/documents/{document_id}/revision")
    assert revised.status_code == 302
    with app.app_context():
        old = db.session.get(CommissioningDocument, document_id)
        new = CommissioningDocument.query.filter_by(
            document_number="FLOW-ME-DWG-001", revision="B",
        ).one()
        assert old.status == DocumentStatus.SUPERSEDED
        assert new.status == DocumentStatus.DRAFT
        assert new.supersedes_id == old.id
        assert new.revision_sequence == 2


def test_document_register_rejects_missing_file_and_requires_rejection_reason(client, app, opera_setup):
    project_id = opera_setup["project"]
    _login_id(client, opera_setup["manager"])
    created = client.post(
        f"/commissioning/projects/{project_id}/documents",
        data={
            "document_number": "FLOW-PR-001", "title": "Commissioning procedure",
            "document_type": "Procedure", "discipline": "Commissioning",
        },
    )
    assert created.status_code == 302
    with app.app_context():
        document = CommissioningDocument.query.filter_by(document_number="FLOW-PR-001").one()
        document_id = document.id
    assert client.post(f"/commissioning/documents/{document_id}/submit").status_code == 409
    from io import BytesIO
    app.config["OPERA_UPLOAD_DIR"] = str(app.instance_path)
    uploaded = client.post(
        f"/commissioning/evidence/CommissioningDocument/{document_id}",
        data={"file": (BytesIO(b"%PDF-1.7\\ncontrolled procedure"), "procedure.pdf")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 302
    assert client.post(f"/commissioning/documents/{document_id}/submit").status_code == 302
    _login_id(client, opera_setup["qc"])
    rejected = client.post(
        f"/commissioning/documents/{document_id}/decision",
        data={"decision": "REJECT", "comments": ""},
    )
    assert rejected.status_code == 400
    rejected = client.post(
        f"/commissioning/documents/{document_id}/decision",
        data={"decision": "REJECT", "comments": "Revise drawing notes and dimensions."},
    )
    assert rejected.status_code == 302
    with app.app_context():
        document = db.session.get(CommissioningDocument, document_id)
        assert document.status == DocumentStatus.REJECTED


def test_document_register_viewer_cannot_create_documents(client, opera_setup):
    _login_id(client, opera_setup["viewer"])
    response = client.post(
        f"/commissioning/projects/{opera_setup['project']}/documents",
        data={
            "document_number": "FLOW-VIEW-001", "title": "Unauthorized",
            "document_type": "Other", "discipline": "Quality",
        },
    )
    assert response.status_code == 403


def test_subsystem_dossier_aggregates_current_document_and_completion_records(client, app, opera_setup):
    with app.app_context():
        document = CommissioningDocument(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            document_number="FLOW-DOS-001", revision="B", revision_sequence=2,
            title="Subsystem piping isometric", document_type="Isometric",
            discipline="Piping", status=DocumentStatus.DRAFT,
            created_by_id=opera_setup["manager"],
        )
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="FLOW-DOS-CS-001", sheet_type=CheckSheetType.PRE_COMM_A,
            title="Line walkdown", created_by_id=opera_setup["manager"],
        )
        db.session.add_all([document, sheet])
        db.session.flush()
        punch = PunchItem(
            company_name="Contractor A", project_id=opera_setup["project"],
            subsystem_id=opera_setup["subsystem"], punch_number="FLOW-DOS-PUNCH-A-001",
            category=PunchCategory.A, severity=PunchSeverity.HIGH,
            description="Missing support clamp", raised_by_id=opera_setup["manager"],
            status=PunchStatus.OPEN,
        )
        db.session.add(punch)
        db.session.commit()
    _login_id(client, opera_setup["manager"])
    response = client.get(
        f"/commissioning/projects/{opera_setup['project']}/subsystems/{opera_setup['subsystem']}/dossier"
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Subsystem Completion Dossier" in html
    assert "FLOW-DOS-001" in html
    assert "FLOW-DOS-CS-001" in html
    assert "FLOW-DOS-PUNCH-A-001" in html
    assert "Action required" in html
    assert "0 of 1 current revisions approved" in html


def test_subsystem_dossier_is_tenant_scoped(client, opera_setup):
    _login_id(client, opera_setup["outsider"])
    response = client.get(
        f"/commissioning/projects/{opera_setup['project']}/subsystems/{opera_setup['subsystem']}/dossier"
    )
    assert response.status_code == 404


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

    _login_id(client, manager_id)
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


def test_checksheet_detail_controls_follow_project_roles(client, app, opera_setup):
    with app.app_context():
        manager = db.session.get(User, opera_setup["manager"])
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="FLOW-01-C-ROLE-00001",
            sheet_type=CheckSheetType.COMM_C, title="Role scoped controls",
            status=CheckSheetStatus.ISSUED, created_by_id=manager.id,
        )
        db.session.add(sheet)
        db.session.flush()
        item = CheckSheetItem(
            company_name="Contractor A", check_sheet_id=sheet.id, sequence=1,
            description="Verify valve operation", result_status=ItemResultStatus.OK,
            actual_result="Pass", operator_id=manager.id,
        )
        db.session.add(item)
        db.session.commit()
        sheet_id, item_id = sheet.id, item.id

    _login_id(client, opera_setup["viewer"])
    viewer_html = client.get(f"/commissioning/checksheets/{sheet_id}").get_data(as_text=True)
    for endpoint in (
        f"/commissioning/checksheets/{sheet_id}/items",
        f"/commissioning/checksheets/{sheet_id}/issue",
        f"/commissioning/checksheets/{sheet_id}/reject",
        f"/commissioning/checksheets/{sheet_id}/sign",
        f"/commissioning/checksheets/{sheet_id}/revise",
        f"/commissioning/checksheets/{sheet_id}/items/{item_id}/verify",
    ):
        assert endpoint not in viewer_html

    _login_id(client, opera_setup["qc"])
    qc_html = client.get(f"/commissioning/checksheets/{sheet_id}").get_data(as_text=True)
    assert f"/commissioning/checksheets/{sheet_id}/items/{item_id}/verify" in qc_html
    assert f"/commissioning/checksheets/{sheet_id}/sign" not in qc_html
    assert f"/commissioning/checksheets/{sheet_id}/reject" not in qc_html

    _login_id(client, opera_setup["client"])
    client_html = client.get(f"/commissioning/checksheets/{sheet_id}").get_data(as_text=True)
    assert f"/commissioning/checksheets/{sheet_id}/sign" in client_html
    assert f"/commissioning/checksheets/{sheet_id}/reject" in client_html
    assert f"/commissioning/checksheets/{sheet_id}/issue" not in client_html


def _make_dependency_task(setup, number, title):
    return CommissioningTask(
        company_name="Contractor A", project_id=setup["project"],
        system_id=setup["system"], subsystem_id=setup["subsystem"],
        task_number=number, title=title, activity_type=CommissioningTaskType.CCK,
        discipline="Mechanical", created_by_id=setup["manager"],
    )


def test_finish_to_start_dependencies_block_readiness_and_prevent_cycles(client, app, opera_setup):
    with app.app_context():
        first = _make_dependency_task(opera_setup, "DEP-001", "Install supports")
        second = _make_dependency_task(opera_setup, "DEP-002", "Pressure test")
        db.session.add_all([first, second])
        db.session.commit()
        first_id, second_id = first.id, second.id
    _login_id(client, opera_setup["manager"])

    linked = client.post(
        f"/commissioning/projects/{opera_setup['project']}/tasks/{second_id}/dependencies",
        data={"predecessor_task_id": str(first_id), "lag_days": "2"},
    )
    assert linked.status_code == 302
    with app.app_context():
        dependency = CommissioningTaskDependency.query.filter_by(
            company_name="Contractor A", predecessor_task_id=first_id,
            successor_task_id=second_id,
        ).one()
        assert dependency.dependency_type == "FINISH_TO_START"
        assert dependency.lag_days == 2

    circular = client.post(
        f"/commissioning/projects/{opera_setup['project']}/tasks/{first_id}/dependencies",
        data={"predecessor_task_id": str(second_id), "lag_days": "0"},
    )
    assert circular.status_code == 409

    blocked = client.post(
        f"/commissioning/projects/{opera_setup['project']}/tasks/{second_id}/transition",
        data={"status": "READY"},
    )
    assert blocked.status_code == 409

    with app.app_context():
        predecessor = db.session.get(CommissioningTask, first_id)
        predecessor.status = CommissioningTaskStatus.COMPLETED
        db.session.commit()
    allowed = client.post(
        f"/commissioning/projects/{opera_setup['project']}/tasks/{second_id}/transition",
        data={"status": "READY"},
    )
    assert allowed.status_code == 302


def test_task_dependencies_are_project_and_tenant_scoped(client, app, opera_setup):
    with app.app_context():
        task = _make_dependency_task(opera_setup, "DEP-003", "Local task")
        db.session.add(task)
        db.session.commit()
        task_id = task.id
    _login_id(client, opera_setup["outsider"])
    response = client.post(
        f"/commissioning/projects/{opera_setup['project']}/tasks/{task_id}/dependencies",
        data={"predecessor_task_id": str(task_id), "lag_days": "0"},
    )
    assert response.status_code == 404


def test_scoped_progress_snapshot_calculates_weighted_sheet_and_task_completion(client, app, opera_setup):
    with app.app_context():
        signed_sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="PROG-CS-001", sheet_type=CheckSheetType.PRE_COMM_A,
            title="Completed walkdown", sheet_weight=3,
            created_by_id=opera_setup["manager"],
        )
        open_sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="PROG-CS-002", sheet_type=CheckSheetType.PRE_COMM_A,
            title="Open walkdown", sheet_weight=1,
            created_by_id=opera_setup["manager"],
        )
        completed_task = CommissioningTask(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            task_number="PROG-TASK-001", title="Completed task",
            activity_type=CommissioningTaskType.CCK, discipline="Mechanical",
            estimated_man_hours=8, status=CommissioningTaskStatus.COMPLETED,
            created_by_id=opera_setup["manager"],
        )
        active_task = CommissioningTask(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            task_number="PROG-TASK-002", title="Active task",
            activity_type=CommissioningTaskType.STS, discipline="Mechanical",
            estimated_man_hours=2, status=CommissioningTaskStatus.IN_PROGRESS,
            created_by_id=opera_setup["manager"],
        )
        cancelled_task = CommissioningTask(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            task_number="PROG-TASK-003", title="Cancelled task",
            activity_type=CommissioningTaskType.PIP, discipline="Piping",
            estimated_man_hours=100, status=CommissioningTaskStatus.CANCELLED,
            created_by_id=opera_setup["manager"],
        )
        db.session.add_all([signed_sheet, open_sheet, completed_task, active_task, cancelled_task])
        db.session.commit()
        signed_sheet.status = CheckSheetStatus.SIGNED_OFF
        signed_sheet.signed_by_client_id = opera_setup["client"]
        signed_sheet.signed_by_contractor_id = opera_setup["manager"]
        signed_sheet.signed_at = datetime.utcnow()
        db.session.commit()

    _login_id(client, opera_setup["manager"])
    response = client.post(
        f"/commissioning/projects/{opera_setup['project']}/reports/snapshot",
        data={"scope": f"subsystem:{opera_setup['subsystem']}", "snapshot_date": "2026-11-17"},
    )
    assert response.status_code == 302
    with app.app_context():
        snapshot = ProgressSnapshot.query.filter_by(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
        ).one()
        assert snapshot.checksheet_total == 2
        assert snapshot.checksheet_signed_off == 1
        assert snapshot.weighted_percent == 75.0
        assert snapshot.task_total == 2
        assert snapshot.task_completed == 1
        assert snapshot.task_percent_complete == 50.0
        assert snapshot.task_weighted_percent == 80.0
        assert snapshot.task_estimated_hours == 10.0
        assert snapshot.task_completed_hours == 8.0


def test_progress_snapshot_rejects_foreign_scope(client, opera_setup):
    _login_id(client, opera_setup["outsider"])
    response = client.post(
        f"/commissioning/projects/{opera_setup['project']}/reports/snapshot",
        data={"scope": f"subsystem:{opera_setup['subsystem']}", "snapshot_date": "2026-11-17"},
    )
    assert response.status_code == 404



def test_mc_rfc_certificates_capture_immutable_issue_time_evidence(client, app, opera_setup):
    with app.app_context():
        package = HandoverPackage(
            company_name="Contractor A", project_id=opera_setup["project"],
            subsystem_id=opera_setup["subsystem"], package_number="HP-SUB-01",
        )
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="CERT-CS-001", sheet_type=CheckSheetType.PRE_COMM_A,
            title="Subsystem completion check", created_by_id=opera_setup["manager"],
        )
        db.session.add_all([package, sheet])
        db.session.flush()
        item = CheckSheetItem(
            company_name="Contractor A", check_sheet_id=sheet.id, sequence=1,
            description="Verify subsystem completion", expected_result="Complete",
        )
        db.session.add(item)
        db.session.commit()
        package_id, sheet_id, item_id = package.id, sheet.id, item.id

    _login_id(client, opera_setup["manager"])
    assert client.post(f"/commissioning/checksheets/{sheet_id}/issue").status_code == 302
    assert client.post(
        f"/commissioning/checksheets/{sheet_id}/items/{item_id}/result",
        data={"actual_result": "Complete", "result_status": ItemResultStatus.OK.value},
    ).status_code == 302
    _login_id(client, opera_setup["qc"])
    assert client.post(
        f"/commissioning/checksheets/{sheet_id}/items/{item_id}/verify",
    ).status_code == 302
    _login_id(client, opera_setup["manager"])
    assert client.post(f"/commissioning/checksheets/{sheet_id}/sign").status_code == 302
    _login_id(client, opera_setup["client"])
    assert client.post(f"/commissioning/checksheets/{sheet_id}/sign").status_code == 302

    with app.app_context():
        signed_sheet = db.session.get(CheckSheet, sheet_id)
        assert signed_sheet.status == CheckSheetStatus.SIGNED_OFF
        assert signed_sheet.signed_by_client_id == opera_setup["client"]
        assert signed_sheet.signed_by_contractor_id == opera_setup["manager"]

    _login_id(client, opera_setup["manager"])
    transition_url = f"/commissioning/handover/{package_id}/transition"
    mc = client.post(transition_url, data={
        "status": HandoverStatus.MC_CERTIFIED.value,
        "certificate_number": "MC-CERT-001",
        "certificate_date": "2026-11-17",
    })
    assert mc.status_code == 302

    with app.app_context():
        mc_certificate = CommissioningCertificate.query.filter_by(
            package_id=package_id, certificate_type="MC",
        ).one()
        assert mc_certificate.snapshot_json["readiness"]["current_check_sheets_signed"] == 1
        assert mc_certificate.snapshot_json["readiness"]["gate"] == "MC"
        assert mc_certificate.snapshot_json["readiness"]["gate_ready"] is True
        assert mc_certificate.snapshot_json["readiness"]["readiness_policy"]["punch_blocking_categories"]["MC"] == ["A", "B"]
        mc_certificate_id = mc_certificate.id
        hold = WitnessPoint(
            company_name="Contractor A", project_id=opera_setup["project"],
            check_sheet_id=sheet_id, type=WitnessType.HOLD,
            scheduled_at=datetime.utcnow(), status=WitnessStatus.PLANNED,
            notified_party="Client QC",
        )
        db.session.add(hold)
        db.session.commit()
        hold_id = hold.id

    blocked_rf = client.post(transition_url, data={
        "status": HandoverStatus.RF_CERTIFIED.value,
        "certificate_number": "RF-CERT-001",
        "certificate_date": "2026-11-17",
    })
    assert blocked_rf.status_code == 409

    with app.app_context():
        hold = db.session.get(WitnessPoint, hold_id)
        hold.status = WitnessStatus.RELEASED
        hold.released_by_id = opera_setup["qc"]
        hold.released_at = datetime.utcnow()
        db.session.commit()

    rf = client.post(transition_url, data={
        "status": HandoverStatus.RF_CERTIFIED.value,
        "certificate_number": "RF-CERT-001",
        "certificate_date": "2026-11-17",
    })
    assert rf.status_code == 302

    certificate_page = client.get(
        f"/commissioning/handover/{package_id}/certificates/RFC",
    )
    assert certificate_page.status_code == 200
    assert b"Ready for Commissioning (RFC) Certificate" in certificate_page.data
    legacy_certificate_page = client.get(
        f"/commissioning/handover/{package_id}/certificates/RF",
    )
    assert legacy_certificate_page.status_code == 200
    assert b"MC-CERT-001" not in certificate_page.data

    with app.app_context():
        mc_certificate = db.session.get(CommissioningCertificate, mc_certificate_id)
        assert mc_certificate.snapshot_json["readiness"]["pending_hold_points"] == 0
        rfc_certificate = CommissioningCertificate.query.filter_by(
            package_id=package_id, certificate_type="RFC",
        ).one()
        assert rfc_certificate.certificate_type == "RFC"
        assert rfc_certificate.certificate_date.isoformat() == "2026-11-17"
        assert rfc_certificate.issued_by_id == opera_setup["manager"]
        assert rfc_certificate.snapshot_json["certificate"]["issued_by_id"] == opera_setup["manager"]
        assert rfc_certificate.snapshot_json["certificate"]["issued_at"]
        assert rfc_certificate.snapshot_json["certificate"]["type"] == "RFC"
        assert rfc_certificate.snapshot_json["readiness"]["pending_hold_points"] == 0
        assert rfc_certificate.snapshot_json["witness_points"][0]["status"] == "RELEASED"
        rfc_certificate.snapshot_json = {"tampered": True}
        with pytest.raises(ValueError, match="append-only"):
            db.session.commit()
        db.session.rollback()



def test_engineering_excel_exchange_dry_run_import_and_export(client, app, opera_setup):
    from datetime import date
    from io import BytesIO
    from openpyxl import load_workbook
    from models_commissioning import (
        CommissioningEquipment, CommissioningSystem, CommissioningSubsystem,
        CommissioningTask,
    )

    _login_id(client, opera_setup["manager"])
    template_response = client.get(
        f"/commissioning/projects/{opera_setup['project']}/engineering-data/template",
    )
    assert template_response.status_code == 200
    workbook = load_workbook(BytesIO(template_response.data))
    workbook["Systems"].append(["SYS-EX", "Exchange System", "Utilities", "P-100", 25])
    workbook["Subsystems"].append([
        "SYS-EX", "SUB-EX", "Exchange Subsystem", "Test scope", 50,
        date(2026, 12, 1), date(2026, 12, 15),
    ])
    workbook["Equipment"].append([
        "EQ-EX-001", "SYS-EX", "SUB-EX", "Pump", "Transfer pump",
        "Vendor", "P-100", "SN-001", "ACTIVE",
    ])
    workbook["Tasks"].append([
        "TASK-EX-001", "SYS-EX", "SUB-EX", "EQ-EX-001", "CCK",
        "Verify pump", "Mechanical conformity check", "Mechanical",
        "Pre-commissioning", "Conformity checks", "Mechanical Team", 12,
        date(2026, 11, 20), date(2026, 11, 30),
    ])
    payload = BytesIO()
    workbook.save(payload)
    workbook_bytes = payload.getvalue()

    dry_run = client.post(
        f"/commissioning/projects/{opera_setup['project']}/engineering-data/import",
        data={"action": "validate", "workbook": (BytesIO(workbook_bytes), "engineering.xlsx")},
        content_type="multipart/form-data",
    )
    assert dry_run.status_code == 200
    assert b"Dry run passed" in dry_run.data
    with app.app_context():
        assert CommissioningSystem.query.filter_by(system_code="SYS-EX").count() == 0
        assert CommissioningTask.query.filter_by(task_number="TASK-EX-001").count() == 0

    imported = client.post(
        f"/commissioning/projects/{opera_setup['project']}/engineering-data/import",
        data={"action": "import", "workbook": (BytesIO(workbook_bytes), "engineering.xlsx")},
        content_type="multipart/form-data",
    )
    assert imported.status_code == 302
    with app.app_context():
        system = CommissioningSystem.query.filter_by(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_code="SYS-EX",
        ).one()
        subsystem = CommissioningSubsystem.query.filter_by(
            company_name="Contractor A", system_id=system.id,
            subsystem_code="SUB-EX",
        ).one()
        equipment = CommissioningEquipment.query.filter_by(
            company_name="Contractor A", project_id=opera_setup["project"],
            tag_number="EQ-EX-001",
        ).one()
        task = CommissioningTask.query.filter_by(
            company_name="Contractor A", project_id=opera_setup["project"],
            task_number="TASK-EX-001",
        ).one()
        assert equipment.subsystem_id == subsystem.id
        assert task.equipment_id == equipment.id
        assert task.estimated_man_hours == 12
        assert task.status == CommissioningTaskStatus.NOT_STARTED

    exported = client.get(
        f"/commissioning/projects/{opera_setup['project']}/engineering-data/export",
    )
    assert exported.status_code == 200
    exported_book = load_workbook(BytesIO(exported.data), data_only=False)
    assert exported_book["Systems"].max_row == 3
    assert exported_book["Subsystems"].max_row == 3
    assert exported_book["Equipment"].max_row == 2
    assert exported_book["Tasks"].max_row == 2


def test_engineering_excel_exchange_rejects_formula_cells_and_wrong_equipment_scope(client, app, opera_setup):
    from io import BytesIO
    from openpyxl import load_workbook

    _login_id(client, opera_setup["manager"])
    response = client.get(
        f"/commissioning/projects/{opera_setup['project']}/engineering-data/template",
    )
    workbook = load_workbook(BytesIO(response.data))
    workbook["Systems"].append(["SYS-FORMULA", "=HYPERLINK(\"https://example.invalid\",\"bad\")", "", "", 0])
    payload = BytesIO()
    workbook.save(payload)
    payload.seek(0)
    rejected = client.post(
        f"/commissioning/projects/{opera_setup['project']}/engineering-data/import",
        data={"action": "validate", "workbook": (payload, "formula.xlsx")},
        content_type="multipart/form-data",
    )
    assert rejected.status_code == 400
    assert b"Formula cells are not accepted" in rejected.data

    workbook = load_workbook(BytesIO(client.get(
        f"/commissioning/projects/{opera_setup['project']}/engineering-data/template",
    ).data))
    workbook["Systems"].append(["SYS-A", "System A", "", "", 0])
    workbook["Systems"].append(["SYS-B", "System B", "", "", 0])
    workbook["Subsystems"].append(["SYS-A", "SUB-A", "Subsystem A", "", 0, None, None])
    workbook["Subsystems"].append(["SYS-B", "SUB-B", "Subsystem B", "", 0, None, None])
    workbook["Equipment"].append(["EQ-B", "SYS-B", "SUB-B", "Pump", "", "", "", "", "ACTIVE"])
    workbook["Tasks"].append([
        "TASK-A", "SYS-A", "SUB-A", "EQ-B", "CCK", "Wrong equipment link",
        "", "Mechanical", "", "", "", 1, None, None,
    ])
    payload = BytesIO()
    workbook.save(payload)
    payload.seek(0)
    wrong_scope = client.post(
        f"/commissioning/projects/{opera_setup['project']}/engineering-data/import",
        data={"action": "validate", "workbook": (payload, "wrong-scope.xlsx")},
        content_type="multipart/form-data",
    )
    assert wrong_scope.status_code == 400
    assert b"Equipment must belong to the same system and subsystem" in wrong_scope.data




def test_punch_close_requires_corrective_action_and_reopen_requires_reason(client, app, opera_setup):
    with app.app_context():
        punch = PunchItem(
            company_name="Contractor A", project_id=opera_setup["project"],
            subsystem_id=opera_setup["subsystem"], punch_number="PUNCH-REOPEN-001",
            category=PunchCategory.C, severity=PunchSeverity.MEDIUM,
            description="A minor installation defect", raised_by_id=opera_setup["manager"],
            status=PunchStatus.OPEN,
        )
        db.session.add(punch)
        db.session.flush()
        db.session.add(PunchHistory(
            company_name="Contractor A", punch_item_id=punch.id,
            old_status=None, new_status=PunchStatus.OPEN,
            changed_by_id=opera_setup["manager"], remarks="Punch item raised",
        ))
        db.session.commit()
        punch_id = punch.id

    _login_id(client, opera_setup["manager"])
    url = f"/commissioning/punch/{punch_id}/transition"
    started = client.post(url, data={"status": PunchStatus.IN_PROGRESS.value})
    assert started.status_code == 302

    missing_action = client.post(url, data={"status": PunchStatus.CLOSED.value})
    assert missing_action.status_code == 400
    with app.app_context():
        punch = db.session.get(PunchItem, punch_id)
        assert punch.status == PunchStatus.IN_PROGRESS
        assert punch.corrective_action is None

    closed = client.post(url, data={
        "status": PunchStatus.CLOSED.value,
        "corrective_action": "Replaced the damaged gasket and completed a leak check.",
    })
    assert closed.status_code == 302
    with app.app_context():
        punch = db.session.get(PunchItem, punch_id)
        assert punch.status == PunchStatus.CLOSED
        assert punch.corrective_action.startswith("Replaced the damaged gasket")
        assert punch.closed_at is not None

    missing_reason = client.post(url, data={"status": PunchStatus.IN_PROGRESS.value})
    assert missing_reason.status_code == 400
    _login_id(client, opera_setup["viewer"])
    unauthorized_reopen = client.post(url, data={
        "status": PunchStatus.IN_PROGRESS.value, "reason": "Unauthorized attempt",
    })
    assert unauthorized_reopen.status_code == 403
    _login_id(client, opera_setup["manager"])
    reopened = client.post(url, data={
        "status": PunchStatus.IN_PROGRESS.value,
        "reason": "QC inspection found the leak check evidence incomplete.",
    })
    assert reopened.status_code == 302

    history_page = client.get(f"/commissioning/punch/{punch_id}/history")
    assert history_page.status_code == 200
    assert b"QC inspection found the leak check evidence incomplete" in history_page.data
    assert b"Replaced the damaged gasket" in history_page.data

    with app.app_context():
        punch = db.session.get(PunchItem, punch_id)
        assert punch.status == PunchStatus.IN_PROGRESS
        assert punch.closed_at is None
        assert punch.closed_by_id is None
        assert punch.corrective_action is None
        events = PunchHistory.query.filter_by(punch_item_id=punch_id).order_by(
            PunchHistory.id,
        ).all()
        assert len(events) == 4
        assert events[-1].old_status == PunchStatus.CLOSED
        assert events[-1].new_status == PunchStatus.IN_PROGRESS
        assert "Previous corrective action" in events[-1].remarks
        audit = CommissioningAuditLog.query.filter_by(
            company_name="Contractor A", entity_type="PunchItem",
            entity_id=punch_id, action="PUNCH_STATUS_CHANGED",
        ).order_by(CommissioningAuditLog.id.desc()).first()
        assert audit.after_json["previous_corrective_action"].startswith("Replaced the damaged gasket")




def test_project_readiness_policy_is_configurable_and_audited(client, app, opera_setup):
    from models_commissioning import CommissioningProject

    _login_id(client, opera_setup["manager"])
    url = f"/commissioning/projects/{opera_setup['project']}/readiness-policy"
    page = client.get(url)
    assert page.status_code == 200
    assert b"Punch categories that block each milestone" in page.data

    response = client.post(url, data={
        "punch_MC": ["C"],
        "punch_RFC": ["A", "C"],
        "punch_RFSU": ["D"],
        "hold_point_blocking_gates": ["RFC"],
        "sheets_MC": ["PRE_COMM_A"],
        "sheets_RFC": ["PRE_COMM_A", "COMM_C"],
        "sheets_RFSU": ["COMM_C", "FUNCTIONAL_TEST"],
        "require_check_sheet_presence": "on",
        "require_all_tasks_complete_for_rfsu": "on",
    })
    assert response.status_code == 302

    with app.app_context():
        project = db.session.get(CommissioningProject, opera_setup["project"])
        assert project.readiness_policy_json["punch_blocking_categories"]["MC"] == ["C"]
        assert project.readiness_policy_json["punch_blocking_categories"]["RFC"] == ["A", "C"]
        assert project.readiness_policy_json["hold_point_blocking_gates"] == ["RFC"]
        audit = CommissioningAuditLog.query.filter_by(
            company_name="Contractor A",
            entity_type="CommissioningProject",
            entity_id=project.id,
            action="READINESS_POLICY_UPDATED",
        ).one()
        assert audit.after_json == project.readiness_policy_json


def test_readiness_policy_changes_punch_blockers_per_gate(client, app, opera_setup):
    from models_commissioning import CommissioningProject
    from services.commissioning_readiness import evaluate_subsystem_readiness

    with app.app_context():
        project = db.session.get(CommissioningProject, opera_setup["project"])
        punch = PunchItem(
            company_name="Contractor A",
            project_id=opera_setup["project"],
            subsystem_id=opera_setup["subsystem"],
            punch_number="POLICY-001",
            category=PunchCategory.C,
            description="Paint damage requiring repair",
            raised_by_id=opera_setup["manager"],
            status=PunchStatus.OPEN,
        )
        db.session.add(punch)
        db.session.commit()

        default_result = evaluate_subsystem_readiness("Contractor A", opera_setup["subsystem"])
        assert default_result.is_ready_for_mc is True

        project.readiness_policy_json = {
            "punch_blocking_categories": {
                "MC": ["C"], "RFC": [], "RFSU": [],
            },
            "hold_point_blocking_gates": [],
            "required_check_sheet_types": {"MC": [], "RFC": [], "RFSU": []},
            "require_check_sheet_presence": False,
            "require_all_tasks_complete_for_rfsu": False,
        }
        db.session.commit()
        configured_result = evaluate_subsystem_readiness("Contractor A", opera_setup["subsystem"])
        assert configured_result.is_ready_for_mc is False
        assert configured_result.is_ready_for_rfc is True
        assert configured_result.is_ready_for_rfsu is True
        assert any(
            issue.gate == "MC" and issue.entity_id == punch.id
            for issue in configured_result.issues
        )


def test_invalid_readiness_policy_fails_closed_and_viewer_cannot_edit(client, app, opera_setup):
    from models_commissioning import CommissioningProject
    from services.commissioning_readiness import evaluate_subsystem_readiness

    _login_id(client, opera_setup["viewer"])
    url = f"/commissioning/projects/{opera_setup['project']}/readiness-policy"
    assert client.get(url).status_code == 403

    with app.app_context():
        project = db.session.get(CommissioningProject, opera_setup["project"])
        project.readiness_policy_json = {
            "punch_blocking_categories": {"MC": ["NOT_A_CATEGORY"]},
        }
        db.session.commit()
        result = evaluate_subsystem_readiness("Contractor A", opera_setup["subsystem"])
        assert result.is_ready_for_mc is False
        assert result.is_ready_for_rfc is False
        assert result.is_ready_for_rfsu is False
        assert any(issue.code == "INVALID_READINESS_POLICY" for issue in result.issues)


def test_project_dossier_index_requirements_are_managed_and_audited(client, app, opera_setup):
    _login_id(client, opera_setup["manager"])
    url = f"/commissioning/projects/{opera_setup['project']}/dossier-requirements"
    created = client.post(url, data={
        "action": "save", "document_type": "P&ID", "discipline": "Process",
        "minimum_count": "2", "require_approved": "on", "require_evidence": "on",
    })
    assert created.status_code == 302
    with app.app_context():
        rule = CommissioningDossierRequirement.query.filter_by(
            company_name="Contractor A", project_id=opera_setup["project"],
            document_type="P&ID", discipline="PROCESS",
        ).one()
        rule_id = rule.id
        assert rule.minimum_count == 2
        assert rule.require_approved is True
        assert rule.require_evidence is True
        event = CommissioningAuditLog.query.filter_by(
            company_name="Contractor A", entity_type="CommissioningDossierRequirement",
            entity_id=rule.id, action="DOSSIER_REQUIREMENT_CREATED",
        ).one()
        assert event.after_json["minimum_count"] == 2

    duplicate = client.post(url, data={
        "action": "save", "document_type": "P&ID", "discipline": "process",
        "minimum_count": "1",
    })
    assert duplicate.status_code == 409

    _login_id(client, opera_setup["viewer"])
    denied = client.post(url, data={
        "action": "save", "document_type": "Datasheet", "minimum_count": "1",
    })
    assert denied.status_code == 403

    _login_id(client, opera_setup["manager"])
    deactivated = client.post(url, data={
        "action": "deactivate", "requirement_id": str(rule_id),
    })
    assert deactivated.status_code == 302
    with app.app_context():
        rule = db.session.get(CommissioningDossierRequirement, rule_id)
        assert rule.is_active is False
        assert CommissioningAuditLog.query.filter_by(
            company_name="Contractor A", entity_type="CommissioningDossierRequirement",
            entity_id=rule_id, action="DOSSIER_REQUIREMENT_DEACTIVATED",
        ).count() == 1


def test_subsystem_dossier_applies_current_document_count_approval_and_evidence_rules(
    client, app, opera_setup,
):
    with app.app_context():
        requirement = CommissioningDossierRequirement(
            company_name="Contractor A", project_id=opera_setup["project"],
            document_type="P&ID", discipline="PROCESS", minimum_count=2,
            require_approved=True, require_evidence=True,
            created_by_id=opera_setup["manager"],
        )
        documents = [
            CommissioningDocument(
                company_name="Contractor A", project_id=opera_setup["project"],
                subsystem_id=opera_setup["subsystem"], document_number="PID-001",
                revision="A", revision_sequence=1, title="Utility P&ID 001",
                document_type="P&ID", discipline="Process",
                status=DocumentStatus.APPROVED, created_by_id=opera_setup["manager"],
            ),
            CommissioningDocument(
                company_name="Contractor A", project_id=opera_setup["project"],
                subsystem_id=opera_setup["subsystem"], document_number="PID-002",
                revision="A", revision_sequence=1, title="Utility P&ID 002",
                document_type="P&ID", discipline="Process",
                status=DocumentStatus.DRAFT, created_by_id=opera_setup["manager"],
            ),
        ]
        db.session.add_all([requirement, *documents])
        db.session.flush()
        db.session.add(CommissioningAttachment(
            company_name="Contractor A", entity_type="CommissioningDocument",
            entity_id=documents[0].id, filename="pid-001.pdf",
            stored_filename="pid-001.pdf", storage_key="test/pid-001.pdf",
            mime_type="application/pdf", file_size=128,
            checksum="a" * 64, uploaded_by_id=opera_setup["manager"],
        ))
        db.session.commit()
        subsystem_id = opera_setup["subsystem"]
        second_document_id = documents[1].id

    _login_id(client, opera_setup["manager"])
    dossier_url = f"/commissioning/projects/{opera_setup['project']}/subsystems/{subsystem_id}/dossier"
    incomplete = client.get(dossier_url)
    assert incomplete.status_code == 200
    assert b"Configured dossier index" in incomplete.data
    assert b"P&amp;ID" in incomplete.data
    assert b"1 / 2" in incomplete.data
    assert b"MISSING" in incomplete.data

    with app.app_context():
        second = db.session.get(CommissioningDocument, second_document_id)
        second.status = DocumentStatus.APPROVED
        db.session.add(CommissioningAttachment(
            company_name="Contractor A", entity_type="CommissioningDocument",
            entity_id=second.id, filename="pid-002.pdf",
            stored_filename="pid-002.pdf", storage_key="test/pid-002.pdf",
            mime_type="application/pdf", file_size=128,
            checksum="b" * 64, uploaded_by_id=opera_setup["manager"],
        ))
        db.session.commit()

    complete_index = client.get(dossier_url)
    assert complete_index.status_code == 200
    assert b"2 / 2" in complete_index.data
    assert b"PASS" in complete_index.data


def test_preservation_plan_inspection_cycle_and_immutable_history(client, app, opera_setup):
    with app.app_context():
        equipment = CommissioningEquipment(
            company_name="Contractor A", project_id=opera_setup["project"],
            subsystem_id=opera_setup["subsystem"], tag_number="P-1001",
            equipment_type="Pump", description="Preservation test pump",
        )
        db.session.add(equipment)
        db.session.commit()
        equipment_id = equipment.id

    _login_id(client, opera_setup["manager"])
    page_url = f"/commissioning/projects/{opera_setup['project']}/preservation"
    assert client.get(page_url).status_code == 200

    create = client.post(f"/commissioning/projects/{opera_setup['project']}/preservation-plans", data={
        "plan_number": "PRES-001",
        "equipment_id": str(equipment_id),
        "activity": "Preserve rotating equipment per OEM instruction",
        "procedure_reference": "OEM-MANUAL-100",
        "procedure_revision": "Rev 4",
        "interval_days": "30",
        "next_due_date": date.today().isoformat(),
        "responsible_company": "Contractor A",
    })
    assert create.status_code == 302

    with app.app_context():
        plan = CommissioningPreservationPlan.query.filter_by(
            company_name="Contractor A", project_id=opera_setup["project"],
            plan_number="PRES-001",
        ).one()
        plan_id = plan.id
        assert plan.status == "ACTIVE"
        assert plan.interval_days == 30

    inspect_url = f"/commissioning/projects/{opera_setup['project']}/preservation-plans/{plan_id}/inspect"
    missing_action = client.post(inspect_url, data={
        "performed_at": date.today().isoformat(),
        "result": "NON_COMPLIANT",
        "findings": "Corrosion inhibitor below required condition",
    })
    assert missing_action.status_code == 400

    non_compliant = client.post(inspect_url, data={
        "performed_at": date.today().isoformat(),
        "result": "NON_COMPLIANT",
        "findings": "Corrosion inhibitor below required condition",
        "corrective_action": "Reapply inhibitor according to OEM procedure",
    })
    assert non_compliant.status_code == 302
    action_required_suspend = client.post(
        f"/commissioning/projects/{opera_setup['project']}/preservation-plans/{plan_id}/status",
        data={"status": "SUSPENDED"},
    )
    assert action_required_suspend.status_code == 409
    action_required_reactivate = client.post(
        f"/commissioning/projects/{opera_setup['project']}/preservation-plans/{plan_id}/status",
        data={"status": "ACTIVE"},
    )
    assert action_required_reactivate.status_code == 409

    with app.app_context():
        plan = db.session.get(CommissioningPreservationPlan, plan_id)
        inspection = CommissioningPreservationInspection.query.filter_by(plan_id=plan_id).one()
        assert plan.status == "ACTION_REQUIRED"
        assert plan.next_due_date == date.today()
        assert inspection.interval_days_snapshot == 30
        assert inspection.procedure_revision_snapshot == "Rev 4"
        inspection.findings = "Tampered"
        with pytest.raises(ValueError, match="append-only"):
            db.session.commit()
        db.session.rollback()

    compliant = client.post(inspect_url, data={
        "performed_at": date.today().isoformat(),
        "result": "COMPLIANT",
        "findings": "Corrective action verified; preservation condition acceptable",
    })
    assert compliant.status_code == 302

    with app.app_context():
        plan = db.session.get(CommissioningPreservationPlan, plan_id)
        inspections = CommissioningPreservationInspection.query.filter_by(plan_id=plan_id).order_by(
            CommissioningPreservationInspection.id,
        ).all()
        assert plan.status == "ACTIVE"
        assert plan.last_performed_at == date.today()
        assert plan.next_due_date == date.today() + timedelta(days=30)
        assert [item.result for item in inspections] == ["NON_COMPLIANT", "COMPLIANT"]
        assert CommissioningAuditLog.query.filter_by(
            company_name="Contractor A", entity_type="CommissioningPreservationInspection",
            action="PRESERVATION_INSPECTION_RECORDED",
        ).count() == 2


def test_preservation_permissions_tenant_scope_and_plan_closure(client, app, opera_setup):
    with app.app_context():
        equipment = CommissioningEquipment(
            company_name="Contractor A", project_id=opera_setup["project"],
            subsystem_id=opera_setup["subsystem"], tag_number="P-1002",
            equipment_type="Valve", description="Preservation permission test",
        )
        db.session.add(equipment)
        db.session.commit()
        equipment_id = equipment.id

    _login_id(client, opera_setup["viewer"])
    page_url = f"/commissioning/projects/{opera_setup['project']}/preservation"
    assert client.get(page_url).status_code == 200
    denied = client.post(f"/commissioning/projects/{opera_setup['project']}/preservation-plans", data={
        "plan_number": "PRES-DENIED", "equipment_id": str(equipment_id),
        "activity": "Test", "procedure_reference": "OEM-REF",
        "procedure_revision": "A", "interval_days": "30",
        "next_due_date": date.today().isoformat(),
    })
    assert denied.status_code == 403

    _login_id(client, opera_setup["outsider"])
    assert client.get(page_url).status_code == 404

    _login_id(client, opera_setup["manager"])
    created = client.post(f"/commissioning/projects/{opera_setup['project']}/preservation-plans", data={
        "plan_number": "PRES-CLOSE", "equipment_id": str(equipment_id),
        "activity": "Valve preservation per approved procedure",
        "procedure_reference": "OEM-VALVE-01", "procedure_revision": "B",
        "interval_days": "45", "next_due_date": date.today().isoformat(),
    })
    assert created.status_code == 302
    with app.app_context():
        plan = CommissioningPreservationPlan.query.filter_by(plan_number="PRES-CLOSE").one()
        plan_id = plan.id

    close = client.post(
        f"/commissioning/projects/{opera_setup['project']}/preservation-plans/{plan_id}/status",
        data={"status": "CLOSED"},
    )
    assert close.status_code == 302
    reopen = client.post(
        f"/commissioning/projects/{opera_setup['project']}/preservation-plans/{plan_id}/status",
        data={"status": "ACTIVE"},
    )
    assert reopen.status_code == 409
    inspect_closed = client.post(
        f"/commissioning/projects/{opera_setup['project']}/preservation-plans/{plan_id}/inspect",
        data={"performed_at": date.today().isoformat(), "result": "COMPLIANT"},
    )
    assert inspect_closed.status_code == 409



def test_subsystem_dossier_pdf_and_zip_exports_are_scoped_and_labelled(
    client, app, opera_setup, tmp_path,
):
    import json
    from io import BytesIO
    from zipfile import ZipFile
    from models import User
    from models_commissioning import CheckSheet, CheckSheetType
    from services.commissioning_storage import resolve_commissioning_upload

    app.config["OPERA_UPLOAD_DIR"] = str(tmp_path)
    with app.app_context():
        manager = db.session.get(User, opera_setup["manager"])
        manager_id = manager.id
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="DOSSIER-CS-001", sheet_type=CheckSheetType.COMM_C,
            title="Dossier export evidence", created_by_id=manager_id,
        )
        db.session.add(sheet)
        db.session.commit()
        sheet_id = sheet.id
    _login_id(client, manager_id)

    uploaded = client.post(
        f"/commissioning/evidence/CheckSheet/{sheet_id}",
        data={"file": (BytesIO(b"%PDF-1.7\nDossier evidence"), "test-evidence.pdf")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 302

    base = f"/commissioning/projects/{opera_setup['project']}/subsystems/{opera_setup['subsystem']}/dossier"
    pdf = client.get(base + "/export.pdf")
    assert pdf.status_code == 200
    assert pdf.data.startswith(b"%PDF-")
    assert pdf.headers["Cache-Control"] == "private, no-store"

    bundle = client.get(base + "/export.zip")
    assert bundle.status_code == 200
    assert bundle.headers["Content-Type"].startswith("application/zip")
    with ZipFile(BytesIO(bundle.data)) as archive:
        assert "dossier.pdf" in archive.namelist()
        assert "manifest.json" in archive.namelist()
        evidence_names = [name for name in archive.namelist() if name.startswith("evidence/")]
        assert len(evidence_names) == 1
        assert archive.read(evidence_names[0]) == b"%PDF-1.7\nDossier evidence"
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["export_classification"] == "UNCONTROLLED_WORKING_EXPORT"
        assert manifest["project"]["code"] == "FLOW-01"
        assert manifest["subsystem"]["code"] == "SUB-01"
        assert manifest["counts"]["evidence_files"] == 1

    with app.app_context():
        attachment = CommissioningAttachment.query.filter_by(
            company_name="Contractor A", entity_type="CheckSheet", entity_id=sheet_id,
        ).one()
        resolve_commissioning_upload(attachment.storage_key).unlink()
    missing_evidence = client.get(base + "/export.zip")
    assert missing_evidence.status_code == 409

    _login_id(client, opera_setup["outsider"])
    denied = client.get(base + "/export.pdf")
    assert denied.status_code == 404


def test_checksheet_template_approval_revision_and_execution_snapshot(client, app, opera_setup):
    _login_id(client, opera_setup["manager"])
    project_id = opera_setup["project"]
    template_url = f"/commissioning/projects/{project_id}/checksheet-templates"
    items_v1 = [
        {
            "description": "Verify equipment tag and nameplate",
            "expected_result": "Matches approved equipment register",
            "acceptance_criteria": "No mismatch",
            "unit": None,
            "witness_required": False,
            "mandatory": True,
        },
        {
            "description": "Record vibration reading",
            "expected_result": "Within approved OEM limit",
            "acceptance_criteria": "Use current OEM procedure",
            "unit": "mm/s",
            "witness_required": True,
            "mandatory": False,
        },
    ]
    created = client.post(template_url, data={
        "template_code": "PUMP-CCK-01",
        "title": "Pump conformity check",
        "sheet_type": "PRE_COMM_A",
        "discipline": "MECHANICAL",
        "acceptance_criteria": "Apply approved project/OEM procedure",
        "items_json": json.dumps(items_v1),
    })
    assert created.status_code == 302

    with app.app_context():
        template = CommissioningCheckSheetTemplate.query.filter_by(
            company_name="Contractor A", project_id=project_id,
            template_code="PUMP-CCK-01", revision=1,
        ).one()
        template_id = template.id
        assert template.status == "DRAFT"

    approved = client.post(
        f"/commissioning/projects/{project_id}/checksheet-templates/{template_id}/approve",
    )
    assert approved.status_code == 302

    with app.app_context():
        template = db.session.get(CommissioningCheckSheetTemplate, template_id)
        assert template.status == "APPROVED"
        assert template.approved_by_id == opera_setup["manager"]

    created_sheet = client.post(f"/commissioning/projects/{project_id}/checksheets/new", data={
        "title": "Pump 1001 conformity",
        "sheet_type": "PRE_COMM_A",
        "subsystem_id": str(opera_setup["subsystem"]),
        "equipment_id": "",
        "template_id": str(template_id),
    })
    assert created_sheet.status_code == 302
    sheet_location = created_sheet.headers["Location"]
    sheet_id = int(sheet_location.rsplit("/", 1)[-1])

    with app.app_context():
        sheet = db.session.get(CheckSheet, sheet_id)
        sheet_items = CheckSheetItem.query.filter_by(check_sheet_id=sheet_id).order_by(
            CheckSheetItem.sequence,
        ).all()
        assert sheet.template_id == template_id
        assert sheet.discipline == "MECHANICAL"
        assert sheet.template_revision_snapshot == 1
        assert sheet.template_title_snapshot == "Pump conformity check"
        assert sheet.template_snapshot_json["template_code"] == "PUMP-CCK-01"
        assert len(sheet_items) == 2
        assert sheet_items[0].mandatory is True
        assert sheet_items[1].mandatory is False
        assert sheet_items[1].unit == "mm/s"
        assert sheet_items[1].witness_required is True
        assert sheet_items[1].measurement_type == "QUALITATIVE"

    revised = client.post(
        f"/commissioning/projects/{project_id}/checksheet-templates/{template_id}/revise",
    )
    assert revised.status_code == 302
    with app.app_context():
        revision_2 = CommissioningCheckSheetTemplate.query.filter_by(
            company_name="Contractor A", project_id=project_id,
            template_code="PUMP-CCK-01", revision=2,
        ).one()
        revision_2_id = revision_2.id

    items_v2 = items_v1 + [{
        "description": "Verify coupling guard installation",
        "expected_result": "Guard installed and secured",
        "acceptance_criteria": "No exposed rotating parts",
        "unit": None,
        "witness_required": False,
        "mandatory": True,
    }]
    updated = client.post(
        f"/commissioning/projects/{project_id}/checksheet-templates/{revision_2_id}/update",
        data={
            "title": "Pump conformity check",
            "discipline": "MECHANICAL",
            "acceptance_criteria": "Apply approved project/OEM procedure",
            "items_json": json.dumps(items_v2),
        },
    )
    assert updated.status_code == 302
    approved_v2 = client.post(
        f"/commissioning/projects/{project_id}/checksheet-templates/{revision_2_id}/approve",
    )
    assert approved_v2.status_code == 302

    with app.app_context():
        revision_1 = db.session.get(CommissioningCheckSheetTemplate, template_id)
        revision_2 = db.session.get(CommissioningCheckSheetTemplate, revision_2_id)
        old_sheet = db.session.get(CheckSheet, sheet_id)
        assert revision_1.status == "RETIRED"
        assert revision_2.status == "APPROVED"
        assert old_sheet.template_revision_snapshot == 1
        assert len(old_sheet.template_snapshot_json["items"]) == 2
        revision_2.title = "Tampered approved template"
        with pytest.raises(ValueError, match="immutable"):
            db.session.commit()
        db.session.rollback()


def test_checksheet_template_validation_and_template_type_mismatch(client, app, opera_setup):
    _login_id(client, opera_setup["manager"])
    project_id = opera_setup["project"]
    url = f"/commissioning/projects/{project_id}/checksheet-templates"
    invalid = client.post(url, data={
        "template_code": "BAD-TEMPLATE", "title": "Invalid template",
        "sheet_type": "PRE_COMM_A", "items_json": "not-json",
    })
    assert invalid.status_code == 400

    created = client.post(url, data={
        "template_code": "VALVE-CCK-01", "title": "Valve conformity",
        "sheet_type": "PRE_COMM_A", "discipline": "MECHANICAL",
        "items_json": json.dumps([{"description": "Verify valve tag", "mandatory": True}]),
    })
    assert created.status_code == 302
    with app.app_context():
        template = CommissioningCheckSheetTemplate.query.filter_by(
            company_name="Contractor A", project_id=project_id,
            template_code="VALVE-CCK-01",
        ).one()
        template_id = template.id
    assert client.post(
        f"/commissioning/projects/{project_id}/checksheet-templates/{template_id}/approve",
    ).status_code == 302
    mismatch = client.post(f"/commissioning/projects/{project_id}/checksheets/new", data={
        "title": "Wrong type", "sheet_type": "PRE_COMM_B",
        "subsystem_id": str(opera_setup["subsystem"]), "template_id": str(template_id),
    })
    assert mismatch.status_code == 400
    discipline_mismatch = client.post(f"/commissioning/projects/{project_id}/checksheets/new", data={
        "title": "Wrong discipline", "sheet_type": "PRE_COMM_A",
        "discipline": "ELECTRICAL",
        "subsystem_id": str(opera_setup["subsystem"]), "template_id": str(template_id),
    })
    assert discipline_mismatch.status_code == 400


def test_controlled_dossier_revision_review_issue_and_exports(client, app, opera_setup):
    from io import BytesIO
    from zipfile import ZipFile

    with app.app_context():
        manager = db.session.get(User, opera_setup["manager"])
        client_rep = db.session.get(User, opera_setup["client"])
        manager_id = manager.id
        client_id = client_rep.id
        issuer = _user("Contractor A", "opera-flow-dossier-issuer@example.com", "Dossier Issuer")
        db.session.add(issuer)
        db.session.flush()
        db.session.add(CommissioningMembership(
            company_name="Contractor A", project_id=opera_setup["project"],
            user_id=issuer.id, role=MembershipRole.COMMISSIONING_MANAGER, is_active=True,
        ))
        sheet = CheckSheet(
            company_name="Contractor A", project_id=opera_setup["project"],
            system_id=opera_setup["system"], subsystem_id=opera_setup["subsystem"],
            sheet_number="DOSSIER-CTRL-CS-001", sheet_type=CheckSheetType.PRE_COMM_A,
            title="Approved dossier check sheet", created_by_id=manager.id,
        )
        document = CommissioningDocument(
            company_name="Contractor A", project_id=opera_setup["project"],
            subsystem_id=opera_setup["subsystem"], document_number="DOSSIER-CTRL-DOC-001",
            revision="A", revision_sequence=1, title="Approved P&ID",
            document_type="P&ID", discipline="PROCESS", status=DocumentStatus.APPROVED,
            created_by_id=manager.id,
        )
        db.session.add_all([sheet, document])
        db.session.commit()
        sheet.status = CheckSheetStatus.SIGNED_OFF
        sheet.signed_by_client_id = client_id
        sheet.signed_by_contractor_id = manager_id
        sheet.signed_at = datetime.utcnow()
        db.session.commit()
        issuer_id = issuer.id
        project_id = opera_setup["project"]
        subsystem_id = opera_setup["subsystem"]

    _login_id(client, manager_id)
    base = f"/commissioning/projects/{project_id}/subsystems/{subsystem_id}/dossier"
    page = client.get(base)
    assert page.status_code == 200
    created = client.post(base.replace("/dossier", "/dossiers"))
    assert created.status_code == 302
    with app.app_context():
        revision = CommissioningDossierRevision.query.filter_by(
            company_name="Contractor A", project_id=project_id, subsystem_id=subsystem_id,
        ).one()
        assert revision.status == DossierRevisionStatus.DRAFT
        assert len(revision.snapshot_sha256) == 64
        assert revision.snapshot_json["export_classification"] == "CONTROLLED_DOSSIER_REVISION"
        revision_id = revision.id

    submitted = client.post(f"/commissioning/dossiers/{revision_id}/submit")
    assert submitted.status_code == 302

    _login_id(client, client_id)
    approved = client.post(
        f"/commissioning/dossiers/{revision_id}/decision",
        data={"decision": "APPROVE", "comments": "Reviewed against the configured dossier index."},
    )
    assert approved.status_code == 302
    with app.app_context():
        revision = db.session.get(CommissioningDossierRevision, revision_id)
        assert revision.status == DossierRevisionStatus.APPROVED
        assert revision.approved_by_id == client_id
        assert CommissioningDossierReview.query.filter_by(
            dossier_revision_id=revision_id, decision=DossierReviewDecision.APPROVED,
        ).count() == 1

    _login_id(client, issuer_id)
    issued = client.post(f"/commissioning/dossiers/{revision_id}/issue")
    assert issued.status_code == 302
    with app.app_context():
        revision = db.session.get(CommissioningDossierRevision, revision_id)
        assert revision.status == DossierRevisionStatus.ISSUED
        assert revision.issued_by_id == issuer_id
        assert revision.snapshot_json["export_classification"] == "CONTROLLED_DOSSIER_REVISION"
        revision.snapshot_sha256 = "0" * 64
        with pytest.raises(ValueError, match="immutable"):
            db.session.commit()
        db.session.rollback()

    pdf = client.get(f"/commissioning/dossiers/{revision_id}/export.pdf")
    assert pdf.status_code == 200
    assert pdf.data.startswith(b"%PDF-")
    bundle = client.get(f"/commissioning/dossiers/{revision_id}/export.zip")
    assert bundle.status_code == 200
    with ZipFile(BytesIO(bundle.data)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["dossier_control"]["status"] == "ISSUED"
        assert manifest["dossier_control"]["revision_number"] == 1
        assert manifest["export_classification"] == "CONTROLLED_DOSSIER_REVISION"


def test_controlled_dossier_requires_readiness_and_rejection_reason(client, app, opera_setup):
    _login_id(client, opera_setup["manager"])
    project_id = opera_setup["project"]
    subsystem_id = opera_setup["subsystem"]
    base = f"/commissioning/projects/{project_id}/subsystems/{subsystem_id}/dossier"
    created = client.post(base.replace("/dossier", "/dossiers"))
    assert created.status_code == 302
    with app.app_context():
        revision = CommissioningDossierRevision.query.filter_by(
            company_name="Contractor A", project_id=project_id, subsystem_id=subsystem_id,
        ).one()
        revision_id = revision.id
    assert client.post(f"/commissioning/dossiers/{revision_id}/submit").status_code == 302

    _login_id(client, opera_setup["client"])
    blocked_approval = client.post(
        f"/commissioning/dossiers/{revision_id}/decision",
        data={"decision": "APPROVE", "comments": "Attempted approval"},
    )
    assert blocked_approval.status_code == 409
    missing_reason = client.post(
        f"/commissioning/dossiers/{revision_id}/decision",
        data={"decision": "REJECT", "comments": ""},
    )
    assert missing_reason.status_code == 400
    rejected = client.post(
        f"/commissioning/dossiers/{revision_id}/decision",
        data={"decision": "REJECT", "comments": "Mandatory check sheets and documents are missing."},
    )
    assert rejected.status_code == 302
    with app.app_context():
        revision = db.session.get(CommissioningDossierRevision, revision_id)
        assert revision.status == DossierRevisionStatus.REJECTED
        assert "missing" in revision.rejection_reason.lower()

    _login_id(client, opera_setup["manager"])
    next_revision = client.post(base.replace("/dossier", "/dossiers"))
    assert next_revision.status_code == 302
    with app.app_context():
        revisions = CommissioningDossierRevision.query.filter_by(
            company_name="Contractor A", project_id=project_id, subsystem_id=subsystem_id,
        ).order_by(CommissioningDossierRevision.revision_number).all()
        assert [item.revision_number for item in revisions] == [1, 2]
        assert revisions[1].supersedes_id == revisions[0].id


def test_controlled_dossier_permissions_and_tenant_isolation(client, app, opera_setup):
    project_id = opera_setup["project"]
    subsystem_id = opera_setup["subsystem"]
    base = f"/commissioning/projects/{project_id}/subsystems/{subsystem_id}/dossier"
    _login_id(client, opera_setup["viewer"])
    denied_create = client.post(base.replace("/dossier", "/dossiers"))
    assert denied_create.status_code == 403

    _login_id(client, opera_setup["outsider"])
    hidden_page = client.get(base)
    assert hidden_page.status_code == 404


def test_preservation_compliance_report_filters_and_safe_csv(client, app, opera_setup):
    with app.app_context():
        equipment = CommissioningEquipment(
            company_name="Contractor A", project_id=opera_setup["project"],
            subsystem_id=opera_setup["subsystem"], tag_number="P-REPORT-001",
            equipment_type="Pump", description="Preservation reporting pump",
        )
        db.session.add(equipment)
        db.session.commit()
        equipment_id = equipment.id

    _login_id(client, opera_setup["manager"])
    base = f"/commissioning/projects/{opera_setup['project']}"
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    soon = (date.today() + timedelta(days=3)).isoformat()
    overdue = client.post(f"{base}/preservation-plans", data={
        "plan_number": "PRES-REPORT-OVERDUE",
        "equipment_id": str(equipment_id),
        "activity": '=HYPERLINK("https://example.invalid")',
        "procedure_reference": "OEM-PRES-REPORT",
        "procedure_revision": "A",
        "interval_days": "30",
        "next_due_date": yesterday,
    })
    due_soon = client.post(f"{base}/preservation-plans", data={
        "plan_number": "PRES-REPORT-SOON",
        "equipment_id": str(equipment_id),
        "activity": "Check desiccant condition per approved procedure",
        "procedure_reference": "OEM-PRES-REPORT",
        "procedure_revision": "A",
        "interval_days": "30",
        "next_due_date": soon,
    })
    assert overdue.status_code == 302
    assert due_soon.status_code == 302

    report_url = f"{base}/preservation/report"
    all_rows = client.get(report_url)
    assert all_rows.status_code == 200
    assert b"Preservation Compliance Report" in all_rows.data
    assert b"PRES-REPORT-OVERDUE" in all_rows.data
    assert b"PRES-REPORT-SOON" in all_rows.data
    overdue_rows = client.get(f"{report_url}?status=OVERDUE")
    assert overdue_rows.status_code == 200
    assert b"PRES-REPORT-OVERDUE" in overdue_rows.data
    assert b"PRES-REPORT-SOON" not in overdue_rows.data

    csv_report = client.get(f"{base}/preservation/report.csv?status=OVERDUE")
    assert csv_report.status_code == 200
    assert csv_report.mimetype == "text/csv"
    assert csv_report.data.startswith(b"\xef\xbb\xbf")
    assert b"PRES-REPORT-OVERDUE" in csv_report.data
    assert b"PRES-REPORT-SOON" not in csv_report.data
    assert b"'=HYPERLINK" in csv_report.data

    invalid_filter = client.get(f"{report_url}?status=UNRECOGNIZED")
    assert invalid_filter.status_code == 400
    invalid_equipment = client.get(f"{report_url}?equipment_id=not-a-number")
    assert invalid_equipment.status_code == 400

    active_rows = client.get(f"{report_url}?status=ACTIVE")
    assert active_rows.status_code == 200
    # ACTIVE is the plan lifecycle state, so both overdue and future-due active plans remain visible.
    assert b"PRES-REPORT-OVERDUE" in active_rows.data
    assert b"PRES-REPORT-SOON" in active_rows.data
    equipment_rows = client.get(f"{report_url}?equipment_id={equipment_id}")
    assert equipment_rows.status_code == 200
    assert b"PRES-REPORT-OVERDUE" in equipment_rows.data
    assert b"PRES-REPORT-SOON" in equipment_rows.data
    assert b"private, no-store" in csv_report.headers.get("Cache-Control", "").encode()
    assert csv_report.headers.get("X-Content-Type-Options") == "nosniff"

    _login_id(client, opera_setup["viewer"])
    assert client.get(report_url).status_code == 200
    viewer_csv = client.get(f"{base}/preservation/report.csv")
    assert viewer_csv.status_code == 200
    _login_id(client, opera_setup["outsider"])
    assert client.get(report_url).status_code == 404


def test_numeric_checksheet_measurement_limits_and_audit(client, app, opera_setup):
    _login_id(client, opera_setup["manager"])
    project_id = opera_setup["project"]
    template_url = f"/commissioning/projects/{project_id}/checksheet-templates"
    items = [{
        "description": "Measure pump vibration",
        "expected_result": "Within approved OEM vibration range",
        "acceptance_criteria": "Approved project/OEM limit",
        "unit": "mm/s",
        "measurement_type": "NUMERIC",
        "minimum_value": "2.5",
        "maximum_value": "5.0",
        "mandatory": True,
        "witness_required": False,
    }]
    created = client.post(template_url, data={
        "template_code": "PUMP-MEAS-01",
        "title": "Pump vibration measurement",
        "sheet_type": "PRE_COMM_A",
        "discipline": "MECHANICAL",
        "items_json": json.dumps(items),
    })
    assert created.status_code == 302
    with app.app_context():
        template = CommissioningCheckSheetTemplate.query.filter_by(
            company_name="Contractor A", project_id=project_id,
            template_code="PUMP-MEAS-01",
        ).one()
        template_id = template.id
    assert client.post(
        f"/commissioning/projects/{project_id}/checksheet-templates/{template_id}/approve",
    ).status_code == 302
    created_sheet = client.post(f"/commissioning/projects/{project_id}/checksheets/new", data={
        "title": "Pump vibration reading",
        "sheet_type": "PRE_COMM_A",
        "subsystem_id": str(opera_setup["subsystem"]),
        "template_id": str(template_id),
    })
    assert created_sheet.status_code == 302
    sheet_id = int(created_sheet.headers["Location"].rsplit("/", 1)[-1])
    with app.app_context():
        item = CheckSheetItem.query.filter_by(check_sheet_id=sheet_id).one()
        item_id = item.id
        assert item.measurement_type == "NUMERIC"
        assert float(item.minimum_value) == 2.5
        assert float(item.maximum_value) == 5.0
    assert client.post(f"/commissioning/checksheets/{sheet_id}/issue").status_code == 302

    out_of_range_ok = client.post(
        f"/commissioning/checksheets/{sheet_id}/items/{item_id}/result",
        data={"measured_value": "5.6", "result_status": "OK"},
    )
    assert out_of_range_ok.status_code == 400
    recorded_nok = client.post(
        f"/commissioning/checksheets/{sheet_id}/items/{item_id}/result",
        data={"measured_value": "5.6", "result_status": "NOK"},
    )
    assert recorded_nok.status_code == 302
    with app.app_context():
        item = db.session.get(CheckSheetItem, item_id)
        assert float(item.measured_value) == 5.6
        assert item.result_status == ItemResultStatus.NOK
    valid_measurement = client.post(
        f"/commissioning/checksheets/{sheet_id}/items/{item_id}/result",
        data={"measured_value": "3.75", "result_status": "OK"},
    )
    assert valid_measurement.status_code == 302
    with app.app_context():
        item = db.session.get(CheckSheetItem, item_id)
        assert float(item.measured_value) == 3.75
        assert item.actual_result == "3.75"
        assert item.unit == "mm/s"
        audit = CommissioningAuditLog.query.filter_by(
            entity_type="CheckSheetItem", entity_id=item_id,
            action="CHECKSHEET_ITEM_RESULT",
        ).order_by(CommissioningAuditLog.id.desc()).first()
        assert audit.after_json["measured_value"] == "3.75000000"
        assert audit.after_json["measurement_type"] == "NUMERIC"
        assert audit.after_json["minimum_value"] == "2.50000000"
        assert audit.after_json["maximum_value"] == "5.00000000"

    not_applicable = client.post(
        f"/commissioning/checksheets/{sheet_id}/items/{item_id}/result",
        data={"result_status": "NA"},
    )
    assert not_applicable.status_code == 302
    with app.app_context():
        item = db.session.get(CheckSheetItem, item_id)
        assert item.result_status == ItemResultStatus.NA
        assert item.measured_value is None
        sheet = db.session.get(CheckSheet, sheet_id)
        sheet.status = CheckSheetStatus.SIGNED_OFF
        sheet.signed_by_client_id = opera_setup["client"]
        sheet.signed_by_contractor_id = opera_setup["manager"]
        sheet.signed_at = datetime.utcnow()
        db.session.commit()

    revised_sheet = client.post(
        f"/commissioning/checksheets/{sheet_id}/revise",
        data={"reason": "Preserve numeric acceptance limits in the next revision"},
    )
    assert revised_sheet.status_code == 302
    revised_sheet_id = int(revised_sheet.headers["Location"].rsplit("/", 1)[-1])
    with app.app_context():
        revised_item = CheckSheetItem.query.filter_by(check_sheet_id=revised_sheet_id).one()
        assert revised_item.measurement_type == "NUMERIC"
        assert float(revised_item.minimum_value) == 2.5
        assert float(revised_item.maximum_value) == 5.0
        assert revised_item.measured_value is None
        assert revised_item.result_status == ItemResultStatus.PENDING

    invalid_limits = client.post(template_url, data={
        "template_code": "PUMP-MEAS-BAD",
        "title": "Invalid vibration template",
        "sheet_type": "PRE_COMM_A",
        "discipline": "MECHANICAL",
        "items_json": json.dumps([{
            "description": "Invalid range", "unit": "mm/s",
            "measurement_type": "NUMERIC",
            "minimum_value": "9", "maximum_value": "2",
            "mandatory": True,
        }]),
    })
    assert invalid_limits.status_code == 400

    unsupported_precision = client.post(template_url, data={
        "template_code": "PUMP-MEAS-PRECISION",
        "title": "Unsupported measurement precision",
        "sheet_type": "PRE_COMM_A",
        "discipline": "MECHANICAL",
        "items_json": json.dumps([{
            "description": "Excess precision", "unit": "mm/s",
            "measurement_type": "NUMERIC",
            "minimum_value": "0.123456789", "mandatory": True,
        }]),
    })
    assert unsupported_precision.status_code == 400

    missing_unit = client.post(template_url, data={
        "template_code": "PUMP-MEAS-NOUNIT",
        "title": "Missing unit template",
        "sheet_type": "PRE_COMM_A",
        "discipline": "MECHANICAL",
        "items_json": json.dumps([{
            "description": "Missing unit", "measurement_type": "NUMERIC",
            "minimum_value": "0", "maximum_value": "10", "mandatory": True,
        }]),
    })
    assert missing_unit.status_code == 400
