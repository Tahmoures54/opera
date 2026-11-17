"""OPERA operational workflows: membership, check sheets, punch, witness and handover."""
from datetime import date, datetime
from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from extensions import db
from models import User
from models_commissioning import (
    CommissioningMembership, CommissioningProject, CommissioningSystem, CommissioningSubsystem, CommissioningEquipment, CommissioningTask, CommissioningTaskDependency, CommissioningTaskType, CommissioningTaskStatus,
    CommissioningDocument, CommissioningDocumentReview, DocumentStatus,
    CheckSheet, CheckSheetItem, CheckSheetRevision,
    CheckSheetType, CheckSheetStatus, ItemResultStatus, MembershipRole,
    PunchItem, PunchHistory, PunchCategory, PunchSeverity, PunchStatus,
    WitnessPoint, WitnessType, WitnessStatus, HandoverPackage, HandoverStatus,
    ProgressSnapshot, CommissioningSignature, CommissioningAttachment,
)
from services.commissioning_access import (
    add_audit_event, get_project, has_permission,
)
from services.commissioning_storage import store_commissioning_upload, resolve_commissioning_upload
from services.commissioning_number_service import (
    next_checksheet_number, next_punch_number,
)
from blueprints.commissioning import commissioning_bp


def _need(project_id, *permissions):
    get_project(project_id)
    if not any(has_permission(project_id, permission) for permission in permissions):
        abort(403)


def _enum(enum_type, value, field):
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        abort(400, description=f"Invalid {field}")


def _required(name, limit=5000):
    value = (request.form.get(name) or "").strip()
    if not value:
        abort(400, description=f"{name} is required")
    if len(value) > limit:
        abort(400, description=f"{name} is too long")
    return value


def _date(name):
    value = (request.form.get(name) or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        abort(400, description=f"Invalid {name}")


def _sheet(sheet_id):
    sheet = CheckSheet.query.filter_by(
        id=sheet_id, company_name=current_user.company_name
    ).first_or_404()
    _need(sheet.project_id, "checksheets.view", "checksheets.manage",
          "checksheets.create", "checksheets.fill", "checksheets.sign")
    return sheet


def _punch(punch_id):
    punch = PunchItem.query.filter_by(
        id=punch_id, company_name=current_user.company_name
    ).first_or_404()
    _need(punch.project_id, "punch.view", "punch.raise", "punch.assign",
          "punch.verify", "project.manage")
    return punch


@commissioning_bp.get("/projects/<int:project_id>/operations")
@login_required
def operations(project_id):
    _need(project_id, "structure.view", "project.manage", "checksheets.view",
          "checksheets.manage", "checksheets.create", "punch.view", "punch.raise",
          "witness.view", "witness.manage", "handover.view", "handover.manage",
          "reports.view")
    project = get_project(project_id)
    systems = CommissioningSystem.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).filter(CommissioningSystem.status != "ARCHIVED").order_by(CommissioningSystem.system_code).all()
    sheets = CheckSheet.query.filter_by(company_name=project.company_name, project_id=project.id).order_by(CheckSheet.created_at.desc()).all()
    punches = PunchItem.query.filter_by(company_name=project.company_name, project_id=project.id).order_by(PunchItem.raised_at.desc()).all()
    witnesses = WitnessPoint.query.filter_by(company_name=project.company_name, project_id=project.id).order_by(WitnessPoint.scheduled_at.desc()).all()
    packages = HandoverPackage.query.filter_by(company_name=project.company_name, project_id=project.id).order_by(HandoverPackage.created_at.desc()).all()
    snapshots = ProgressSnapshot.query.filter_by(company_name=project.company_name, project_id=project.id).order_by(ProgressSnapshot.snapshot_date.desc()).limit(12).all()
    members = CommissioningMembership.query.filter_by(company_name=project.company_name, project_id=project.id, is_active=True).all()
    punch_ids = [item.id for item in punches]
    package_ids = [item.id for item in packages]
    evidence = CommissioningAttachment.query.filter(
        CommissioningAttachment.company_name == project.company_name,
        CommissioningAttachment.entity_type.in_(["PunchItem", "HandoverPackage"]),
        CommissioningAttachment.entity_id.in_(punch_ids + package_ids or [-1]),
    ).order_by(CommissioningAttachment.uploaded_at.desc()).all()
    evidence_by_entity = {}
    for attachment in evidence:
        evidence_by_entity.setdefault((attachment.entity_type, attachment.entity_id), []).append(attachment)
    users = User.query.filter_by(company_name=project.company_name).order_by(User.full_name).all()
    subsystems = (CommissioningSubsystem.query
        .join(CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id)
        .filter(CommissioningSubsystem.company_name == project.company_name,
                CommissioningSystem.project_id == project.id,
                CommissioningSubsystem.status != "ARCHIVED")
        .order_by(CommissioningSubsystem.subsystem_code).all())
    system_by_id = {item.id: item for item in systems}
    subsystem_by_id = {item.id: item for item in subsystems}
    total = len(sheets)
    signed = sum(1 for item in sheets if item.status == CheckSheetStatus.SIGNED_OFF)
    punch_open = sum(1 for item in punches if item.status not in (PunchStatus.VERIFIED, PunchStatus.WAIVED))
    percent = round((signed / total) * 100, 2) if total else 0.0
    total_sheet_weight = sum(sheet.sheet_weight for sheet in sheets)
    weighted_progress = round(
        sum(sheet.sheet_weight for sheet in sheets if sheet.status == CheckSheetStatus.SIGNED_OFF)
        / total_sheet_weight * 100, 2
    ) if total_sheet_weight else 0.0
    return render_template(
        "commissioning/operations.html", project=project, sheets=sheets,
        punches=punches, witnesses=witnesses, packages=packages, snapshots=snapshots, members=members,
        users=users, project_users=[user for user in users if user.id in {member.user_id for member in members}],
        systems=systems, subsystems=subsystems, system_by_id=system_by_id,
        subsystem_by_id=subsystem_by_id, roles=list(MembershipRole),
        evidence_by_entity=evidence_by_entity,
        can_upload_punch_evidence=any(has_permission(project.id, p) for p in ("punch.raise", "punch.assign", "punch.verify")),
        can_upload_handover_evidence=any(has_permission(project.id, p) for p in ("handover.manage", "handover.accept")),
        witness_items=CheckSheetItem.query.join(CheckSheet, CheckSheet.id == CheckSheetItem.check_sheet_id).filter(CheckSheet.company_name == project.company_name, CheckSheet.project_id == project.id).order_by(CheckSheet.sheet_number, CheckSheetItem.sequence).all(),
        sheet_types=list(CheckSheetType), punch_categories=list(PunchCategory),
        punch_severities=list(PunchSeverity), witness_types=list(WitnessType),
        progress=percent, weighted_progress=weighted_progress,
        signed=signed, total=total, punch_open=punch_open,
    )


@commissioning_bp.post("/projects/<int:project_id>/members")
@login_required
def add_member(project_id):
    _need(project_id, "members.manage", "project.manage")
    project = get_project(project_id)
    try:
        user_id = int(_required("user_id", 20))
    except ValueError:
        abort(400, description="Invalid user")
    user = User.query.filter_by(id=user_id, company_name=project.company_name).first()
    if not user:
        abort(404, description="User not found in this company")
    role = _enum(MembershipRole, _required("role", 50), "role")
    membership = CommissioningMembership.query.filter_by(
        company_name=project.company_name, project_id=project.id, user_id=user.id
    ).first()
    if membership:
        membership.role, membership.is_active = role, True
    else:
        membership = CommissioningMembership(
            company_name=project.company_name, project_id=project.id,
            user_id=user.id, role=role, is_active=True, created_by_id=current_user.id,
        )
        db.session.add(membership)
    add_audit_event(project.company_name, "CommissioningMembership", user.id,
                    "MEMBER_ASSIGNED", after={"role": role.value, "project_id": project.id})
    db.session.commit()
    flash("Project membership updated successfully.", "success")
    return redirect(url_for("commissioning.operations", project_id=project.id))


@commissioning_bp.post("/projects/<int:project_id>/members/<int:membership_id>/deactivate")
@login_required
def deactivate_member(project_id, membership_id):
    _need(project_id, "members.manage", "project.manage")
    member = CommissioningMembership.query.filter_by(
        id=membership_id, project_id=project_id, company_name=current_user.company_name
    ).first_or_404()
    if member.user_id == current_user.id and member.role == MembershipRole.COMMISSIONING_MANAGER:
        other_managers = CommissioningMembership.query.filter_by(
            project_id=project_id, company_name=current_user.company_name,
            role=MembershipRole.COMMISSIONING_MANAGER, is_active=True
        ).filter(CommissioningMembership.user_id != current_user.id).count()
        if not other_managers:
            abort(409, description="Assign another manager before removing your own access")
    member.is_active = False
    add_audit_event(member.company_name, "CommissioningMembership", member.user_id,
                    "MEMBER_DEACTIVATED", after={"project_id": project_id})
    db.session.commit()
    return redirect(url_for("commissioning.operations", project_id=project_id))


@commissioning_bp.route("/projects/<int:project_id>/checksheets/new", methods=["POST"])
@login_required
def create_checksheet(project_id):
    _need(project_id, "checksheets.create", "checksheets.manage")
    project = get_project(project_id)
    subsystem_id = int(_required("subsystem_id", 20))
    subsystem = CommissioningSubsystem.query.join(CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id).filter(
        CommissioningSubsystem.id == subsystem_id,
        CommissioningSubsystem.company_name == project.company_name,
        CommissioningSystem.project_id == project.id,
    ).first_or_404()
    sheet_type = _enum(CheckSheetType, _required("sheet_type", 30), "sheet type")
    sheet_number = next_checksheet_number(project.company_name, project.project_code, sheet_type)
    sheet = CheckSheet(
        company_name=project.company_name, project_id=project.id,
        system_id=subsystem.system_id, subsystem_id=subsystem.id,
        sheet_number=sheet_number, sheet_type=sheet_type,
        title=_required("title", 200), created_by_id=current_user.id,
        status=CheckSheetStatus.DRAFT,
    )
    db.session.add(sheet)
    db.session.flush()
    add_audit_event(project.company_name, "CheckSheet", sheet.id, "CHECKSHEET_CREATED",
                    after={"sheet_number": sheet_number, "revision": 0})
    db.session.commit()
    return redirect(url_for("commissioning.checksheet_detail", sheet_id=sheet.id))


@commissioning_bp.get("/checksheets/<int:sheet_id>")
@login_required
def checksheet_detail(sheet_id):
    sheet = _sheet(sheet_id)
    items = CheckSheetItem.query.filter_by(
        company_name=sheet.company_name, check_sheet_id=sheet.id
    ).order_by(CheckSheetItem.sequence).all()
    attachments = CommissioningAttachment.query.filter_by(
        company_name=sheet.company_name, entity_type="CheckSheet", entity_id=sheet.id
    ).order_by(CommissioningAttachment.uploaded_at.desc()).all()
    return render_template("commissioning/checksheet_detail.html", sheet=sheet, items=items,
                           attachments=attachments,
                           results=list(ItemResultStatus),
                           can_fill=has_permission(sheet.project_id, "checksheets.fill") or has_permission(sheet.project_id, "checksheets.manage"),
                           can_verify=has_permission(sheet.project_id, "checksheets.verify") or has_permission(sheet.project_id, "checksheets.manage"),
                           can_upload_attachments=(sheet.status != CheckSheetStatus.SIGNED_OFF and any(
                               has_permission(sheet.project_id, p)
                               for p in ("checksheets.manage", "checksheets.create", "checksheets.fill", "checksheets.verify"))))


@commissioning_bp.post("/checksheets/<int:sheet_id>/items")
@login_required
def add_checksheet_item(sheet_id):
    sheet = _sheet(sheet_id)
    if not (has_permission(sheet.project_id, "checksheets.create") or has_permission(sheet.project_id, "checksheets.manage")):
        abort(403)
    if sheet.status not in (CheckSheetStatus.DRAFT, CheckSheetStatus.REJECTED):
        abort(409, description="Items can only be added to a draft or rejected sheet")
    sequence = (db.session.query(db.func.max(CheckSheetItem.sequence))
                .filter_by(company_name=sheet.company_name, check_sheet_id=sheet.id).scalar() or 0) + 1
    item = CheckSheetItem(
        company_name=sheet.company_name, check_sheet_id=sheet.id, sequence=sequence,
        description=_required("description"), expected_result=(request.form.get("expected_result") or "").strip() or None,
        witness_required=request.form.get("witness_required") == "1",
    )
    db.session.add(item)
    add_audit_event(sheet.company_name, "CheckSheet", sheet.id, "CHECKSHEET_ITEM_ADDED",
                    after={"sequence": sequence, "description": item.description})
    db.session.commit()
    return redirect(url_for("commissioning.checksheet_detail", sheet_id=sheet.id))


@commissioning_bp.post("/checksheets/<int:sheet_id>/items/<int:item_id>/result")
@login_required
def update_checksheet_item(sheet_id, item_id):
    sheet = _sheet(sheet_id)
    if not (has_permission(sheet.project_id, "checksheets.fill") or has_permission(sheet.project_id, "checksheets.manage")):
        abort(403)
    if sheet.status not in (CheckSheetStatus.ISSUED, CheckSheetStatus.IN_PROGRESS, CheckSheetStatus.REJECTED):
        abort(409, description="Only issued or rejected sheets may be completed")
    item = CheckSheetItem.query.filter_by(
        id=item_id, company_name=sheet.company_name, check_sheet_id=sheet.id
    ).first_or_404()
    old = item.result_status.value
    item.actual_result = (request.form.get("actual_result") or "").strip() or None
    item.result_status = _enum(ItemResultStatus, _required("result_status", 20), "result")
    if item.result_status in (ItemResultStatus.OK, ItemResultStatus.NOK) and not item.actual_result:
        abort(400, description="Actual result is required for OK/NOK items")
    # Any rework invalidates a previous QC verification.
    item.verified_by_id, item.verified_at = None, None
    item.remarks = (request.form.get("remarks") or "").strip() or None
    item.operator_id = current_user.id
    sheet.status = CheckSheetStatus.IN_PROGRESS
    add_audit_event(sheet.company_name, "CheckSheetItem", item.id, "CHECKSHEET_ITEM_RESULT",
                    before={"result": old}, after={"result": item.result_status.value})
    db.session.commit()
    return redirect(url_for("commissioning.checksheet_detail", sheet_id=sheet.id))


@commissioning_bp.post("/checksheets/<int:sheet_id>/items/<int:item_id>/verify")
@login_required
def verify_checksheet_item(sheet_id, item_id):
    sheet = _sheet(sheet_id)
    if not (has_permission(sheet.project_id, "checksheets.verify") or has_permission(sheet.project_id, "checksheets.manage")):
        abort(403)
    if sheet.status not in (CheckSheetStatus.ISSUED, CheckSheetStatus.IN_PROGRESS):
        abort(409, description="Only an issued sheet can be verified")
    item = CheckSheetItem.query.filter_by(
        id=item_id, company_name=sheet.company_name, check_sheet_id=sheet.id
    ).first_or_404()
    if item.result_status not in (ItemResultStatus.OK, ItemResultStatus.NA):
        abort(409, description="Only OK or N/A items can be verified")
    if item.operator_id == current_user.id:
        abort(409, description="Independent verification must be performed by another user")
    item.verified_by_id, item.verified_at = current_user.id, datetime.utcnow()
    add_audit_event(sheet.company_name, "CheckSheetItem", item.id, "CHECKSHEET_ITEM_VERIFIED",
                    after={"verified_by_id": current_user.id})
    db.session.commit()
    return redirect(url_for("commissioning.checksheet_detail", sheet_id=sheet.id))


@commissioning_bp.post("/checksheets/<int:sheet_id>/issue")
@login_required
def issue_checksheet(sheet_id):
    sheet = _sheet(sheet_id)
    if not (has_permission(sheet.project_id, "checksheets.manage") or has_permission(sheet.project_id, "checksheets.create")):
        abort(403)
    if sheet.status not in (CheckSheetStatus.DRAFT, CheckSheetStatus.REJECTED):
        abort(409)
    if not CheckSheetItem.query.filter_by(company_name=sheet.company_name, check_sheet_id=sheet.id).count():
        abort(409, description="A check sheet needs at least one item before issue")
    sheet.status, sheet.issued_by_id, sheet.issued_at = CheckSheetStatus.ISSUED, current_user.id, datetime.utcnow()
    add_audit_event(sheet.company_name, "CheckSheet", sheet.id, "CHECKSHEET_ISSUED")
    db.session.commit()
    return redirect(url_for("commissioning.checksheet_detail", sheet_id=sheet.id))


@commissioning_bp.post("/checksheets/<int:sheet_id>/sign")
@login_required
def sign_checksheet(sheet_id):
    sheet = _sheet(sheet_id)
    role = has_permission(sheet.project_id, "checksheets.sign")
    manager = has_permission(sheet.project_id, "checksheets.manage")
    if not (role or manager):
        abort(403)
    if sheet.status not in (CheckSheetStatus.ISSUED, CheckSheetStatus.IN_PROGRESS):
        abort(409, description="Only an issued check sheet can be signed")
    items = CheckSheetItem.query.filter_by(company_name=sheet.company_name, check_sheet_id=sheet.id).all()
    if not items or any(i.result_status in (ItemResultStatus.PENDING, ItemResultStatus.NOK) for i in items):
        abort(409, description="All check sheet items must be completed without NOK results")
    if any(i.witness_required for i in items):
        for required_item in (item for item in items if item.witness_required):
            points = WitnessPoint.query.filter_by(
                company_name=sheet.company_name, check_sheet_id=sheet.id,
                check_sheet_item_id=required_item.id,
            ).all()
            if not points or any(point.status != WitnessStatus.RELEASED for point in points):
                abort(409, description="Every required witness point must be released before sign-off")
    if has_permission(sheet.project_id, "checksheets.sign"):
        if sheet.signed_by_client_id and sheet.signed_by_client_id != current_user.id:
            abort(409, description="Client signature already recorded")
        sheet.signed_by_client_id = current_user.id
        sig_type = "CLIENT"
    else:
        if sheet.signed_by_contractor_id and sheet.signed_by_contractor_id != current_user.id:
            abort(409, description="Contractor signature already recorded")
        if sheet.signed_by_client_id == current_user.id:
            abort(409, description="Two-party sign-off requires different users")
        sheet.signed_by_contractor_id = current_user.id
        sig_type = "CONTRACTOR"
    db.session.add(CommissioningSignature(
        company_name=sheet.company_name, entity_type="CheckSheet", entity_id=sheet.id,
        signature_type=sig_type, signer_id=current_user.id,
        verification_method="authenticated_session",
        verification_reference=f"user:{current_user.id}",
        ip_address=request.remote_addr, user_agent=request.user_agent.string[:500],
    ))
    if sheet.signed_by_client_id and sheet.signed_by_contractor_id:
        sheet.status, sheet.signed_at = CheckSheetStatus.SIGNED_OFF, datetime.utcnow()
    add_audit_event(sheet.company_name, "CheckSheet", sheet.id, "CHECKSHEET_SIGNED",
                    after={"signature_type": sig_type, "signed_off": sheet.status == CheckSheetStatus.SIGNED_OFF})
    db.session.commit()
    return redirect(url_for("commissioning.checksheet_detail", sheet_id=sheet.id))


@commissioning_bp.post("/checksheets/<int:sheet_id>/reject")
@login_required
def reject_checksheet(sheet_id):
    sheet = _sheet(sheet_id)
    if not has_permission(sheet.project_id, "checksheets.sign"):
        abort(403)
    if sheet.status not in (CheckSheetStatus.ISSUED, CheckSheetStatus.IN_PROGRESS):
        abort(409, description="Only an issued check sheet can be rejected")
    reason = _required("reason", 2000)
    old = sheet.status
    sheet.status = CheckSheetStatus.REJECTED
    sheet.rejection_reason = reason
    add_audit_event(sheet.company_name, "CheckSheet", sheet.id, "CHECKSHEET_REJECTED",
                    before={"status": old.value}, after={"reason": reason})
    db.session.commit()
    return redirect(url_for("commissioning.checksheet_detail", sheet_id=sheet.id))


@commissioning_bp.post("/checksheets/<int:sheet_id>/revise")
@login_required
def revise_checksheet(sheet_id):
    previous = _sheet(sheet_id)
    if not (has_permission(previous.project_id, "checksheets.manage") or has_permission(previous.project_id, "checksheets.create")):
        abort(403)
    if previous.status != CheckSheetStatus.SIGNED_OFF:
        abort(409, description="Only a signed-off sheet can be revised")
    revision_no = previous.revision + 1
    new_sheet = CheckSheet(
        company_name=previous.company_name, project_id=previous.project_id,
        system_id=previous.system_id, subsystem_id=previous.subsystem_id,
        equipment_id=previous.equipment_id, sheet_number=previous.sheet_number,
        sheet_type=previous.sheet_type, revision=revision_no, supersedes_id=previous.id,
        sheet_weight=previous.sheet_weight, title=previous.title,
        status=CheckSheetStatus.DRAFT, created_by_id=current_user.id,
    )
    db.session.add(new_sheet)
    db.session.flush()
    for old in CheckSheetItem.query.filter_by(company_name=previous.company_name, check_sheet_id=previous.id).order_by(CheckSheetItem.sequence).all():
        db.session.add(CheckSheetItem(
            company_name=previous.company_name, check_sheet_id=new_sheet.id,
            sequence=old.sequence, description=old.description,
            expected_result=old.expected_result, witness_required=old.witness_required,
        ))
    db.session.add(CheckSheetRevision(
        company_name=previous.company_name, sheet_number=previous.sheet_number,
        revision_number=revision_no, previous_check_sheet_id=previous.id,
        new_check_sheet_id=new_sheet.id, revision_reason=_required("reason", 2000),
        created_by_id=current_user.id,
    ))
    add_audit_event(previous.company_name, "CheckSheet", new_sheet.id, "CHECKSHEET_REVISION_CREATED",
                    before={"previous_id": previous.id}, after={"revision": revision_no})
    db.session.commit()
    return redirect(url_for("commissioning.checksheet_detail", sheet_id=new_sheet.id))


@commissioning_bp.post("/projects/<int:project_id>/punch")
@login_required
def create_punch(project_id):
    _need(project_id, "punch.raise", "punch.assign")
    project = get_project(project_id)
    subsystem = CommissioningSubsystem.query.join(CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id).filter(
        CommissioningSubsystem.id == int(_required("subsystem_id", 20)),
        CommissioningSubsystem.company_name == project.company_name,
        CommissioningSystem.project_id == project.id,
    ).first_or_404()
    category = _enum(PunchCategory, _required("category", 1), "category")
    punch = PunchItem(
        company_name=project.company_name, project_id=project.id, subsystem_id=subsystem.id,
        punch_number=next_punch_number(project.company_name, project.project_code, category),
        category=category, severity=_enum(PunchSeverity, request.form.get("severity") or "MEDIUM", "severity"),
        description=_required("description"), raised_by_id=current_user.id,
        target_closure_date=_date("target_closure_date"),
    )
    db.session.add(punch)
    db.session.flush()
    db.session.add(PunchHistory(company_name=project.company_name, punch_item_id=punch.id,
        old_status=None, new_status=PunchStatus.OPEN, changed_by_id=current_user.id,
        remarks="Punch item raised"))
    add_audit_event(project.company_name, "PunchItem", punch.id, "PUNCH_RAISED",
                    after={"punch_number": punch.punch_number, "category": category.value})
    db.session.commit()
    return redirect(url_for("commissioning.operations", project_id=project.id))


@commissioning_bp.post("/punch/<int:punch_id>/assign")
@login_required
def assign_punch(punch_id):
    punch = _punch(punch_id)
    if not has_permission(punch.project_id, "punch.assign"):
        abort(403)
    assignee_value = (request.form.get("assigned_to_id") or "").strip()
    assignee = None
    if assignee_value:
        try:
            assignee_id = int(assignee_value)
        except ValueError:
            abort(400, description="Invalid assignee")
        active_member = CommissioningMembership.query.filter_by(
            company_name=punch.company_name, project_id=punch.project_id,
            user_id=assignee_id, is_active=True,
        ).first()
        if not active_member:
            abort(400, description="Assignee must be an active project member")
        assignee = User.query.filter_by(id=assignee_id, company_name=punch.company_name).first_or_404()
    old_assignee = punch.assigned_to_id
    punch.assigned_to_id = assignee.id if assignee else None
    punch.target_closure_date = _date("target_closure_date") or punch.target_closure_date
    add_audit_event(punch.company_name, "PunchItem", punch.id, "PUNCH_ASSIGNED",
                    before={"assigned_to_id": old_assignee},
                    after={"assigned_to_id": punch.assigned_to_id})
    db.session.commit()
    return redirect(url_for("commissioning.operations", project_id=punch.project_id))


@commissioning_bp.post("/punch/<int:punch_id>/transition")
@login_required
def transition_punch(punch_id):
    punch = _punch(punch_id)
    target = _enum(PunchStatus, _required("status", 30), "status")
    old = punch.status
    allowed = {
        PunchStatus.OPEN: {PunchStatus.IN_PROGRESS, PunchStatus.WAIVED},
        PunchStatus.IN_PROGRESS: {PunchStatus.CLOSED, PunchStatus.WAIVED},
        PunchStatus.CLOSED: {PunchStatus.VERIFIED, PunchStatus.IN_PROGRESS},
    }
    if target not in allowed.get(old, set()):
        abort(409, description=f"Transition {old.value} to {target.value} is not allowed")
    if target in (PunchStatus.IN_PROGRESS, PunchStatus.CLOSED) and not (has_permission(punch.project_id, "punch.assign") or has_permission(punch.project_id, "punch.raise")):
        abort(403)
    if target in (PunchStatus.VERIFIED, PunchStatus.WAIVED) and not has_permission(punch.project_id, "punch.verify"):
        abort(403)
    if target == PunchStatus.WAIVED:
        punch.waiver_reason = _required("reason", 2000)
        punch.waived_by_id, punch.waived_at = current_user.id, datetime.utcnow()
    if target == PunchStatus.CLOSED:
        punch.closed_by_id, punch.closed_at = current_user.id, datetime.utcnow()
    if target == PunchStatus.VERIFIED:
        punch.verified_by_id, punch.verified_at = current_user.id, datetime.utcnow()
    punch.status = target
    db.session.add(PunchHistory(company_name=punch.company_name, punch_item_id=punch.id,
        old_status=old, new_status=target, changed_by_id=current_user.id,
        remarks=(request.form.get("remarks") or "").strip() or None))
    add_audit_event(punch.company_name, "PunchItem", punch.id, "PUNCH_STATUS_CHANGED",
                    before={"status": old.value}, after={"status": target.value})
    db.session.commit()
    return redirect(url_for("commissioning.operations", project_id=punch.project_id))


@commissioning_bp.post("/projects/<int:project_id>/witness")
@login_required
def create_witness(project_id):
    _need(project_id, "witness.manage", "project.manage")
    project = get_project(project_id)
    sheet = CheckSheet.query.filter_by(
        id=int(_required("check_sheet_id", 20)), project_id=project.id,
        company_name=project.company_name,
    ).first_or_404()
    item_id = request.form.get("check_sheet_item_id") or None
    if item_id:
        CheckSheetItem.query.filter_by(id=int(item_id), check_sheet_id=sheet.id,
                                      company_name=project.company_name).first_or_404()
        item_id = int(item_id)
    scheduled_text = _required("scheduled_at", 40)
    try:
        scheduled = datetime.fromisoformat(scheduled_text)
    except ValueError:
        abort(400, description="Invalid scheduled date/time")
    witness = WitnessPoint(
        company_name=project.company_name, project_id=project.id, check_sheet_id=sheet.id,
        check_sheet_item_id=item_id,
        type=_enum(WitnessType, _required("type", 20), "witness type"),
        notified_party=(request.form.get("notified_party") or "").strip() or None,
        scheduled_at=scheduled, status=WitnessStatus.PLANNED,
    )
    db.session.add(witness)
    db.session.flush()
    add_audit_event(project.company_name, "WitnessPoint", witness.id, "WITNESS_SCHEDULED",
                    after={"check_sheet_id": sheet.id, "scheduled_at": scheduled.isoformat()})
    db.session.commit()
    return redirect(url_for("commissioning.operations", project_id=project.id))


@commissioning_bp.post("/witness/<int:witness_id>/transition")
@login_required
def transition_witness(witness_id):
    witness = WitnessPoint.query.filter_by(id=witness_id, company_name=current_user.company_name).first_or_404()
    _need(witness.project_id, "witness.attend", "witness.manage", "project.manage")
    target = _enum(WitnessStatus, _required("status", 20), "witness status")
    if target == WitnessStatus.ATTENDED:
        if not has_permission(witness.project_id, "witness.attend"):
            abort(403)
        if witness.status not in (WitnessStatus.PLANNED, WitnessStatus.NOTIFIED):
            abort(409)
        witness.attended_by_id, witness.attended_at = current_user.id, datetime.utcnow()
        witness.result = _required("result", 30)
    elif target == WitnessStatus.RELEASED:
        if not has_permission(witness.project_id, "witness.manage"):
            abort(403)
        if witness.status != WitnessStatus.ATTENDED:
            abort(409, description="Witness point must be attended before release")
        witness.released_by_id, witness.released_at = current_user.id, datetime.utcnow()
    elif target == WitnessStatus.NOTIFIED:
        if not has_permission(witness.project_id, "witness.manage") or witness.status != WitnessStatus.PLANNED:
            abort(403)
    else:
        abort(400, description="Unsupported witness transition")
    old = witness.status
    witness.status = target
    witness.remarks = (request.form.get("remarks") or "").strip() or witness.remarks
    add_audit_event(witness.company_name, "WitnessPoint", witness.id, "WITNESS_STATUS_CHANGED",
                    before={"status": old.value}, after={"status": target.value})
    db.session.commit()
    return redirect(url_for("commissioning.operations", project_id=witness.project_id))


@commissioning_bp.post("/projects/<int:project_id>/handover")
@login_required
def create_handover(project_id):
    _need(project_id, "handover.manage", "project.manage")
    project = get_project(project_id)
    subsystem = CommissioningSubsystem.query.join(CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id).filter(
        CommissioningSubsystem.id == int(_required("subsystem_id", 20)),
        CommissioningSubsystem.company_name == project.company_name,
        CommissioningSystem.project_id == project.id,
    ).first_or_404()
    package_no = _required("package_number", 100)
    package = HandoverPackage(
        company_name=project.company_name, project_id=project.id,
        subsystem_id=subsystem.id, package_number=package_no,
        status=HandoverStatus.DRAFT,
    )
    db.session.add(package)
    db.session.flush()
    add_audit_event(project.company_name, "HandoverPackage", package.id, "HANDOVER_PACKAGE_CREATED",
                    after={"package_number": package_no, "subsystem_id": subsystem.id})
    db.session.commit()
    return redirect(url_for("commissioning.operations", project_id=project.id))


@commissioning_bp.post("/handover/<int:package_id>/transition")
@login_required
def transition_handover(package_id):
    package = HandoverPackage.query.filter_by(id=package_id, company_name=current_user.company_name).first_or_404()
    _need(package.project_id, "handover.manage", "handover.accept", "project.manage")
    target = _enum(HandoverStatus, _required("status", 30), "handover status")
    old = package.status
    subsystem_id = package.subsystem_id
    if target == HandoverStatus.MC_CERTIFIED:
        if not has_permission(package.project_id, "handover.manage") or old != HandoverStatus.DRAFT:
            abort(403)
        sheets = CheckSheet.query.filter_by(company_name=package.company_name,
            project_id=package.project_id, subsystem_id=subsystem_id).all()
        if not sheets or any(s.status != CheckSheetStatus.SIGNED_OFF for s in sheets):
            abort(409, description="All subsystem check sheets must be signed off before MC certification")
        open_critical = PunchItem.query.filter_by(company_name=package.company_name,
            project_id=package.project_id, subsystem_id=subsystem_id).filter(
            PunchItem.category.in_([PunchCategory.A, PunchCategory.B]),
            PunchItem.status.notin_([PunchStatus.VERIFIED, PunchStatus.WAIVED])).count()
        if open_critical:
            abort(409, description="Category A/B punch items must be cleared before MC certification")
        package.status, package.mc_issued_by_id = target, current_user.id
        package.mc_certificate_number = _required("certificate_number", 100)
        package.mc_certificate_date = _date("certificate_date") or date.today()
    elif target == HandoverStatus.RF_CERTIFIED:
        if not has_permission(package.project_id, "handover.manage") or old != HandoverStatus.MC_CERTIFIED:
            abort(403)
        package.status, package.rf_issued_by_id = target, current_user.id
        package.rf_certificate_number = _required("certificate_number", 100)
        package.rf_certificate_date = _date("certificate_date") or date.today()
    elif target == HandoverStatus.RFSU:
        if not has_permission(package.project_id, "handover.manage") or old != HandoverStatus.RF_CERTIFIED:
            abort(403)
        package.status = target
    elif target == HandoverStatus.ACCEPTED:
        if not has_permission(package.project_id, "handover.accept") or old != HandoverStatus.RFSU:
            abort(403)
        package.status, package.accepted_by_operations = target, True
        package.operations_accepted_by_id, package.operations_accepted_at = current_user.id, datetime.utcnow()
    elif target == HandoverStatus.REJECTED:
        if not has_permission(package.project_id, "handover.accept") or old not in (
            HandoverStatus.MC_CERTIFIED, HandoverStatus.RF_CERTIFIED, HandoverStatus.RFSU):
            abort(403)
        package.status, package.rejection_reason = target, _required("reason", 2000)
    else:
        abort(400, description="Unsupported handover transition")
    add_audit_event(package.company_name, "HandoverPackage", package.id, "HANDOVER_STATUS_CHANGED",
                    before={"status": old.value}, after={"status": target.value})
    db.session.commit()
    return redirect(url_for("commissioning.operations", project_id=package.project_id))



_ATTACHMENT_PERMISSIONS = {
    "CheckSheet": {
        "upload": ("checksheets.manage", "checksheets.create", "checksheets.fill", "checksheets.verify"),
        "view": ("checksheets.view", "checksheets.manage", "checksheets.create",
                 "checksheets.fill", "checksheets.verify", "checksheets.sign"),
    },
    "PunchItem": {
        "upload": ("punch.raise", "punch.assign", "punch.verify"),
        "view": ("punch.view", "punch.raise", "punch.assign", "punch.verify", "project.manage"),
    },
    "HandoverPackage": {
        "upload": ("handover.manage", "handover.accept"),
        "view": ("handover.view", "handover.manage", "handover.accept", "project.manage"),
    },
    "CommissioningDocument": {
        "upload": ("documents.create", "documents.manage"),
        "view": ("documents.view", "documents.create", "documents.manage", "documents.review", "documents.approve"),
    },
}


def _attachment_entity(entity_type, entity_id):
    if entity_type == "CheckSheet":
        entity = CheckSheet.query.filter_by(
            id=entity_id, company_name=current_user.company_name
        ).first_or_404()
        return entity, entity.project_id
    if entity_type == "PunchItem":
        entity = PunchItem.query.filter_by(
            id=entity_id, company_name=current_user.company_name
        ).first_or_404()
        return entity, entity.project_id
    if entity_type == "HandoverPackage":
        entity = HandoverPackage.query.filter_by(
            id=entity_id, company_name=current_user.company_name
        ).first_or_404()
        return entity, entity.project_id
    if entity_type == "CommissioningDocument":
        entity = CommissioningDocument.query.filter_by(
            id=entity_id, company_name=current_user.company_name
        ).first_or_404()
        return entity, entity.project_id
    abort(404)


@commissioning_bp.post("/evidence/<entity_type>/<int:entity_id>")
@login_required
def upload_evidence(entity_type, entity_id):
    permissions = _ATTACHMENT_PERMISSIONS.get(entity_type)
    if permissions is None:
        abort(404)
    entity, project_id = _attachment_entity(entity_type, entity_id)
    if not any(has_permission(project_id, permission) for permission in permissions["upload"]):
        abort(403)
    if entity_type == "CheckSheet" and entity.status == CheckSheetStatus.SIGNED_OFF:
        abort(409, description="Signed-off check sheets are immutable; create a new revision to add evidence")
    if entity_type == "PunchItem" and entity.status in (PunchStatus.VERIFIED, PunchStatus.WAIVED):
        abort(409, description="Verified or waived Punch items are immutable")
    if entity_type == "HandoverPackage" and entity.status == HandoverStatus.ACCEPTED:
        abort(409, description="Accepted handover packages are immutable")
    if entity_type == "CommissioningDocument" and entity.status not in (DocumentStatus.DRAFT, DocumentStatus.REJECTED):
        abort(409, description="Evidence can only be added to draft or rejected document revisions")
    metadata = store_commissioning_upload(
        request.files.get("file"), company_name=current_user.company_name,
        entity_type=entity_type, entity_id=entity_id, uploaded_by_id=current_user.id,
    )
    attachment = CommissioningAttachment(
        company_name=current_user.company_name, entity_type=entity_type,
        entity_id=entity_id, **metadata,
    )
    db.session.add(attachment)
    try:
        db.session.flush()
        add_audit_event(current_user.company_name, "CommissioningAttachment", attachment.id,
                        "EVIDENCE_UPLOADED",
                        after={"entity_type": entity_type, "entity_id": entity_id,
                               "filename": attachment.filename, "sha256": attachment.checksum})
        db.session.commit()
    except Exception:
        db.session.rollback()
        stored_path = resolve_commissioning_upload(metadata["storage_key"])
        stored_path.unlink(missing_ok=True)
        raise
    flash("Evidence uploaded successfully.", "success")
    if entity_type == "CheckSheet":
        return redirect(url_for("commissioning.checksheet_detail", sheet_id=entity_id))
    if entity_type == "CommissioningDocument":
        return redirect(url_for("commissioning.document_register", project_id=project_id))
    return redirect(url_for("commissioning.operations", project_id=project_id))


@commissioning_bp.get("/evidence/<int:attachment_id>")
@login_required
def download_evidence(attachment_id):
    attachment = CommissioningAttachment.query.filter_by(
        id=attachment_id, company_name=current_user.company_name
    ).first_or_404()
    permissions = _ATTACHMENT_PERMISSIONS.get(attachment.entity_type)
    if permissions is None:
        abort(404)
    _, project_id = _attachment_entity(attachment.entity_type, attachment.entity_id)
    if not any(has_permission(project_id, permission) for permission in permissions["view"]):
        abort(403)
    path = resolve_commissioning_upload(attachment.storage_key)
    response = send_file(path, mimetype=attachment.mime_type, as_attachment=True,
                         download_name=attachment.filename, max_age=0)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@commissioning_bp.post("/projects/<int:project_id>/reports/snapshot")
@login_required
def create_progress_snapshot(project_id):
    """Save project, system or subsystem progress using check-sheet and task weights."""
    _need(project_id, "project.manage")
    project = get_project(project_id)
    snapshot_date = _date("snapshot_date") or date.today()
    scope = (request.form.get("scope") or "project").strip()
    system_id = None
    subsystem_id = None
    subsystem_ids = None

    if scope.startswith("system:"):
        try:
            system_id = int(scope.split(":", 1)[1])
        except ValueError:
            abort(400, description="Invalid system scope.")
        system = CommissioningSystem.query.filter_by(
            id=system_id, company_name=project.company_name, project_id=project.id,
        ).first_or_404()
        subsystem_ids = [
            item.id for item in CommissioningSubsystem.query.filter_by(
                company_name=project.company_name, system_id=system.id,
            ).all()
        ]
    elif scope.startswith("subsystem:"):
        try:
            subsystem_id = int(scope.split(":", 1)[1])
        except ValueError:
            abort(400, description="Invalid subsystem scope.")
        subsystem = CommissioningSubsystem.query.join(
            CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id,
        ).filter(
            CommissioningSubsystem.id == subsystem_id,
            CommissioningSubsystem.company_name == project.company_name,
            CommissioningSystem.project_id == project.id,
        ).first_or_404()
        system_id = subsystem.system_id
        subsystem_ids = [subsystem.id]
    elif scope != "project":
        abort(400, description="Unsupported progress scope.")

    sheets_query = CheckSheet.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    )
    punches_query = PunchItem.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    )
    tasks_query = CommissioningTask.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    )
    if subsystem_id is not None:
        sheets_query = sheets_query.filter_by(subsystem_id=subsystem_id)
        punches_query = punches_query.filter_by(subsystem_id=subsystem_id)
        tasks_query = tasks_query.filter_by(subsystem_id=subsystem_id)
    elif system_id is not None:
        sheets_query = sheets_query.filter_by(system_id=system_id)
        punches_query = punches_query.filter(PunchItem.subsystem_id.in_(subsystem_ids or [-1]))
        tasks_query = tasks_query.filter_by(system_id=system_id)

    all_sheets = sheets_query.all()
    superseded_sheet_ids = {sheet.supersedes_id for sheet in all_sheets if sheet.supersedes_id is not None}
    sheets = [sheet for sheet in all_sheets if sheet.id not in superseded_sheet_ids]
    punches = punches_query.all()
    tasks = tasks_query.filter(
        CommissioningTask.status != CommissioningTaskStatus.CANCELLED,
    ).all()
    signed = sum(1 for sheet in sheets if sheet.status == CheckSheetStatus.SIGNED_OFF)
    completed_punches = sum(
        1 for punch in punches if punch.status in (PunchStatus.VERIFIED, PunchStatus.WAIVED)
    )
    total_sheets = len(sheets)
    percent = round((signed / total_sheets) * 100, 2) if total_sheets else 0.0
    total_sheet_weight = sum(sheet.sheet_weight for sheet in sheets)
    weighted = round(
        sum(sheet.sheet_weight for sheet in sheets if sheet.status == CheckSheetStatus.SIGNED_OFF)
        / total_sheet_weight * 100, 2
    ) if total_sheet_weight else 0.0

    total_tasks = len(tasks)
    completed_tasks = sum(1 for task in tasks if task.status == CommissioningTaskStatus.COMPLETED)
    task_percent = round(completed_tasks / total_tasks * 100, 2) if total_tasks else 0.0
    estimated_hours = sum(task.estimated_man_hours for task in tasks)
    completed_hours = sum(
        task.estimated_man_hours for task in tasks
        if task.status == CommissioningTaskStatus.COMPLETED
    )
    task_weighted = round(completed_hours / estimated_hours * 100, 2) if estimated_hours > 0 else task_percent

    snapshot = ProgressSnapshot.query.filter_by(
        company_name=project.company_name, project_id=project.id,
        system_id=system_id, subsystem_id=subsystem_id, snapshot_date=snapshot_date,
    ).first()
    if snapshot is None:
        snapshot = ProgressSnapshot(
            company_name=project.company_name, project_id=project.id,
            system_id=system_id, subsystem_id=subsystem_id, snapshot_date=snapshot_date,
        )
        db.session.add(snapshot)
    snapshot.percent_complete, snapshot.weighted_percent = percent, weighted
    snapshot.checksheet_total, snapshot.checksheet_signed_off = total_sheets, signed
    snapshot.punch_open_count = len(punches) - completed_punches
    snapshot.punch_closed_count = completed_punches
    snapshot.task_total, snapshot.task_completed = total_tasks, completed_tasks
    snapshot.task_percent_complete, snapshot.task_weighted_percent = task_percent, task_weighted
    snapshot.task_estimated_hours, snapshot.task_completed_hours = estimated_hours, completed_hours
    db.session.flush()
    add_audit_event(
        project.company_name, "ProgressSnapshot", snapshot.id or 0,
        "PROGRESS_SNAPSHOT_CREATED",
        after={
            "scope": scope, "percent_complete": percent, "weighted_percent": weighted,
            "task_percent_complete": task_percent, "task_weighted_percent": task_weighted,
            "task_total": total_tasks, "task_completed": completed_tasks,
        },
    )
    db.session.commit()
    flash("Scoped progress snapshot saved successfully.", "success")
    return redirect(url_for("commissioning.operations", project_id=project.id))


@commissioning_bp.post("/projects/<int:project_id>/tasks/<int:task_id>/transition")
@login_required
def transition_task(project_id, task_id):
    """Apply a controlled task lifecycle transition with an append-only audit event."""
    _need(project_id, "tasks.manage", "project.manage")
    project = get_project(project_id)
    task = CommissioningTask.query.filter_by(
        id=task_id, company_name=project.company_name, project_id=project.id
    ).first_or_404()
    target = _enum(CommissioningTaskStatus, _required("status", 30), "status")
    reason = (request.form.get("reason") or "").strip()[:2000]
    current = task.status
    transitions = {
        CommissioningTaskStatus.NOT_STARTED: {CommissioningTaskStatus.READY, CommissioningTaskStatus.CANCELLED},
        CommissioningTaskStatus.READY: {CommissioningTaskStatus.IN_PROGRESS, CommissioningTaskStatus.BLOCKED, CommissioningTaskStatus.CANCELLED},
        CommissioningTaskStatus.IN_PROGRESS: {CommissioningTaskStatus.BLOCKED, CommissioningTaskStatus.COMPLETED, CommissioningTaskStatus.CANCELLED},
        CommissioningTaskStatus.BLOCKED: {CommissioningTaskStatus.IN_PROGRESS, CommissioningTaskStatus.CANCELLED},
        CommissioningTaskStatus.COMPLETED: {CommissioningTaskStatus.IN_PROGRESS},
        CommissioningTaskStatus.CANCELLED: set(),
    }
    if target not in transitions.get(current, set()):
        abort(409, description=f"Transition from {current.value} to {target.value} is not allowed.")
    if target in (CommissioningTaskStatus.BLOCKED, CommissioningTaskStatus.CANCELLED) and not reason:
        abort(400, description="A reason is required when blocking or cancelling a task.")
    if current in (CommissioningTaskStatus.COMPLETED, CommissioningTaskStatus.CANCELLED) and not reason:
        abort(400, description="A reason is required to reopen a completed task.")
    if target in (CommissioningTaskStatus.READY, CommissioningTaskStatus.IN_PROGRESS):
        predecessor_ids = [
            row.predecessor_task_id for row in CommissioningTaskDependency.query.filter_by(
                company_name=project.company_name, project_id=project.id,
                successor_task_id=task.id,
            ).all()
        ]
        if predecessor_ids:
            incomplete_predecessors = CommissioningTask.query.filter(
                CommissioningTask.company_name == project.company_name,
                CommissioningTask.project_id == project.id,
                CommissioningTask.id.in_(predecessor_ids),
                CommissioningTask.status != CommissioningTaskStatus.COMPLETED,
            ).count()
            if incomplete_predecessors:
                abort(409, description="All finish-to-start predecessor tasks must be completed first.")
    before = {"status": current.value, "actual_start_date": task.actual_start_date.isoformat() if task.actual_start_date else None,
              "actual_finish_date": task.actual_finish_date.isoformat() if task.actual_finish_date else None}
    now = datetime.utcnow()
    task.status = target
    if target == CommissioningTaskStatus.IN_PROGRESS and task.actual_start_date is None:
        task.actual_start_date = now.date()
    if target == CommissioningTaskStatus.COMPLETED:
        task.actual_finish_date = now.date()
    if target == CommissioningTaskStatus.IN_PROGRESS and current == CommissioningTaskStatus.COMPLETED:
        task.actual_finish_date = None
    after = {"status": target.value, "reason": reason or None,
             "actual_start_date": task.actual_start_date.isoformat() if task.actual_start_date else None,
             "actual_finish_date": task.actual_finish_date.isoformat() if task.actual_finish_date else None}
    add_audit_event(project.company_name, "CommissioningTask", task.id, "TASK_STATUS_CHANGED",
                    before=before, after=after)
    db.session.commit()
    flash(f"Task {task.task_number} status updated to {target.value.replace('_', ' ').title()}.", "success")
    return redirect(url_for("commissioning.task_register", project_id=project.id))


@commissioning_bp.route("/projects/<int:project_id>/tasks", methods=["GET", "POST"])
@login_required
def task_register(project_id):
    """Manage the project task branch and its equipment/progress associations."""
    _need(project_id, "tasks.view", "tasks.create", "tasks.manage", "project.manage")
    project = get_project(project_id)
    if request.method == "POST":
        if not (has_permission(project.id, "tasks.create") or has_permission(project.id, "tasks.manage") or has_permission(project.id, "project.manage")):
            abort(403)
        task_number = _required("task_number", 100)
        if CommissioningTask.query.filter_by(company_name=project.company_name, task_number=task_number).first():
            abort(409, description="Task number is already in use in this company.")
        system = CommissioningSystem.query.filter_by(
            id=request.form.get("system_id", type=int), company_name=project.company_name,
            project_id=project.id,
        ).first_or_404()
        subsystem = CommissioningSubsystem.query.filter_by(
            id=request.form.get("subsystem_id", type=int), company_name=project.company_name,
            system_id=system.id,
        ).first_or_404()
        equipment_id = request.form.get("equipment_id", type=int)
        check_sheet_id = request.form.get("check_sheet_id", type=int)
        if check_sheet_id is not None:
            linked_sheet = CheckSheet.query.filter_by(
                id=check_sheet_id, company_name=project.company_name,
                project_id=project.id, system_id=system.id, subsystem_id=subsystem.id,
            ).first()
            if linked_sheet is None:
                abort(400, description="Check sheet must belong to the selected system and subsystem.")
        if equipment_id is not None:
            equipment = CommissioningEquipment.query.filter_by(
                id=equipment_id, company_name=project.company_name,
                project_id=project.id, subsystem_id=subsystem.id,
            ).first()
            if equipment is None:
                abort(400, description="Equipment must belong to the selected subsystem.")
        activity = _enum(CommissioningTaskType, _required("activity_type", 10), "activity_type")
        try:
            estimated = float(request.form.get("estimated_man_hours") or 0)
            spent = float(request.form.get("spent_man_hours") or 0)
        except (TypeError, ValueError):
            abort(400, description="Man-hours must be numeric.")
        if estimated < 0 or spent < 0:
            abort(400, description="Man-hours cannot be negative.")
        planned_start = _date("planned_start_date")
        planned_finish = _date("planned_finish_date")
        actual_start = _date("actual_start_date")
        actual_finish = _date("actual_finish_date")
        if planned_start and planned_finish and planned_finish < planned_start:
            abort(400, description="Planned finish cannot precede planned start.")
        if actual_start and actual_finish and actual_finish < actual_start:
            abort(400, description="Actual finish cannot precede actual start.")
        task = CommissioningTask(
            company_name=project.company_name, project_id=project.id,
            system_id=system.id, subsystem_id=subsystem.id, equipment_id=equipment_id,
            check_sheet_id=check_sheet_id, task_number=task_number, title=_required("title", 200),
            description=(request.form.get("description") or "").strip()[:5000] or None,
            activity_type=activity, discipline=_required("discipline", 80),
            progress_stage=(request.form.get("progress_stage") or "").strip()[:80] or None,
            progress_substage=(request.form.get("progress_substage") or "").strip()[:80] or None,
            assigned_group=(request.form.get("assigned_group") or "").strip()[:120] or None,
            estimated_man_hours=estimated, spent_man_hours=spent,
            planned_start_date=planned_start, planned_finish_date=planned_finish,
            actual_start_date=actual_start, actual_finish_date=actual_finish,
            status=CommissioningTaskStatus.NOT_STARTED, created_by_id=current_user.id,
        )
        db.session.add(task)
        db.session.flush()
        add_audit_event(project.company_name, "CommissioningTask", task.id, "TASK_CREATED",
                        after={"task_number": task.task_number, "activity_type": task.activity_type.value,
                               "system_id": system.id, "subsystem_id": subsystem.id,
                               "equipment_id": equipment_id})
        db.session.commit()
        flash("Commissioning task added to the project register.", "success")
        return redirect(url_for("commissioning.task_register", project_id=project.id))

    tasks_query = CommissioningTask.query.filter_by(company_name=project.company_name, project_id=project.id)
    activity_filter = (request.args.get("activity_type") or "").strip()
    status_filter = (request.args.get("status") or "").strip()
    search_term = (request.args.get("q") or "").strip()[:100]
    if activity_filter:
        tasks_query = tasks_query.filter(CommissioningTask.activity_type == _enum(CommissioningTaskType, activity_filter, "activity_type"))
    if status_filter:
        tasks_query = tasks_query.filter(CommissioningTask.status == _enum(CommissioningTaskStatus, status_filter, "status"))
    if search_term:
        like = f"%{search_term}%"
        tasks_query = tasks_query.filter(or_(
            CommissioningTask.task_number.ilike(like),
            CommissioningTask.title.ilike(like),
            CommissioningTask.discipline.ilike(like),
            CommissioningTask.assigned_group.ilike(like),
        ))
    tasks = tasks_query.order_by(CommissioningTask.task_number).all()
    systems = CommissioningSystem.query.filter_by(company_name=project.company_name, project_id=project.id).filter(CommissioningSystem.status != "ARCHIVED").order_by(CommissioningSystem.system_code).all()
    subsystems = CommissioningSubsystem.query.join(CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id).filter(
        CommissioningSubsystem.company_name == project.company_name,
        CommissioningSystem.project_id == project.id,
        CommissioningSubsystem.status != "ARCHIVED",
    ).order_by(CommissioningSubsystem.subsystem_code).all()
    equipment = CommissioningEquipment.query.filter_by(company_name=project.company_name, project_id=project.id).order_by(CommissioningEquipment.tag_number).all()
    check_sheets = CheckSheet.query.filter_by(company_name=project.company_name, project_id=project.id).order_by(CheckSheet.sheet_number).all()
    system_by_id = {item.id: item for item in systems}
    subsystem_by_id = {item.id: item for item in subsystems}
    equipment_by_id = {item.id: item for item in equipment}
    sheet_by_id = {item.id: item for item in check_sheets}
    dependency_rows = CommissioningTaskDependency.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).all()
    dependencies_by_task = {}
    for dependency in dependency_rows:
        dependencies_by_task.setdefault(dependency.successor_task_id, []).append(dependency)
    task_by_id = {item.id: item for item in tasks}

    return render_template(
        "commissioning/task_register.html", project=project, tasks=tasks,
        systems=systems, subsystems=subsystems, equipment=equipment, check_sheets=check_sheets,
        system_by_id=system_by_id, subsystem_by_id=subsystem_by_id,
        equipment_by_id=equipment_by_id, sheet_by_id=sheet_by_id,
        dependencies_by_task=dependencies_by_task, task_by_id=task_by_id,
        activity_types=list(CommissioningTaskType), task_statuses=list(CommissioningTaskStatus),
        can_create=any(has_permission(project.id, p) for p in ("tasks.create", "tasks.manage", "project.manage")),
        can_manage_tasks=any(has_permission(project.id, p) for p in ("tasks.manage", "project.manage")),
        selected_activity=activity_filter, selected_status=status_filter, search_term=search_term,
    )



@commissioning_bp.route("/projects/<int:project_id>/documents", methods=["GET", "POST"])
@login_required
def document_register(project_id):
    """Project document register with controlled revisions and approval history."""
    _need(project_id, "documents.view", "documents.create", "documents.manage",
          "documents.review", "documents.approve", "project.manage")
    project = get_project(project_id)
    if request.method == "POST":
        if not (has_permission(project.id, "documents.create")
                or has_permission(project.id, "documents.manage")
                or has_permission(project.id, "project.manage")):
            abort(403)
        number = _required("document_number", 120)
        if CommissioningDocument.query.filter_by(
            company_name=project.company_name, project_id=project.id,
            document_number=number,
        ).first():
            abort(409, description="Document number already exists. Use the controlled revision action.")
        system_id = request.form.get("system_id", type=int)
        subsystem_id = request.form.get("subsystem_id", type=int)
        equipment_id = request.form.get("equipment_id", type=int)
        system = None
        if system_id:
            system = CommissioningSystem.query.filter_by(
                id=system_id, company_name=project.company_name, project_id=project.id,
            ).first_or_404()
        subsystem = None
        if subsystem_id:
            if not system:
                abort(400, description="Select a system when linking a subsystem.")
            subsystem = CommissioningSubsystem.query.filter_by(
                id=subsystem_id, company_name=project.company_name, system_id=system.id,
            ).first_or_404()
        if equipment_id:
            if not subsystem:
                abort(400, description="Select a subsystem when linking equipment.")
            CommissioningEquipment.query.filter_by(
                id=equipment_id, company_name=project.company_name,
                project_id=project.id, subsystem_id=subsystem.id,
            ).first_or_404()
        document = CommissioningDocument(
            company_name=project.company_name, project_id=project.id,
            system_id=system.id if system else None,
            subsystem_id=subsystem.id if subsystem else None,
            equipment_id=equipment_id, document_number=number,
            revision="A", revision_sequence=1,
            title=_required("title", 250),
            document_type=_required("document_type", 80),
            discipline=_required("discipline", 80),
            purpose=(request.form.get("purpose") or "").strip()[:80] or None,
            status=DocumentStatus.DRAFT, created_by_id=current_user.id,
        )
        db.session.add(document)
        db.session.flush()
        add_audit_event(project.company_name, "CommissioningDocument", document.id,
                        "DOCUMENT_CREATED", after={
                            "document_number": number, "revision": "A",
                            "title": document.title, "document_type": document.document_type,
                        })
        db.session.commit()
        flash("Document revision A added to the register.", "success")
        return redirect(url_for("commissioning.document_register", project_id=project.id))

    documents = CommissioningDocument.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).order_by(CommissioningDocument.document_number,
               CommissioningDocument.revision_sequence.desc()).all()
    document_ids = [item.id for item in documents]
    reviews = CommissioningDocumentReview.query.filter(
        CommissioningDocumentReview.company_name == project.company_name,
        CommissioningDocumentReview.document_id.in_(document_ids or [-1]),
    ).order_by(CommissioningDocumentReview.decided_at.desc()).all()
    review_by_document = {}
    for review in reviews:
        review_by_document.setdefault(review.document_id, []).append(review)
    attachments = CommissioningAttachment.query.filter(
        CommissioningAttachment.company_name == project.company_name,
        CommissioningAttachment.entity_type == "CommissioningDocument",
        CommissioningAttachment.entity_id.in_(document_ids or [-1]),
    ).order_by(CommissioningAttachment.uploaded_at.desc()).all()
    attachment_by_document = {}
    for attachment in attachments:
        attachment_by_document.setdefault(attachment.entity_id, []).append(attachment)
    systems = CommissioningSystem.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).filter(CommissioningSystem.status != "ARCHIVED").order_by(CommissioningSystem.system_code).all()
    subsystems = CommissioningSubsystem.query.join(
        CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id,
    ).filter(CommissioningSubsystem.company_name == project.company_name,
             CommissioningSystem.project_id == project.id,
             CommissioningSubsystem.status != "ARCHIVED").order_by(CommissioningSubsystem.subsystem_code).all()
    equipment = CommissioningEquipment.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).order_by(CommissioningEquipment.tag_number).all()
    return render_template(
        "commissioning/document_register.html", project=project, documents=documents,
        review_by_document=review_by_document, attachment_by_document=attachment_by_document,
        systems=systems, subsystems=subsystems, equipment=equipment,
        system_by_id={item.id: item for item in systems},
        subsystem_by_id={item.id: item for item in subsystems},
        equipment_by_id={item.id: item for item in equipment},
        statuses=list(DocumentStatus),
        can_create=any(has_permission(project.id, p) for p in ("documents.create", "documents.manage", "project.manage")),
        can_review=any(has_permission(project.id, p) for p in ("documents.review", "documents.manage", "project.manage")),
        can_approve=any(has_permission(project.id, p) for p in ("documents.approve", "documents.manage", "project.manage")),
    )


@commissioning_bp.post("/documents/<int:document_id>/submit")
@login_required
def submit_document(document_id):
    document = CommissioningDocument.query.filter_by(
        id=document_id, company_name=current_user.company_name,
    ).first_or_404()
    _need(document.project_id, "documents.create", "documents.manage", "project.manage")
    if document.status not in (DocumentStatus.DRAFT, DocumentStatus.REJECTED):
        abort(409, description="Only draft or rejected revisions can be submitted.")
    evidence = CommissioningAttachment.query.filter_by(
        company_name=document.company_name, entity_type="CommissioningDocument",
        entity_id=document.id,
    ).first()
    if evidence is None:
        abort(409, description="Upload the controlled document file before submitting it for review.")
    before = {"status": document.status.value}
    document.status = DocumentStatus.IN_REVIEW
    document.submitted_at = datetime.utcnow()
    add_audit_event(document.company_name, "CommissioningDocument", document.id,
                    "DOCUMENT_SUBMITTED", before=before,
                    after={"status": document.status.value})
    db.session.commit()
    flash("Document submitted for review.", "success")
    return redirect(url_for("commissioning.document_register", project_id=document.project_id))


@commissioning_bp.post("/documents/<int:document_id>/decision")
@login_required
def decide_document(document_id):
    document = CommissioningDocument.query.filter_by(
        id=document_id, company_name=current_user.company_name,
    ).first_or_404()
    _need(document.project_id, "documents.review", "documents.approve", "documents.manage", "project.manage")
    decision = _required("decision", 20).upper()
    comments = (request.form.get("comments") or "").strip()[:3000]
    if document.status != DocumentStatus.IN_REVIEW:
        abort(409, description="Only documents in review can receive a decision.")
    if document.created_by_id == current_user.id:
        abort(403, description="The document author cannot approve or reject their own revision.")
    if decision == "APPROVE":
        if not (has_permission(document.project_id, "documents.approve")
                or has_permission(document.project_id, "documents.manage")
                or has_permission(document.project_id, "project.manage")):
            abort(403)
        target = DocumentStatus.APPROVED
    elif decision == "REJECT":
        if not (has_permission(document.project_id, "documents.review")
                or has_permission(document.project_id, "documents.manage")
                or has_permission(document.project_id, "project.manage")):
            abort(403)
        if not comments:
            abort(400, description="A reason is required when rejecting a document.")
        target = DocumentStatus.REJECTED
    else:
        abort(400, description="Decision must be APPROVE or REJECT.")
    before = {"status": document.status.value}
    document.status = target
    if target == DocumentStatus.APPROVED:
        document.approved_by_id = current_user.id
        document.approved_at = datetime.utcnow()
    review = CommissioningDocumentReview(
        company_name=document.company_name, document_id=document.id,
        reviewer_id=current_user.id, decision=decision, comments=comments or None,
    )
    db.session.add(review)
    add_audit_event(document.company_name, "CommissioningDocument", document.id,
                    "DOCUMENT_" + decision + "D" if decision == "APPROVE" else "DOCUMENT_REJECTED",
                    before=before, after={"status": target.value, "comments": comments or None})
    db.session.commit()
    flash("Document decision recorded.", "success")
    return redirect(url_for("commissioning.document_register", project_id=document.project_id))


@commissioning_bp.post("/documents/<int:document_id>/revision")
@login_required
def create_document_revision(document_id):
    source = CommissioningDocument.query.filter_by(
        id=document_id, company_name=current_user.company_name,
    ).first_or_404()
    _need(source.project_id, "documents.create", "documents.manage", "project.manage")
    if source.status not in (DocumentStatus.APPROVED, DocumentStatus.REJECTED):
        abort(409, description="A new revision can only be created from an approved or rejected revision.")
    latest_sequence = db.session.query(db.func.max(CommissioningDocument.revision_sequence)).filter_by(
        company_name=source.company_name, project_id=source.project_id,
        document_number=source.document_number,
    ).scalar() or source.revision_sequence
    next_sequence = latest_sequence + 1
    next_revision = chr(64 + next_sequence) if next_sequence <= 26 else f"R{next_sequence}"
    revision = CommissioningDocument(
        company_name=source.company_name, project_id=source.project_id,
        system_id=source.system_id, subsystem_id=source.subsystem_id,
        equipment_id=source.equipment_id, document_number=source.document_number,
        revision=next_revision, revision_sequence=next_sequence, supersedes_id=source.id,
        title=source.title, document_type=source.document_type,
        discipline=source.discipline, purpose=source.purpose,
        status=DocumentStatus.DRAFT, created_by_id=current_user.id,
    )
    db.session.add(revision)
    if source.status == DocumentStatus.APPROVED:
        source.status = DocumentStatus.SUPERSEDED
    db.session.flush()
    add_audit_event(source.company_name, "CommissioningDocument", revision.id,
                    "DOCUMENT_REVISION_CREATED",
                    before={"supersedes_id": source.id, "revision": source.revision},
                    after={"revision": next_revision, "supersedes_id": source.id})
    db.session.commit()
    flash(f"Revision {next_revision} created as a new controlled draft.", "success")
    return redirect(url_for("commissioning.document_register", project_id=source.project_id))



@commissioning_bp.get("/projects/<int:project_id>/subsystems/<int:subsystem_id>/dossier")
@login_required
def subsystem_dossier(project_id, subsystem_id):
    """Consolidated, evidence-based readiness view for one commissioning subsystem."""
    _need(project_id, "structure.view", "handover.view", "handover.manage",
          "handover.accept", "reports.view", "project.manage")
    project = get_project(project_id)
    subsystem = CommissioningSubsystem.query.join(
        CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id,
    ).filter(
        CommissioningSubsystem.id == subsystem_id,
        CommissioningSubsystem.company_name == project.company_name,
        CommissioningSystem.project_id == project.id,
    ).first_or_404()
    documents_all = CommissioningDocument.query.filter_by(
        company_name=project.company_name, project_id=project.id,
        subsystem_id=subsystem.id,
    ).order_by(CommissioningDocument.document_number,
               CommissioningDocument.revision_sequence.desc()).all()
    latest_documents = {}
    for document in documents_all:
        latest_documents.setdefault(document.document_number, document)
    documents = list(latest_documents.values())
    sheets = CheckSheet.query.filter_by(
        company_name=project.company_name, project_id=project.id,
        subsystem_id=subsystem.id,
    ).order_by(CheckSheet.sheet_number).all()
    punches = PunchItem.query.filter_by(
        company_name=project.company_name, project_id=project.id,
        subsystem_id=subsystem.id,
    ).order_by(PunchItem.punch_number).all()
    witnesses = WitnessPoint.query.join(
        CheckSheet, CheckSheet.id == WitnessPoint.check_sheet_id,
    ).filter(
        WitnessPoint.company_name == project.company_name,
        WitnessPoint.project_id == project.id,
        CheckSheet.subsystem_id == subsystem.id,
    ).order_by(WitnessPoint.scheduled_at).all()
    tasks = CommissioningTask.query.filter_by(
        company_name=project.company_name, project_id=project.id,
        subsystem_id=subsystem.id,
    ).order_by(CommissioningTask.task_number).all()
    equipment = CommissioningEquipment.query.filter_by(
        company_name=project.company_name, project_id=project.id,
        subsystem_id=subsystem.id,
    ).order_by(CommissioningEquipment.tag_number).all()
    document_ids = [item.id for item in documents]
    attachments = CommissioningAttachment.query.filter(
        CommissioningAttachment.company_name == project.company_name,
        CommissioningAttachment.entity_type == "CommissioningDocument",
        CommissioningAttachment.entity_id.in_(document_ids or [-1]),
    ).all()
    evidence_by_document = {}
    for attachment in attachments:
        evidence_by_document.setdefault(attachment.entity_id, []).append(attachment)

    unsigned_sheets = [item for item in sheets if item.status != CheckSheetStatus.SIGNED_OFF]
    unapproved_documents = [item for item in documents if item.status != DocumentStatus.APPROVED]
    open_critical_punches = [
        item for item in punches
        if item.category in (PunchCategory.A, PunchCategory.B)
        and item.status not in (PunchStatus.VERIFIED, PunchStatus.WAIVED)
    ]
    open_other_punches = [
        item for item in punches
        if item.category not in (PunchCategory.A, PunchCategory.B)
        and item.status not in (PunchStatus.VERIFIED, PunchStatus.WAIVED)
    ]
    pending_holds = [
        item for item in witnesses
        if item.type == WitnessType.HOLD
        and item.status not in (WitnessStatus.RELEASED, WitnessStatus.CANCELLED)
    ]
    incomplete_tasks = [item for item in tasks if item.status != CommissioningTaskStatus.COMPLETED]
    gates = [
        {"name": "Check Sheets", "passed": bool(sheets) and not unsigned_sheets,
         "detail": f"{len(sheets) - len(unsigned_sheets)} of {len(sheets)} signed off"},
        {"name": "Current engineering documents", "passed": bool(documents) and not unapproved_documents,
         "detail": f"{len(documents) - len(unapproved_documents)} of {len(documents)} current revisions approved"},
        {"name": "Category A / B Punch", "passed": not open_critical_punches,
         "detail": f"{len(open_critical_punches)} open critical Punch items"},
        {"name": "Hold points", "passed": not pending_holds,
         "detail": f"{len(pending_holds)} pending Hold points"},
    ]
    readiness_passed = all(item["passed"] for item in gates)
    return render_template(
        "commissioning/subsystem_dossier.html", project=project, subsystem=subsystem,
        documents=documents, evidence_by_document=evidence_by_document,
        sheets=sheets, punches=punches, witnesses=witnesses, tasks=tasks,
        equipment=equipment, gates=gates, readiness_passed=readiness_passed,
        unsigned_sheets=unsigned_sheets, unapproved_documents=unapproved_documents,
        open_critical_punches=open_critical_punches, open_other_punches=open_other_punches,
        pending_holds=pending_holds, incomplete_tasks=incomplete_tasks,
    )



@commissioning_bp.post("/projects/<int:project_id>/tasks/<int:task_id>/dependencies")
@login_required
def add_task_dependency(project_id, task_id):
    """Add a validated finish-to-start predecessor without permitting cycles."""
    _need(project_id, "tasks.manage", "project.manage")
    project = get_project(project_id)
    successor = CommissioningTask.query.filter_by(
        id=task_id, company_name=project.company_name, project_id=project.id,
    ).first_or_404()
    predecessor = CommissioningTask.query.filter_by(
        id=request.form.get("predecessor_task_id", type=int),
        company_name=project.company_name, project_id=project.id,
    ).first_or_404()
    if predecessor.id == successor.id:
        abort(400, description="A task cannot depend on itself.")
    if CommissioningTaskDependency.query.filter_by(
        company_name=project.company_name, project_id=project.id,
        predecessor_task_id=predecessor.id, successor_task_id=successor.id,
    ).first():
        abort(409, description="This predecessor is already linked.")
    try:
        lag_days = int(request.form.get("lag_days") or 0)
    except (TypeError, ValueError):
        abort(400, description="Lag days must be a non-negative whole number.")
    if lag_days < 0:
        abort(400, description="Lag days cannot be negative.")

    graph = {}
    for edge in CommissioningTaskDependency.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).all():
        graph.setdefault(edge.predecessor_task_id, set()).add(edge.successor_task_id)
    pending, visited = [successor.id], set()
    while pending:
        node = pending.pop()
        if node == predecessor.id:
            abort(409, description="This dependency would create a circular task sequence.")
        if node not in visited:
            visited.add(node)
            pending.extend(graph.get(node, ()))

    dependency = CommissioningTaskDependency(
        company_name=project.company_name, project_id=project.id,
        predecessor_task_id=predecessor.id, successor_task_id=successor.id,
        dependency_type="FINISH_TO_START", lag_days=lag_days,
        created_by_id=current_user.id,
    )
    db.session.add(dependency)
    add_audit_event(project.company_name, "CommissioningTask", successor.id,
                    "TASK_DEPENDENCY_ADDED",
                    after={"predecessor_task_id": predecessor.id,
                           "predecessor_task_number": predecessor.task_number,
                           "dependency_type": "FINISH_TO_START", "lag_days": lag_days})
    db.session.commit()
    flash(f"Predecessor {predecessor.task_number} linked to {successor.task_number}.", "success")
    return redirect(url_for("commissioning.task_register", project_id=project.id))


@commissioning_bp.post("/projects/<int:project_id>/tasks/<int:task_id>/dependencies/<int:dependency_id>/remove")
@login_required
def remove_task_dependency(project_id, task_id, dependency_id):
    """Remove a task link with an auditable change record."""
    _need(project_id, "tasks.manage", "project.manage")
    project = get_project(project_id)
    successor = CommissioningTask.query.filter_by(
        id=task_id, company_name=project.company_name, project_id=project.id,
    ).first_or_404()
    dependency = CommissioningTaskDependency.query.filter_by(
        id=dependency_id, company_name=project.company_name, project_id=project.id,
        successor_task_id=successor.id,
    ).first_or_404()
    predecessor = CommissioningTask.query.filter_by(
        id=dependency.predecessor_task_id, company_name=project.company_name,
        project_id=project.id,
    ).first()
    add_audit_event(project.company_name, "CommissioningTask", successor.id,
                    "TASK_DEPENDENCY_REMOVED",
                    before={"predecessor_task_id": dependency.predecessor_task_id,
                            "predecessor_task_number": predecessor.task_number if predecessor else None,
                            "dependency_type": dependency.dependency_type,
                            "lag_days": dependency.lag_days})
    db.session.delete(dependency)
    db.session.commit()
    flash("Task dependency removed.", "success")
    return redirect(url_for("commissioning.task_register", project_id=project.id))

