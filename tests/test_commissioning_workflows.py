"""End-to-end tests for OPERA operational workflows."""
from datetime import datetime

import pytest

from extensions import db
from models import AccessLevel, User
from models_commissioning import (
    CommissioningProject, CommissioningSystem, CommissioningSubsystem,
    CommissioningMembership, MembershipRole, CheckSheet, CheckSheetItem,
    CheckSheetType, CheckSheetStatus, ItemResultStatus, PunchItem,
    PunchCategory, PunchSeverity, PunchStatus, CommissioningTask,
    CommissioningTaskType, CommissioningTaskStatus, CommissioningTaskDependency, ProgressSnapshot, CommissioningAuditLog,
    CommissioningDocument, CommissioningDocumentReview, DocumentStatus,
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



def test_mc_rf_certificates_capture_immutable_issue_time_evidence(client, app, opera_setup):
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
        f"/commissioning/handover/{package_id}/certificates/RF",
    )
    assert certificate_page.status_code == 200
    assert b"Ready for Commissioning Certificate" in certificate_page.data
    assert b"MC-CERT-001" not in certificate_page.data

    with app.app_context():
        mc_certificate = db.session.get(CommissioningCertificate, mc_certificate_id)
        assert mc_certificate.snapshot_json["readiness"]["pending_hold_points"] == 0
        rf_certificate = CommissioningCertificate.query.filter_by(
            package_id=package_id, certificate_type="RF",
        ).one()
        assert rf_certificate.snapshot_json["readiness"]["pending_hold_points"] == 0
        assert rf_certificate.snapshot_json["witness_points"][0]["status"] == "RELEASED"
        rf_certificate.snapshot_json = {"tampered": True}
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


