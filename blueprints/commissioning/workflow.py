"""OPERA operational workflows: membership, check sheets, punch, witness and handover."""
from datetime import date, datetime
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import User
from models_commissioning import (
    CommissioningMembership, CommissioningProject, CommissioningSystem,
    CommissioningSubsystem, CheckSheet, CheckSheetItem, CheckSheetRevision,
    CheckSheetType, CheckSheetStatus, ItemResultStatus, MembershipRole,
    PunchItem, PunchHistory, PunchCategory, PunchSeverity, PunchStatus,
    WitnessPoint, WitnessType, WitnessStatus, HandoverPackage, HandoverStatus,
    ProgressSnapshot, CommissioningSignature,
)
from services.commissioning_access import (
    add_audit_event, get_project, has_permission,
)
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
    sheets = CheckSheet.query.filter_by(company_name=project.company_name, project_id=project.id).order_by(CheckSheet.created_at.desc()).all()
    punches = PunchItem.query.filter_by(company_name=project.company_name, project_id=project.id).order_by(PunchItem.raised_at.desc()).all()
    witnesses = WitnessPoint.query.filter_by(company_name=project.company_name, project_id=project.id).order_by(WitnessPoint.scheduled_at.desc()).all()
    packages = HandoverPackage.query.filter_by(company_name=project.company_name, project_id=project.id).order_by(HandoverPackage.created_at.desc()).all()
    members = CommissioningMembership.query.filter_by(company_name=project.company_name, project_id=project.id, is_active=True).all()
    users = User.query.filter_by(company_name=project.company_name).order_by(User.full_name).all()
    subsystems = (CommissioningSubsystem.query
        .join(CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id)
        .filter(CommissioningSubsystem.company_name == project.company_name,
                CommissioningSystem.project_id == project.id,
                CommissioningSubsystem.status != "ARCHIVED")
        .order_by(CommissioningSubsystem.subsystem_code).all())
    total = len(sheets)
    signed = sum(1 for item in sheets if item.status == CheckSheetStatus.SIGNED_OFF)
    punch_open = sum(1 for item in punches if item.status not in (PunchStatus.VERIFIED, PunchStatus.WAIVED))
    percent = round((signed / total) * 100, 2) if total else 0.0
    return render_template(
        "commissioning/operations.html", project=project, sheets=sheets,
        punches=punches, witnesses=witnesses, packages=packages, members=members,
        users=users, subsystems=subsystems, roles=list(MembershipRole),
        witness_items=CheckSheetItem.query.join(CheckSheet, CheckSheet.id == CheckSheetItem.check_sheet_id).filter(CheckSheet.company_name == project.company_name, CheckSheet.project_id == project.id).order_by(CheckSheet.sheet_number, CheckSheetItem.sequence).all(),
        sheet_types=list(CheckSheetType), punch_categories=list(PunchCategory),
        punch_severities=list(PunchSeverity), witness_types=list(WitnessType),
        progress=percent, signed=signed, total=total, punch_open=punch_open,
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
    flash("عضو پروژه به‌روزرسانی شد.", "success")
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
    subsystem = CommissioningSubsystem.query.join(CommissioningSystem).filter(
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
    return render_template("commissioning/checksheet_detail.html", sheet=sheet, items=items,
                           results=list(ItemResultStatus), can_fill=has_permission(sheet.project_id, "checksheets.fill") or has_permission(sheet.project_id, "checksheets.manage"))


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
    if sheet.status not in (CheckSheetStatus.ISSUED, CheckSheetStatus.IN_PROGRESS):
        abort(409, description="Only issued sheets may be completed")
    item = CheckSheetItem.query.filter_by(
        id=item_id, company_name=sheet.company_name, check_sheet_id=sheet.id
    ).first_or_404()
    old = item.result_status.value
    item.actual_result = (request.form.get("actual_result") or "").strip() or None
    item.result_status = _enum(ItemResultStatus, _required("result_status", 20), "result")
    item.remarks = (request.form.get("remarks") or "").strip() or None
    item.operator_id = current_user.id
    if item.result_status == ItemResultStatus.OK:
        item.verified_by_id, item.verified_at = current_user.id, datetime.utcnow()
    sheet.status = CheckSheetStatus.IN_PROGRESS
    add_audit_event(sheet.company_name, "CheckSheetItem", item.id, "CHECKSHEET_ITEM_RESULT",
                    before={"result": old}, after={"result": item.result_status.value})
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
        required_ids = [i.id for i in items if i.witness_required]
        released = {w.check_sheet_item_id for w in WitnessPoint.query.filter_by(
            company_name=sheet.company_name, check_sheet_id=sheet.id, status=WitnessStatus.RELEASED
        ).all()}
        if any(iid not in released for iid in required_ids):
            abort(409, description="Required witness points must be released before sign-off")
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
    subsystem = CommissioningSubsystem.query.join(CommissioningSystem).filter(
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
    subsystem = CommissioningSubsystem.query.join(CommissioningSystem).filter(
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


@commissioning_bp.post("/projects/<int:project_id>/reports/snapshot")
@login_required
def create_progress_snapshot(project_id):
    _need(project_id, "reports.view", "project.manage")
    project = get_project(project_id)
    snapshot_date = _date("snapshot_date") or date.today()
    sheets = CheckSheet.query.filter_by(company_name=project.company_name, project_id=project.id).all()
    punches = PunchItem.query.filter_by(company_name=project.company_name, project_id=project.id).all()
    signed = sum(1 for s in sheets if s.status == CheckSheetStatus.SIGNED_OFF)
    completed_punches = sum(1 for p in punches if p.status in (PunchStatus.VERIFIED, PunchStatus.WAIVED))
    total = len(sheets)
    percent = round((signed / total) * 100, 2) if total else 0.0
    weighted = round(sum(s.sheet_weight for s in sheets if s.status == CheckSheetStatus.SIGNED_OFF) /
                     sum(s.sheet_weight for s in sheets) * 100, 2) if sheets and sum(s.sheet_weight for s in sheets) else 0.0
    snapshot = ProgressSnapshot.query.filter_by(company_name=project.company_name,
        project_id=project.id, system_id=None, subsystem_id=None, snapshot_date=snapshot_date).first()
    if snapshot is None:
        snapshot = ProgressSnapshot(company_name=project.company_name, project_id=project.id,
            snapshot_date=snapshot_date)
        db.session.add(snapshot)
    snapshot.percent_complete, snapshot.weighted_percent = percent, weighted
    snapshot.punch_open_count, snapshot.punch_closed_count = len(punches)-completed_punches, completed_punches
    snapshot.checksheet_total, snapshot.checksheet_signed_off = total, signed
    add_audit_event(project.company_name, "ProgressSnapshot", snapshot.id or 0,
                    "PROGRESS_SNAPSHOT_CREATED", after={"percent_complete": percent, "weighted_percent": weighted})
    db.session.commit()
    flash("گزارش پیشرفت ذخیره شد.", "success")
    return redirect(url_for("commissioning.operations", project_id=project.id))
