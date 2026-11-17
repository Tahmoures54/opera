"""OPERA operational workflows: membership, check sheets, punch, witness and handover."""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from io import BytesIO
from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from extensions import db
from models import User
from models_commissioning import (
    CommissioningMembership, CommissioningProject, CommissioningSystem, CommissioningSubsystem, CommissioningEquipment, CommissioningTask, CommissioningTaskDependency, CommissioningTaskType, CommissioningTaskStatus,
    CommissioningDocument, CommissioningDocumentReview, CommissioningDossierRequirement, CommissioningDossierRevision, CommissioningDossierReview, DossierRevisionStatus, DossierReviewDecision, CommissioningPreservationInspection, CommissioningCheckSheetTemplate, DocumentStatus,
    CheckSheet, CheckSheetItem, CheckSheetRevision,
    CheckSheetType, CheckSheetStatus, ItemResultStatus, MembershipRole,
    PunchItem, PunchHistory, PunchCategory, PunchSeverity, PunchStatus,
    WitnessPoint, WitnessType, WitnessStatus, HandoverPackage, HandoverStatus, CommissioningCertificate,
    ProgressSnapshot, CommissioningSignature, CommissioningAttachment,
)
from services.commissioning_access import (
    add_audit_event, get_project, has_permission,
)
from services.commissioning_storage import (store_commissioning_upload, read_commissioning_upload, delete_commissioning_upload)
from services.commissioning_dossier_export import (build_subsystem_dossier_snapshot, render_subsystem_dossier_pdf, render_subsystem_dossier_zip)
from services.commissioning_number_service import (
    next_checksheet_number, next_punch_number,
)
from services.commissioning_readiness import evaluate_subsystem_readiness
from services.commissioning_readiness_policy import normalize_readiness_policy
from services.commissioning_handover_gates import (
    require_ready_for_mc,
    require_ready_for_rfc,
    require_ready_for_rfsu,
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



def _validate_template_items(raw):
    try:
        items = json.loads(raw)
    except (TypeError, ValueError):
        abort(400, description="Template items must be valid JSON.")
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        abort(400, description="A template must contain between 1 and 100 items.")
    normalized = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            abort(400, description=f"Template item {index} must be an object.")
        description = str(item.get("description") or "").strip()
        if not description or len(description) > 1000:
            abort(400, description=f"Template item {index} needs a description (maximum 1000 characters).")
        for key, limit in (("expected_result", 2000), ("acceptance_criteria", 2000), ("unit", 40)):
            value = item.get(key)
            if value is not None and (not isinstance(value, str) or len(value.strip()) > limit):
                abort(400, description=f"Template item {index} has an invalid {key}.")
        witness_required = item.get("witness_required", False)
        mandatory = item.get("mandatory", True)
        if not isinstance(witness_required, bool) or not isinstance(mandatory, bool):
            abort(400, description=f"Template item {index} boolean flags must be true or false.")
        measurement_type = str(item.get("measurement_type") or "QUALITATIVE").strip().upper()
        if measurement_type not in ("QUALITATIVE", "NUMERIC"):
            abort(400, description=f"Template item {index} has an invalid measurement_type.")

        def parse_limit(key):
            raw_value = item.get(key)
            if raw_value in (None, ""):
                return None
            try:
                value = Decimal(str(raw_value))
            except (InvalidOperation, TypeError, ValueError):
                abort(400, description=f"Template item {index} has an invalid {key}.")
            if not value.is_finite() or len(str(raw_value)) > 40:
                abort(400, description=f"Template item {index} has an invalid {key}.")
            return format(value, "f")

        minimum_value = parse_limit("minimum_value")
        maximum_value = parse_limit("maximum_value")
        if measurement_type == "NUMERIC":
            if not (item.get("unit") or "").strip():
                abort(400, description=f"Template item {index} numeric measurement requires a unit.")
            if minimum_value is not None and maximum_value is not None:
                if Decimal(minimum_value) > Decimal(maximum_value):
                    abort(400, description=f"Template item {index} minimum_value cannot exceed maximum_value.")
        elif minimum_value is not None or maximum_value is not None:
            abort(400, description=f"Template item {index} limits require NUMERIC measurement_type.")

        normalized.append({
            "sequence": index,
            "description": description,
            "expected_result": (item.get("expected_result") or "").strip() or None,
            "acceptance_criteria": (item.get("acceptance_criteria") or "").strip() or None,
            "unit": (item.get("unit") or "").strip() or None,
            "measurement_type": measurement_type,
            "minimum_value": minimum_value,
            "maximum_value": maximum_value,
            "witness_required": witness_required,
            "mandatory": mandatory,
        })
    if not any(item["mandatory"] for item in normalized):
        abort(400, description="A template must contain at least one mandatory item.")
    return normalized

def _positive_int(name):
    try:
        value = int(_required(name, 20))
    except ValueError:
        abort(400, description=f"Invalid {name}")
    if value < 1:
        abort(400, description=f"Invalid {name}")
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


def _dossier_snapshot_digest(snapshot):
    payload = json.dumps(
        snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _dossier_revision_attachments(revision):
    evidence = revision.snapshot_json.get("evidence", [])
    ids = [int(item["id"]) for item in evidence]
    if len(ids) != len(set(ids)):
        abort(409, description="The dossier snapshot contains duplicate evidence references.")
    records = CommissioningAttachment.query.filter(
        CommissioningAttachment.company_name == revision.company_name,
        CommissioningAttachment.id.in_(ids or [-1]),
    ).all()
    by_id = {item.id: item for item in records}
    if len(by_id) != len(ids):
        abort(409, description="One or more dossier evidence records are no longer available.")
    ordered = []
    for item in evidence:
        attachment = by_id[int(item["id"])]
        if (
            attachment.checksum != item.get("sha256")
            or attachment.filename != item.get("filename")
            or attachment.file_size != item.get("file_size")
        ):
            abort(409, description="Dossier evidence metadata no longer matches its approved snapshot.")
        try:
            content = read_commissioning_upload(attachment.storage_key)
        except Exception:
            abort(409, description=f"Evidence file {attachment.filename} is unavailable.")
        if hashlib.sha256(content).hexdigest() != attachment.checksum:
            abort(409, description=f"Evidence checksum mismatch for {attachment.filename}.")
        ordered.append(attachment)
    return ordered


def _require_issued_dossier(dossier_id):
    revision = CommissioningDossierRevision.query.filter_by(
        id=dossier_id, company_name=current_user.company_name,
    ).first_or_404()
    _need(
        revision.project_id, "dossier.view", "dossier.manage",
        "dossier.review", "dossier.issue", "project.manage",
    )
    if revision.status != DossierRevisionStatus.ISSUED:
        abort(409, description="Only an issued dossier revision can be exported.")
    if _dossier_snapshot_digest(revision.snapshot_json) != revision.snapshot_sha256:
        abort(409, description="The stored dossier snapshot failed its integrity check.")
    attachments = _dossier_revision_attachments(revision)
    snapshot = dict(revision.snapshot_json)
    snapshot["dossier_control"] = {
        "revision_number": revision.revision_number,
        "status": revision.status.value,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
        "submitted_at": revision.submitted_at.isoformat() if revision.submitted_at else None,
        "approved_at": revision.approved_at.isoformat() if revision.approved_at else None,
        "issued_at": revision.issued_at.isoformat() if revision.issued_at else None,
        "snapshot_sha256": revision.snapshot_sha256,
    }
    return revision, snapshot, attachments


@commissioning_bp.get("/projects/<int:project_id>/operations")
@login_required
def operations(project_id):
    _need(project_id, "structure.view", "project.manage", "checksheets.view",
          "checksheets.manage", "checksheets.create", "punch.view", "punch.raise",
          "witness.view", "witness.manage", "handover.view", "handover.manage",
          "reports.view")
    project = get_project(project_id)
    dossier_requirements = CommissioningDossierRequirement.query.filter_by(
        company_name=project.company_name, project_id=project.id, is_active=True,
    ).order_by(
        CommissioningDossierRequirement.document_type,
        CommissioningDossierRequirement.discipline,
    ).all()
    checksheet_templates = CommissioningCheckSheetTemplate.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).order_by(CommissioningCheckSheetTemplate.template_code, CommissioningCheckSheetTemplate.revision.desc()).all()
    equipment = CommissioningEquipment.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).order_by(CommissioningEquipment.tag_number).all()
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
    certificates = CommissioningCertificate.query.filter(
        CommissioningCertificate.company_name == project.company_name,
        CommissioningCertificate.project_id == project.id,
        CommissioningCertificate.package_id.in_(package_ids or [-1]),
    ).order_by(CommissioningCertificate.issued_at).all()
    certificates_by_package = {}
    for certificate in certificates:
        certificate_key = "RFC" if certificate.certificate_type == "RF" else certificate.certificate_type
        certificates_by_package.setdefault(certificate.package_id, {})[certificate_key] = certificate
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
        punches=punches, witnesses=witnesses, packages=packages, snapshots=snapshots,
        certificates_by_package=certificates_by_package, members=members,
        dossier_requirements=dossier_requirements,
        can_manage_dossier_requirements=has_permission(project.id, "documents.manage"),
        users=users, project_users=[user for user in users if user.id in {member.user_id for member in members}],
        systems=systems, subsystems=subsystems, system_by_id=system_by_id,
        subsystem_by_id=subsystem_by_id, roles=list(MembershipRole),
        evidence_by_entity=evidence_by_entity,
        can_upload_punch_evidence=any(has_permission(project.id, p) for p in ("punch.raise", "punch.assign", "punch.verify")),
        can_manage_structure=has_permission(project.id, "structure.manage"),
        can_view_preservation=any(has_permission(project.id, p) for p in ("preservation.view", "preservation.manage")),
        can_upload_handover_evidence=any(has_permission(project.id, p) for p in ("handover.manage", "handover.accept")),
        witness_items=CheckSheetItem.query.join(CheckSheet, CheckSheet.id == CheckSheetItem.check_sheet_id).filter(CheckSheet.company_name == project.company_name, CheckSheet.project_id == project.id).order_by(CheckSheet.sheet_number, CheckSheetItem.sequence).all(),
        sheet_types=list(CheckSheetType), checksheet_templates=checksheet_templates,
        can_manage_templates=has_permission(project.id, "checksheets.manage"), equipment=equipment,
        punch_categories=list(PunchCategory),
        punch_severities=list(PunchSeverity), witness_types=list(WitnessType),
        progress=percent, weighted_progress=weighted_progress,
        today=date.today().isoformat(),
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


@commissioning_bp.post("/projects/<int:project_id>/checksheet-templates")
@login_required
def create_checksheet_template(project_id):
    _need(project_id, "checksheets.manage")
    project = get_project(project_id)
    template_code = _required("template_code", 80).upper()
    if CommissioningCheckSheetTemplate.query.filter_by(
        company_name=project.company_name, project_id=project.id,
        template_code=template_code, revision=1,
    ).first():
        abort(409, description="Template code already exists. Create a new revision instead.")
    discipline = (request.form.get("discipline") or "ANY").strip().upper() or "ANY"
    equipment_type = (request.form.get("equipment_type") or "").strip().upper() or None
    if len(discipline) > 80 or (equipment_type is not None and len(equipment_type) > 100):
        abort(400, description="Template discipline or equipment type is too long.")
    template = CommissioningCheckSheetTemplate(
        company_name=project.company_name, project_id=project.id,
        template_code=template_code, title=_required("title", 200),
        sheet_type=_enum(CheckSheetType, _required("sheet_type", 30), "sheet type"),
        discipline=discipline,
        equipment_type=equipment_type,
        acceptance_criteria=(request.form.get("acceptance_criteria") or "").strip() or None,
        revision=1, items_json=_validate_template_items(_required("items_json", 20000)),
        status="DRAFT", created_by_id=current_user.id,
    )
    db.session.add(template)
    db.session.flush()
    add_audit_event(
        project.company_name, "CommissioningCheckSheetTemplate", template.id,
        "CHECKSHEET_TEMPLATE_CREATED",
        after={"template_code": template_code, "revision": 1, "status": "DRAFT"},
    )
    db.session.commit()
    flash("Check Sheet template draft created.", "success")
    return redirect(url_for("commissioning.operations", project_id=project.id))


@commissioning_bp.post("/projects/<int:project_id>/checksheet-templates/<int:template_id>/update")
@login_required
def update_checksheet_template(project_id, template_id):
    _need(project_id, "checksheets.manage")
    project = get_project(project_id)
    template = CommissioningCheckSheetTemplate.query.filter_by(
        id=template_id, company_name=project.company_name, project_id=project.id,
    ).first_or_404()
    if template.status != "DRAFT":
        abort(409, description="Only draft templates can be edited. Create a new revision for an approved template.")
    before = {
        "title": template.title, "discipline": template.discipline,
        "equipment_type": template.equipment_type, "items": template.items_json,
        "acceptance_criteria": template.acceptance_criteria,
    }
    template.title = _required("title", 200)
    discipline = (request.form.get("discipline") or "ANY").strip().upper() or "ANY"
    equipment_type = (request.form.get("equipment_type") or "").strip().upper() or None
    if len(discipline) > 80 or (equipment_type is not None and len(equipment_type) > 100):
        abort(400, description="Template discipline or equipment type is too long.")
    template.discipline = discipline
    template.equipment_type = equipment_type
    template.acceptance_criteria = (request.form.get("acceptance_criteria") or "").strip() or None
    template.items_json = _validate_template_items(_required("items_json", 20000))
    after = {
        "title": template.title, "discipline": template.discipline,
        "equipment_type": template.equipment_type, "items": template.items_json,
        "acceptance_criteria": template.acceptance_criteria,
    }
    add_audit_event(
        project.company_name, "CommissioningCheckSheetTemplate", template.id,
        "CHECKSHEET_TEMPLATE_UPDATED", before=before, after=after,
    )
    db.session.commit()
    flash("Check Sheet template draft updated.", "success")
    return redirect(url_for("commissioning.operations", project_id=project.id))


@commissioning_bp.post("/projects/<int:project_id>/checksheet-templates/<int:template_id>/approve")
@login_required
def approve_checksheet_template(project_id, template_id):
    _need(project_id, "checksheets.manage")
    project = get_project(project_id)
    template = CommissioningCheckSheetTemplate.query.filter_by(
        id=template_id, company_name=project.company_name, project_id=project.id,
    ).with_for_update().first_or_404()
    if template.status != "DRAFT" or not template.items_json:
        abort(409, description="Only a non-empty draft template can be approved.")
    previous = None
    if template.supersedes_id is not None:
        previous = CommissioningCheckSheetTemplate.query.filter_by(
            id=template.supersedes_id, company_name=project.company_name,
            project_id=project.id,
        ).with_for_update().first_or_404()
        if previous.status != "APPROVED":
            abort(409, description="The superseded revision is no longer approved.")
        previous.status = "RETIRED"
        add_audit_event(
            project.company_name, "CommissioningCheckSheetTemplate", previous.id,
            "CHECKSHEET_TEMPLATE_RETIRED",
            before={"status": "APPROVED"},
            after={"status": "RETIRED", "superseded_by_id": template.id},
        )
    template.status = "APPROVED"
    template.approved_by_id = current_user.id
    template.approved_at = datetime.utcnow()
    add_audit_event(
        project.company_name, "CommissioningCheckSheetTemplate", template.id,
        "CHECKSHEET_TEMPLATE_APPROVED",
        after={"template_code": template.template_code, "revision": template.revision,
               "approved_by_id": current_user.id, "approved_at": template.approved_at.isoformat()},
    )
    db.session.commit()
    flash("Check Sheet template approved and available for execution.", "success")
    return redirect(url_for("commissioning.operations", project_id=project.id))


@commissioning_bp.post("/projects/<int:project_id>/checksheet-templates/<int:template_id>/revise")
@login_required
def revise_checksheet_template(project_id, template_id):
    _need(project_id, "checksheets.manage")
    project = get_project(project_id)
    previous = CommissioningCheckSheetTemplate.query.filter_by(
        id=template_id, company_name=project.company_name, project_id=project.id,
    ).with_for_update().first_or_404()
    if previous.status != "APPROVED":
        abort(409, description="Only an approved template can be revised.")
    latest = CommissioningCheckSheetTemplate.query.filter_by(
        company_name=project.company_name, project_id=project.id,
        template_code=previous.template_code,
    ).order_by(CommissioningCheckSheetTemplate.revision.desc()).first()
    if latest is None or latest.id != previous.id:
        abort(409, description="Create the next revision from the latest template revision.")
    revised = CommissioningCheckSheetTemplate(
        company_name=project.company_name, project_id=project.id,
        template_code=previous.template_code, title=previous.title,
        sheet_type=previous.sheet_type, discipline=previous.discipline,
        equipment_type=previous.equipment_type, revision=previous.revision + 1,
        supersedes_id=previous.id, acceptance_criteria=previous.acceptance_criteria,
        items_json=previous.items_json, status="DRAFT", created_by_id=current_user.id,
    )
    db.session.add(revised)
    db.session.flush()
    add_audit_event(
        project.company_name, "CommissioningCheckSheetTemplate", revised.id,
        "CHECKSHEET_TEMPLATE_REVISION_CREATED",
        before={"previous_id": previous.id, "revision": previous.revision},
        after={"template_code": revised.template_code, "revision": revised.revision,
               "supersedes_id": previous.id},
    )
    db.session.commit()
    flash("New Check Sheet template revision created as a draft.", "success")
    return redirect(url_for("commissioning.operations", project_id=project.id))


@commissioning_bp.route("/projects/<int:project_id>/checksheets/new", methods=["POST"])
@login_required
def create_checksheet(project_id):
    _need(project_id, "checksheets.create", "checksheets.manage")
    project = get_project(project_id)
    subsystem_id = _positive_int("subsystem_id")
    subsystem = CommissioningSubsystem.query.join(
        CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id,
    ).filter(
        CommissioningSubsystem.id == subsystem_id,
        CommissioningSubsystem.company_name == project.company_name,
        CommissioningSystem.project_id == project.id,
    ).first_or_404()
    sheet_type = _enum(CheckSheetType, _required("sheet_type", 30), "sheet type")
    template = None
    template_id = request.form.get("template_id", type=int)
    equipment = None
    equipment_id = request.form.get("equipment_id", type=int)
    if equipment_id is not None:
        equipment = CommissioningEquipment.query.filter_by(
            id=equipment_id, company_name=project.company_name,
            project_id=project.id, subsystem_id=subsystem.id,
        ).first_or_404()
    if template_id is not None:
        template = CommissioningCheckSheetTemplate.query.filter_by(
            id=template_id, company_name=project.company_name,
            project_id=project.id, status="APPROVED",
        ).first_or_404()
        if template.sheet_type != sheet_type:
            abort(400, description="Selected template type does not match the Check Sheet type.")
        if template.equipment_type:
            if equipment is None:
                abort(400, description="This template requires a matching equipment tag.")
            if equipment.equipment_type.strip().upper() != template.equipment_type:
                abort(400, description="Selected equipment type does not match the approved template.")
    discipline = (
        (request.form.get("discipline") or (template.discipline if template else "ANY"))
        .strip().upper() or "ANY"
    )
    if len(discipline) > 80:
        abort(400, description="Discipline is too long.")
    if template is not None and template.discipline != "ANY" and discipline != template.discipline:
        abort(400, description="Selected discipline does not match the approved template.")
    sheet_number = next_checksheet_number(project.company_name, project.project_code, sheet_type)
    template_snapshot = None
    if template is not None:
        template_snapshot = {
            "template_code": template.template_code,
            "title": template.title,
            "revision": template.revision,
            "sheet_type": template.sheet_type.value,
            "discipline": template.discipline,
            "equipment_type": template.equipment_type,
            "acceptance_criteria": template.acceptance_criteria,
            "items": template.items_json,
        }
    sheet = CheckSheet(
        company_name=project.company_name, project_id=project.id,
        system_id=subsystem.system_id, subsystem_id=subsystem.id,
        equipment_id=equipment.id if equipment else None,
        sheet_number=sheet_number, sheet_type=sheet_type, discipline=discipline,
        title=_required("title", 200), created_by_id=current_user.id,
        template_id=template.id if template else None,
        template_revision_snapshot=template.revision if template else None,
        template_title_snapshot=template.title if template else None,
        template_snapshot_json=template_snapshot,
        status=CheckSheetStatus.DRAFT,
    )
    db.session.add(sheet)
    db.session.flush()
    if template is not None:
        for item in template.items_json:
            db.session.add(CheckSheetItem(
                company_name=project.company_name, check_sheet_id=sheet.id,
                sequence=item["sequence"], description=item["description"],
                expected_result=item.get("expected_result"),
                acceptance_criteria=item.get("acceptance_criteria"),
                unit=item.get("unit"), measurement_type=item.get("measurement_type", "QUALITATIVE"),
                minimum_value=item.get("minimum_value"), maximum_value=item.get("maximum_value"),
                mandatory=item.get("mandatory", True), witness_required=item.get("witness_required", False),
            ))
    add_audit_event(
        project.company_name, "CheckSheet", sheet.id, "CHECKSHEET_CREATED",
        after={
            "sheet_number": sheet_number, "revision": 0,
            "template_id": template.id if template else None,
            "template_revision": template.revision if template else None,
            "items_created": len(template.items_json) if template else 0,
        },
    )
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
    revision_history = CheckSheetRevision.query.filter_by(
        company_name=sheet.company_name, sheet_number=sheet.sheet_number
    ).order_by(CheckSheetRevision.revision_number.asc()).all()
    return render_template("commissioning/checksheet_detail.html", sheet=sheet, items=items,
                           attachments=attachments, revision_history=revision_history,
                           results=list(ItemResultStatus),
                           can_manage=has_permission(sheet.project_id, "checksheets.create") or has_permission(sheet.project_id, "checksheets.manage"),
                           can_fill=has_permission(sheet.project_id, "checksheets.fill") or has_permission(sheet.project_id, "checksheets.manage"),
                           can_verify=has_permission(sheet.project_id, "checksheets.verify") or has_permission(sheet.project_id, "checksheets.manage"),
                           can_sign=has_permission(sheet.project_id, "checksheets.sign") or has_permission(sheet.project_id, "checksheets.manage"),
                           can_reject=has_permission(sheet.project_id, "checksheets.sign"),
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
    mandatory_values = request.form.getlist("mandatory")
    mandatory = "1" in mandatory_values if mandatory_values else True
    item = CheckSheetItem(
        company_name=sheet.company_name, check_sheet_id=sheet.id, sequence=sequence,
        description=_required("description"),
        expected_result=(request.form.get("expected_result") or "").strip() or None,
        acceptance_criteria=(request.form.get("acceptance_criteria") or "").strip() or None,
        unit=(request.form.get("unit") or "").strip()[:40] or None,
        mandatory=mandatory,
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
    old = {
        "result": item.result_status.value,
        "actual_result": item.actual_result,
        "measured_value": str(item.measured_value) if item.measured_value is not None else None,
        "remarks": item.remarks,
    }
    item.result_status = _enum(ItemResultStatus, _required("result_status", 20), "result")
    if item.measurement_type == "NUMERIC":
        raw_measurement = (request.form.get("measured_value") or "").strip()
        if item.result_status in (ItemResultStatus.OK, ItemResultStatus.NOK) and not raw_measurement:
            abort(400, description="A numeric measurement is required for OK/NOK items.")
        if raw_measurement:
            try:
                measured_value = Decimal(raw_measurement)
            except (InvalidOperation, TypeError, ValueError):
                abort(400, description="Measured value must be a valid number.")
            if not measured_value.is_finite() or len(raw_measurement) > 40:
                abort(400, description="Measured value must be a finite number.")
            item.measured_value = measured_value
            item.actual_result = format(measured_value, "f")
            if item.result_status == ItemResultStatus.OK:
                if item.minimum_value is not None and measured_value < item.minimum_value:
                    abort(400, description="Measured value is below the approved minimum; record NOK or correct the reading.")
                if item.maximum_value is not None and measured_value > item.maximum_value:
                    abort(400, description="Measured value exceeds the approved maximum; record NOK or correct the reading.")
        else:
            item.measured_value = None
            item.actual_result = None
    else:
        item.measured_value = None
        item.actual_result = (request.form.get("actual_result") or "").strip() or None
        if item.result_status in (ItemResultStatus.OK, ItemResultStatus.NOK) and not item.actual_result:
            abort(400, description="Actual result is required for OK/NOK items")
    # Any rework invalidates a previous QC verification.
    item.verified_by_id, item.verified_at = None, None
    item.remarks = (request.form.get("remarks") or "").strip() or None
    item.operator_id = current_user.id
    # Keep a rejected sheet in REJECTED while it is being corrected so the
    # explicit reissue action remains available after the rework is saved.
    if sheet.status != CheckSheetStatus.REJECTED:
        sheet.status = CheckSheetStatus.IN_PROGRESS
    add_audit_event(
        sheet.company_name, "CheckSheetItem", item.id, "CHECKSHEET_ITEM_RESULT",
        before=old,
        after={
            "result": item.result_status.value,
            "actual_result": item.actual_result,
            "measured_value": str(item.measured_value) if item.measured_value is not None else None,
            "measurement_type": item.measurement_type,
            "unit": item.unit,
            "remarks": item.remarks,
        },
    )
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
    issue_items = CheckSheetItem.query.filter_by(
        company_name=sheet.company_name, check_sheet_id=sheet.id,
    ).all()
    if not issue_items or not any(item.mandatory for item in issue_items):
        abort(409, description="A check sheet needs at least one mandatory item before issue")
    old_status = sheet.status
    if old_status == CheckSheetStatus.REJECTED:
        # Reissue starts a fresh approval cycle; prior signatures remain in the
        # append-only signature ledger but cannot satisfy this revision's sign-off.
        sheet.signed_by_client_id = None
        sheet.signed_by_contractor_id = None
        sheet.signed_at = None
        sheet.rejection_reason = None
    sheet.status, sheet.issued_by_id, sheet.issued_at = CheckSheetStatus.ISSUED, current_user.id, datetime.utcnow()
    add_audit_event(
        sheet.company_name, "CheckSheet", sheet.id, "CHECKSHEET_ISSUED",
        before={"status": old_status.value},
        after={"status": sheet.status.value, "issued_by_id": current_user.id},
    )
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
    mandatory_items = [item for item in items if item.mandatory]
    if (not mandatory_items
            or any(i.result_status == ItemResultStatus.PENDING for i in mandatory_items)
            or any(i.result_status == ItemResultStatus.NOK for i in items)):
        abort(409, description="All mandatory items must be completed and no item may retain an NOK result")
    review_items = [item for item in items if item.mandatory or item.result_status != ItemResultStatus.PENDING]
    if any(not item.verified_by_id or item.verified_by_id == item.operator_id for item in review_items):
        abort(409, description="Every completed mandatory/optional item requires independent QC verification before sign-off")
    witness_items = [item for item in items if item.witness_required and (item.mandatory or item.result_status != ItemResultStatus.PENDING)]
    if witness_items:
        for required_item in witness_items:
            points = WitnessPoint.query.filter_by(
                company_name=sheet.company_name, check_sheet_id=sheet.id,
                check_sheet_item_id=required_item.id,
            ).all()
            if not points or any(point.status != WitnessStatus.RELEASED for point in points):
                abort(409, description="Every required witness point must be released before sign-off")
    if has_permission(sheet.project_id, "checksheets.sign"):
        if sheet.signed_by_client_id is not None:
            abort(409, description="Client signature already recorded")
        if sheet.signed_by_contractor_id == current_user.id:
            abort(409, description="Two-party sign-off requires different users")
        sheet.signed_by_client_id = current_user.id
        sig_type = "CLIENT"
    else:
        if sheet.signed_by_contractor_id is not None:
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
    before = {
        "status": old.value,
        "signed_by_client_id": sheet.signed_by_client_id,
        "signed_by_contractor_id": sheet.signed_by_contractor_id,
    }
    sheet.status = CheckSheetStatus.REJECTED
    sheet.rejection_reason = reason
    # A rejection invalidates any signatures already collected in this approval
    # cycle. The immutable signature ledger retains the historical evidence.
    sheet.signed_by_client_id = None
    sheet.signed_by_contractor_id = None
    sheet.signed_at = None
    add_audit_event(
        sheet.company_name, "CheckSheet", sheet.id, "CHECKSHEET_REJECTED",
        before=before, after={"status": sheet.status.value, "reason": reason},
    )
    db.session.commit()
    return redirect(url_for("commissioning.checksheet_detail", sheet_id=sheet.id))

@commissioning_bp.post("/checksheets/<int:sheet_id>/revise")
@login_required
def revise_checksheet(sheet_id):
    previous = _sheet(sheet_id)
    previous = CheckSheet.query.filter_by(
        id=previous.id, company_name=current_user.company_name
    ).with_for_update().first_or_404()
    if not (has_permission(previous.project_id, "checksheets.manage") or has_permission(previous.project_id, "checksheets.create")):
        abort(403)
    if previous.status != CheckSheetStatus.SIGNED_OFF:
        abort(409, description="Only a signed-off sheet can be revised")
    latest = CheckSheet.query.filter_by(
        company_name=previous.company_name, sheet_number=previous.sheet_number
    ).order_by(CheckSheet.revision.desc()).first()
    if latest is None or latest.id != previous.id:
        abort(409, description="Create the next revision from the latest check sheet revision")
    revision_reason = _required("reason", 2000)
    revision_no = previous.revision + 1
    new_sheet = CheckSheet(
        company_name=previous.company_name, project_id=previous.project_id,
        system_id=previous.system_id, subsystem_id=previous.subsystem_id,
        equipment_id=previous.equipment_id, sheet_number=previous.sheet_number,
        sheet_type=previous.sheet_type, discipline=previous.discipline,
        revision=revision_no, supersedes_id=previous.id,
        template_id=previous.template_id,
        template_revision_snapshot=previous.template_revision_snapshot,
        template_title_snapshot=previous.template_title_snapshot,
        template_snapshot_json=previous.template_snapshot_json,
        sheet_weight=previous.sheet_weight, title=previous.title,
        status=CheckSheetStatus.DRAFT, created_by_id=current_user.id,
    )
    db.session.add(new_sheet)
    db.session.flush()
    for old in CheckSheetItem.query.filter_by(company_name=previous.company_name, check_sheet_id=previous.id).order_by(CheckSheetItem.sequence).all():
        db.session.add(CheckSheetItem(
            company_name=previous.company_name, check_sheet_id=new_sheet.id,
            sequence=old.sequence, description=old.description,
            expected_result=old.expected_result,
            acceptance_criteria=old.acceptance_criteria, unit=old.unit,
            mandatory=old.mandatory, witness_required=old.witness_required,
        ))
    db.session.add(CheckSheetRevision(
        company_name=previous.company_name, sheet_number=previous.sheet_number,
        revision_number=revision_no, previous_check_sheet_id=previous.id,
        new_check_sheet_id=new_sheet.id, revision_reason=revision_reason,
        created_by_id=current_user.id,
    ))
    add_audit_event(
        previous.company_name, "CheckSheet", new_sheet.id, "CHECKSHEET_REVISION_CREATED",
        before={"previous_id": previous.id},
        after={"revision": revision_no, "reason": revision_reason},
    )
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
    old_corrective_action = punch.corrective_action
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
    history_remarks = (request.form.get("remarks") or "").strip() or None
    audit_after = {"status": target.value}
    if target == PunchStatus.WAIVED:
        reason = _required("reason", 2000)
        punch.waiver_reason = reason
        punch.waived_by_id, punch.waived_at = current_user.id, datetime.utcnow()
        history_remarks = f"Waived: {reason}" + (f" · {history_remarks}" if history_remarks else "")
        audit_after["waiver_reason"] = reason
    if target == PunchStatus.CLOSED:
        corrective_action = _required("corrective_action", 2000)
        punch.corrective_action = corrective_action
        punch.closed_by_id, punch.closed_at = current_user.id, datetime.utcnow()
        history_remarks = f"Corrective action: {corrective_action}" + (f" · {history_remarks}" if history_remarks else "")
        audit_after["corrective_action"] = corrective_action
    if old == PunchStatus.CLOSED and target == PunchStatus.IN_PROGRESS:
        reopen_reason = _required("reason", 2000)
        previous_action = punch.corrective_action or "Not recorded"
        history_remarks = f"Reopened: {reopen_reason}. Previous corrective action: {previous_action}"
        punch.closed_by_id, punch.closed_at = None, None
        punch.corrective_action = None
        audit_after["reopen_reason"] = reopen_reason
        audit_after["previous_corrective_action"] = previous_action
    if target == PunchStatus.VERIFIED:
        punch.verified_by_id, punch.verified_at = current_user.id, datetime.utcnow()
    punch.status = target
    db.session.add(PunchHistory(company_name=punch.company_name, punch_item_id=punch.id,
        old_status=old, new_status=target, changed_by_id=current_user.id,
        remarks=history_remarks))
    add_audit_event(punch.company_name, "PunchItem", punch.id, "PUNCH_STATUS_CHANGED",
                    before={"status": old.value, "corrective_action": old_corrective_action},
                    after=audit_after)
    db.session.commit()
    return redirect(url_for("commissioning.operations", project_id=punch.project_id))


@commissioning_bp.get("/punch/<int:punch_id>/history")
@login_required
def punch_history(punch_id):
    punch = _punch(punch_id)
    history = PunchHistory.query.filter_by(
        company_name=punch.company_name, punch_item_id=punch.id,
    ).order_by(PunchHistory.created_at.asc(), PunchHistory.id.asc()).all()
    project = get_project(punch.project_id, punch.company_name)
    return render_template(
        "commissioning/punch_history.html", project=project,
        punch=punch, history=history,
    )


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


def _completion_certificate_snapshot(package, certificate_type, certificate_number, certificate_date):
    """Capture issue-time evidence; later register changes never rewrite a certificate."""
    project = CommissioningProject.query.filter_by(
        id=package.project_id, company_name=package.company_name,
    ).first_or_404()
    subsystem = CommissioningSubsystem.query.join(
        CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id,
    ).filter(
        CommissioningSubsystem.id == package.subsystem_id,
        CommissioningSubsystem.company_name == package.company_name,
        CommissioningSystem.project_id == package.project_id,
    ).first_or_404()

    all_sheets = CheckSheet.query.filter_by(
        company_name=package.company_name, project_id=package.project_id,
        subsystem_id=package.subsystem_id,
    ).order_by(CheckSheet.sheet_number, CheckSheet.revision.desc()).all()
    superseded_sheet_ids = {
        item.supersedes_id for item in all_sheets if item.supersedes_id is not None
    }
    sheets = [item for item in all_sheets if item.id not in superseded_sheet_ids]

    all_documents = CommissioningDocument.query.filter_by(
        company_name=package.company_name, project_id=package.project_id,
        subsystem_id=package.subsystem_id,
    ).order_by(CommissioningDocument.document_number,
               CommissioningDocument.revision_sequence.desc()).all()
    latest_documents = {}
    for item in all_documents:
        latest_documents.setdefault(item.document_number, item)
    documents = list(latest_documents.values())

    punches = PunchItem.query.filter_by(
        company_name=package.company_name, project_id=package.project_id,
        subsystem_id=package.subsystem_id,
    ).order_by(PunchItem.punch_number).all()
    witnesses = WitnessPoint.query.join(
        CheckSheet, CheckSheet.id == WitnessPoint.check_sheet_id,
    ).filter(
        WitnessPoint.company_name == package.company_name,
        WitnessPoint.project_id == package.project_id,
        CheckSheet.subsystem_id == package.subsystem_id,
    ).order_by(WitnessPoint.scheduled_at).all()
    tasks = CommissioningTask.query.filter_by(
        company_name=package.company_name, project_id=package.project_id,
        subsystem_id=package.subsystem_id,
    ).order_by(CommissioningTask.task_number).all()
    equipment = CommissioningEquipment.query.filter_by(
        company_name=package.company_name, project_id=package.project_id,
        subsystem_id=package.subsystem_id,
    ).order_by(CommissioningEquipment.tag_number).all()
    issuer = User.query.filter_by(
        id=current_user.id, company_name=package.company_name,
    ).first_or_404()

    readiness_policy, policy_errors = normalize_readiness_policy(project.readiness_policy_json)
    readiness_result = evaluate_subsystem_readiness(package.company_name, package.subsystem_id)
    readiness_gate = "MC" if certificate_type == "MC" else "RFC"
    blocking_categories = set(readiness_policy["punch_blocking_categories"][readiness_gate])
    open_critical = [
        item for item in punches
        if item.category.value in blocking_categories
        and item.status in (PunchStatus.OPEN, PunchStatus.IN_PROGRESS)
    ]
    legacy_open_ab = [
        item for item in punches
        if item.category in (PunchCategory.A, PunchCategory.B)
        and item.status in (PunchStatus.OPEN, PunchStatus.IN_PROGRESS)
    ]
    gate_issues = [
        {
            "code": issue.code,
            "severity": issue.severity,
            "message": issue.message,
            "entity_type": issue.entity_type,
            "entity_id": issue.entity_id,
            "gate": issue.gate,
        }
        for issue in readiness_result.issues if issue.gate == readiness_gate
    ]
    pending_holds = [
        item for item in witnesses
        if item.type == WitnessType.HOLD
        and item.status not in (WitnessStatus.RELEASED, WitnessStatus.CANCELLED)
    ]
    return {
        "certificate": {
            "type": certificate_type,
            "number": certificate_number,
            "date": certificate_date.isoformat(),
            "issued_by": issuer.full_name,
            "issued_by_id": issuer.id,
            "issued_at": datetime.utcnow().isoformat(),
        },
        "project": {
            "code": project.project_code, "name": project.name,
            "client": project.client, "contractor": project.contractor,
        },
        "subsystem": {
            "code": subsystem.subsystem_code, "name": subsystem.name,
        },
        "package": {"number": package.package_number},
        "readiness": {
            "current_check_sheets_total": len(sheets),
            "current_check_sheets_signed": sum(
                1 for item in sheets if item.status == CheckSheetStatus.SIGNED_OFF
            ),
            "open_category_a_b_punch": len(legacy_open_ab),
            "blocking_punch_count": len(open_critical),
            "gate": readiness_gate,
            "gate_ready": readiness_result.is_ready_for_mc if readiness_gate == "MC" else readiness_result.is_ready_for_rfc,
            "gate_issues": gate_issues,
            "readiness_policy": readiness_policy,
            "readiness_policy_errors": policy_errors,
            "current_documents_total": len(documents),
            "current_documents_approved": sum(
                1 for item in documents if item.status == DocumentStatus.APPROVED
            ),
            "pending_hold_points": len(pending_holds),
            "tasks_total": len(tasks),
            "tasks_completed": sum(
                1 for item in tasks if item.status == CommissioningTaskStatus.COMPLETED
            ),
        },
        "check_sheets": [{
            "number": item.sheet_number, "revision": item.revision,
            "title": item.title, "type": item.sheet_type.value,
            "status": item.status.value,
            "client_signatory_id": item.signed_by_client_id,
            "contractor_signatory_id": item.signed_by_contractor_id,
            "signed_at": item.signed_at.isoformat() if item.signed_at else None,
        } for item in sheets],
        "documents": [{
            "number": item.document_number, "revision": item.revision,
            "title": item.title, "type": item.document_type,
            "discipline": item.discipline, "status": item.status.value,
        } for item in documents],
        "punch_items": [{
            "number": item.punch_number, "category": item.category.value,
            "severity": item.severity.value, "status": item.status.value,
            "description": item.description,
            "corrective_action": item.corrective_action,
            "target_closure_date": item.target_closure_date.isoformat() if item.target_closure_date else None,
        } for item in punches],
        "witness_points": [{
            "type": item.type.value, "status": item.status.value,
            "scheduled_at": item.scheduled_at.isoformat(),
            "notified_party": item.notified_party,
        } for item in witnesses],
        "tasks": [{
            "number": item.task_number, "activity": item.activity_type.value,
            "title": item.title, "discipline": item.discipline,
            "status": item.status.value,
            "planned_finish": item.planned_finish_date.isoformat() if item.planned_finish_date else None,
            "actual_finish": item.actual_finish_date.isoformat() if item.actual_finish_date else None,
        } for item in tasks],
        "equipment": [{
            "tag": item.tag_number, "type": item.equipment_type,
            "description": item.description,
        } for item in equipment],
    }


@commissioning_bp.post("/handover/<int:package_id>/transition")
@login_required
def transition_handover(package_id):
    package = HandoverPackage.query.filter_by(id=package_id, company_name=current_user.company_name).first_or_404()
    _need(package.project_id, "handover.manage", "handover.accept", "project.manage")
    raw_target = _required("status", 30)
    if raw_target == "RF_CERTIFIED":  # Accept legacy clients during rollout.
        raw_target = "RFC_CERTIFIED"
    target = _enum(HandoverStatus, raw_target, "handover status")
    old = package.status
    subsystem_id = package.subsystem_id
    if target == HandoverStatus.MC_CERTIFIED:
        if not has_permission(package.project_id, "handover.manage") or old != HandoverStatus.DRAFT:
            abort(403)
        # Centralized readiness gate (Pre-Comm sheets + Punch A/B + Holds)
        require_ready_for_mc(package.company_name, subsystem_id)
        package.status, package.mc_issued_by_id = target, current_user.id
        package.mc_certificate_number = _required("certificate_number", 100)
        package.mc_certificate_date = _date("certificate_date") or date.today()
        if CommissioningCertificate.query.filter_by(
            company_name=package.company_name,
            certificate_number=package.mc_certificate_number,
        ).first():
            abort(409, description="Certificate number is already in use in this company.")
        certificate = CommissioningCertificate(
            company_name=package.company_name, project_id=package.project_id,
            subsystem_id=package.subsystem_id, package_id=package.id,
            certificate_type="MC", certificate_number=package.mc_certificate_number,
            certificate_date=package.mc_certificate_date, issued_by_id=current_user.id,
            snapshot_json=_completion_certificate_snapshot(
                package, "MC", package.mc_certificate_number, package.mc_certificate_date,
            ),
        )
        db.session.add(certificate)
        db.session.flush()
        add_audit_event(package.company_name, "CommissioningCertificate", certificate.id,
                        "COMPLETION_CERTIFICATE_ISSUED",
                        after={"type": "MC", "number": certificate.certificate_number,
                               "package_id": package.id})
    elif target == HandoverStatus.RFC_CERTIFIED:
        if not has_permission(package.project_id, "handover.manage") or old != HandoverStatus.MC_CERTIFIED:
            abort(403)
        require_ready_for_rfc(package.company_name, subsystem_id)
        package.status, package.rfc_issued_by_id = target, current_user.id
        package.rfc_certificate_number = _required("certificate_number", 100)
        package.rfc_certificate_date = _date("certificate_date") or date.today()
        if CommissioningCertificate.query.filter_by(
            company_name=package.company_name,
            certificate_number=package.rfc_certificate_number,
        ).first():
            abort(409, description="Certificate number is already in use in this company.")
        certificate = CommissioningCertificate(
            company_name=package.company_name, project_id=package.project_id,
            subsystem_id=package.subsystem_id, package_id=package.id,
            certificate_type="RFC", certificate_number=package.rfc_certificate_number,
            certificate_date=package.rfc_certificate_date, issued_by_id=current_user.id,
            snapshot_json=_completion_certificate_snapshot(
                package, "RFC", package.rfc_certificate_number, package.rfc_certificate_date,
            ),
        )
        db.session.add(certificate)
        db.session.flush()
        add_audit_event(package.company_name, "CommissioningCertificate", certificate.id,
                        "COMPLETION_CERTIFICATE_ISSUED",
                        after={"type": "RFC", "number": certificate.certificate_number,
                               "package_id": package.id})
    elif target == HandoverStatus.RFSU:
        if not has_permission(package.project_id, "handover.manage") or old != HandoverStatus.RFC_CERTIFIED:
            abort(403)
        require_ready_for_rfsu(package.company_name, subsystem_id)
        package.status = target
    elif target == HandoverStatus.ACCEPTED:
        if not has_permission(package.project_id, "handover.accept") or old != HandoverStatus.RFSU:
            abort(403)
        package.status, package.accepted_by_operations = target, True
        package.operations_accepted_by_id, package.operations_accepted_at = current_user.id, datetime.utcnow()
    elif target == HandoverStatus.REJECTED:
        if not has_permission(package.project_id, "handover.accept") or old not in (
            HandoverStatus.MC_CERTIFIED, HandoverStatus.RFC_CERTIFIED, HandoverStatus.RFSU):
            abort(403)
        package.status, package.rejection_reason = target, _required("reason", 2000)
    else:
        abort(400, description="Unsupported handover transition")
    add_audit_event(package.company_name, "HandoverPackage", package.id, "HANDOVER_STATUS_CHANGED",
                    before={"status": old.value}, after={"status": target.value})
    db.session.commit()
    return redirect(url_for("commissioning.operations", project_id=package.project_id))


@commissioning_bp.get("/handover/<int:package_id>/certificates/<string:certificate_type>")
@login_required
def completion_certificate(package_id, certificate_type):
    """Render the immutable issue-time MC/RFC certificate for print or PDF export."""
    package = HandoverPackage.query.filter_by(
        id=package_id, company_name=current_user.company_name,
    ).first_or_404()
    _need(package.project_id, "handover.view", "handover.manage",
          "handover.accept", "project.manage")
    certificate_type = certificate_type.upper()
    if certificate_type == "RF":  # Legacy certificate URL alias.
        certificate_type = "RFC"
    if certificate_type not in ("MC", "RFC"):
        abort(404)
    certificate = CommissioningCertificate.query.filter_by(
        company_name=package.company_name, project_id=package.project_id,
        package_id=package.id, certificate_type=certificate_type,
    ).first_or_404()
    return render_template(
        "commissioning/completion_certificate.html",
        project=get_project(package.project_id), package=package,
        certificate=certificate, snapshot=certificate.snapshot_json,
    )





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
    "CommissioningPreservationInspection": {
        "upload": ("preservation.execute", "preservation.manage"),
        "view": ("preservation.view", "preservation.execute", "preservation.manage", "project.manage"),
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
    if entity_type == "CommissioningPreservationInspection":
        entity = CommissioningPreservationInspection.query.filter_by(
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
        try:
            delete_commissioning_upload(metadata["storage_key"])
        except Exception:
            current_app.logger.exception("Failed to clean up evidence after database rollback")
        raise
    flash("Evidence uploaded successfully.", "success")
    if entity_type == "CheckSheet":
        return redirect(url_for("commissioning.checksheet_detail", sheet_id=entity_id))
    if entity_type == "CommissioningDocument":
        return redirect(url_for("commissioning.document_register", project_id=project_id))
    if entity_type == "CommissioningPreservationInspection":
        return redirect(url_for("commissioning.preservation_index", project_id=project_id))
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
    content = read_commissioning_upload(attachment.storage_key)
    response = send_file(BytesIO(content), mimetype=attachment.mime_type, as_attachment=True,
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



@commissioning_bp.post("/projects/<int:project_id>/dossier-requirements")
@login_required
def save_dossier_requirement(project_id):
    """Create, update or deactivate a project's mandatory dossier-index rule."""
    _need(project_id, "documents.manage", "project.manage")
    project = get_project(project_id)
    action = (request.form.get("action") or "save").strip().lower()
    raw_requirement_id = (request.form.get("requirement_id") or "").strip()
    requirement_id = None
    if raw_requirement_id:
        try:
            requirement_id = int(raw_requirement_id)
        except ValueError:
            abort(400, description="Invalid dossier requirement identifier.")

    requirement = None
    if requirement_id is not None:
        requirement = CommissioningDossierRequirement.query.filter_by(
            id=requirement_id, company_name=project.company_name,
            project_id=project.id,
        ).first_or_404()

    if action == "deactivate":
        if requirement is None:
            abort(400, description="A dossier requirement is required.")
        before = {
            "document_type": requirement.document_type,
            "discipline": requirement.discipline,
            "minimum_count": requirement.minimum_count,
            "require_approved": requirement.require_approved,
            "require_evidence": requirement.require_evidence,
            "is_active": requirement.is_active,
        }
        requirement.is_active = False
        add_audit_event(
            project.company_name, "CommissioningDossierRequirement",
            requirement.id, "DOSSIER_REQUIREMENT_DEACTIVATED",
            before=before, after={**before, "is_active": False},
        )
        db.session.commit()
        flash("Dossier index requirement deactivated.", "success")
        return redirect(url_for("commissioning.operations", project_id=project.id))

    if action != "save":
        abort(400, description="Invalid dossier requirement action.")

    document_type = _required("document_type", 80).upper()
    discipline = (request.form.get("discipline") or "ANY").strip().upper() or "ANY"
    if len(discipline) > 80:
        abort(400, description="Discipline is too long.")
    try:
        minimum_count = int(_required("minimum_count", 5))
    except ValueError:
        abort(400, description="Minimum count must be a whole number.")
    if not 1 <= minimum_count <= 1000:
        abort(400, description="Minimum count must be between 1 and 1000.")

    duplicate = CommissioningDossierRequirement.query.filter_by(
        company_name=project.company_name, project_id=project.id,
        document_type=document_type, discipline=discipline,
    )
    if requirement is not None:
        duplicate = duplicate.filter(CommissioningDossierRequirement.id != requirement.id)
    if duplicate.first():
        abort(409, description="A requirement already exists for this document type and discipline.")

    require_approved = request.form.get("require_approved") == "on"
    require_evidence = request.form.get("require_evidence") == "on"
    if requirement is None:
        requirement = CommissioningDossierRequirement(
            company_name=project.company_name, project_id=project.id,
            document_type=document_type, discipline=discipline,
            minimum_count=minimum_count, require_approved=require_approved,
            require_evidence=require_evidence, created_by_id=current_user.id,
        )
        db.session.add(requirement)
        db.session.flush()
        action_name = "DOSSIER_REQUIREMENT_CREATED"
        before = None
    else:
        before = {
            "document_type": requirement.document_type,
            "discipline": requirement.discipline,
            "minimum_count": requirement.minimum_count,
            "require_approved": requirement.require_approved,
            "require_evidence": requirement.require_evidence,
            "is_active": requirement.is_active,
        }
        requirement.document_type = document_type
        requirement.discipline = discipline
        requirement.minimum_count = minimum_count
        requirement.require_approved = require_approved
        requirement.require_evidence = require_evidence
        requirement.is_active = True
        action_name = "DOSSIER_REQUIREMENT_UPDATED"

    after = {
        "document_type": requirement.document_type,
        "discipline": requirement.discipline,
        "minimum_count": requirement.minimum_count,
        "require_approved": requirement.require_approved,
        "require_evidence": requirement.require_evidence,
        "is_active": requirement.is_active,
    }
    add_audit_event(
        project.company_name, "CommissioningDossierRequirement",
        requirement.id, action_name, before=before, after=after,
    )
    db.session.commit()
    flash("Dossier index requirement saved.", "success")
    return redirect(url_for("commissioning.operations", project_id=project.id))


@commissioning_bp.get("/projects/<int:project_id>/subsystems/<int:subsystem_id>/dossier")
@login_required
def subsystem_dossier(project_id, subsystem_id):
    """Consolidated, evidence-based readiness view and configurable document index."""
    _need(project_id, "structure.view", "handover.view", "handover.manage",
          "handover.accept", "reports.view", "dossier.view", "project.manage")
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
    ).order_by(
        CommissioningDocument.document_number,
        CommissioningDocument.revision_sequence.desc(),
    ).all()
    latest_documents = {}
    for document in documents_all:
        latest_documents.setdefault(document.document_number, document)
    documents = list(latest_documents.values())

    all_sheets = CheckSheet.query.filter_by(
        company_name=project.company_name, project_id=project.id,
        subsystem_id=subsystem.id,
    ).order_by(CheckSheet.sheet_number, CheckSheet.revision.desc()).all()
    superseded_sheet_ids = {
        item.supersedes_id for item in all_sheets if item.supersedes_id is not None
    }
    sheets = [item for item in all_sheets if item.id not in superseded_sheet_ids]
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
    readiness_policy, policy_errors = normalize_readiness_policy(project.readiness_policy_json)
    mc_blocking_categories = set(readiness_policy["punch_blocking_categories"]["MC"])
    open_critical_punches = [
        item for item in punches
        if item.category.value in mc_blocking_categories
        and item.status in (PunchStatus.OPEN, PunchStatus.IN_PROGRESS)
    ]
    open_other_punches = [
        item for item in punches
        if item.category.value not in mc_blocking_categories
        and item.status in (PunchStatus.OPEN, PunchStatus.IN_PROGRESS)
    ]
    pending_holds = [
        item for item in witnesses
        if "MC" in readiness_policy["hold_point_blocking_gates"]
        and item.type == WitnessType.HOLD
        and item.status not in (WitnessStatus.RELEASED, WitnessStatus.CANCELLED)
    ]
    incomplete_tasks = [
        item for item in tasks
        if item.status not in (CommissioningTaskStatus.COMPLETED, CommissioningTaskStatus.CANCELLED)
    ]

    dossier_requirements = CommissioningDossierRequirement.query.filter_by(
        company_name=project.company_name, project_id=project.id, is_active=True,
    ).order_by(
        CommissioningDossierRequirement.document_type,
        CommissioningDossierRequirement.discipline,
    ).all()
    document_requirement_results = []
    if dossier_requirements:
        for requirement in dossier_requirements:
            matching = [
                item for item in documents
                if item.document_type.strip().casefold() == requirement.document_type.strip().casefold()
                and (
                    requirement.discipline == "ANY"
                    or item.discipline.strip().casefold() == requirement.discipline.strip().casefold()
                )
            ]
            qualifying = [
                item for item in matching
                if (not requirement.require_approved or item.status == DocumentStatus.APPROVED)
                and (not requirement.require_evidence or bool(evidence_by_document.get(item.id)))
            ]
            approved_count = sum(1 for item in matching if item.status == DocumentStatus.APPROVED)
            evidence_count = sum(1 for item in matching if evidence_by_document.get(item.id))
            passed = len(qualifying) >= requirement.minimum_count
            discipline_label = "Any discipline" if requirement.discipline == "ANY" else requirement.discipline
            document_requirement_results.append({
                "name": requirement.document_type,
                "discipline": discipline_label,
                "minimum_count": requirement.minimum_count,
                "matching_count": len(matching),
                "qualifying_count": len(qualifying),
                "approved_count": approved_count,
                "evidence_count": evidence_count,
                "require_approved": requirement.require_approved,
                "require_evidence": requirement.require_evidence,
                "passed": passed,
                "detail": f"{len(qualifying)} of {requirement.minimum_count} required current documents qualify",
            })
        document_gate_passed = all(item["passed"] for item in document_requirement_results)
        document_gate_detail = "; ".join(
            f"{item['name']} ({item['discipline']}): {item['qualifying_count']}/{item['minimum_count']}"
            for item in document_requirement_results
        )
        document_gate_name = "Configured dossier index"
    else:
        # Preserve the existing safe default until a project manager configures
        # the mandatory index: at least one current document and all approved.
        document_gate_passed = bool(documents) and not unapproved_documents
        document_gate_detail = (
            f"{len(documents) - len(unapproved_documents)} of {len(documents)} current revisions approved"
            if documents else "No current engineering documents registered"
        )
        document_gate_name = "Current engineering documents"

    gates = [
        {"name": "Check Sheets", "passed": bool(sheets) and not unsigned_sheets,
         "detail": f"{len(sheets) - len(unsigned_sheets)} of {len(sheets)} current revisions signed off"},
        {"name": document_gate_name, "passed": document_gate_passed,
         "detail": document_gate_detail},
        {"name": "Configured MC Punch categories", "passed": not open_critical_punches,
         "detail": f"{len(open_critical_punches)} open blocking Punch items"},
        {"name": "MC Hold points", "passed": not pending_holds,
         "detail": f"{len(pending_holds)} blocking Hold points"},
        {"name": "Readiness policy", "passed": not policy_errors,
         "detail": "; ".join(policy_errors) if policy_errors else "Valid project readiness policy"},
    ]
    readiness_passed = all(item["passed"] for item in gates)
    dossier_revisions = CommissioningDossierRevision.query.filter_by(
        company_name=project.company_name, project_id=project.id, subsystem_id=subsystem.id,
    ).order_by(CommissioningDossierRevision.revision_number.desc()).all()
    dossier_reviews = CommissioningDossierReview.query.filter(
        CommissioningDossierReview.company_name == project.company_name,
        CommissioningDossierReview.dossier_revision_id.in_([item.id for item in dossier_revisions] or [-1]),
    ).order_by(CommissioningDossierReview.decided_at.desc()).all()
    dossier_reviews_by_revision = {}
    for review in dossier_reviews:
        dossier_reviews_by_revision.setdefault(review.dossier_revision_id, []).append(review)
    return render_template(
        "commissioning/subsystem_dossier.html", project=project, subsystem=subsystem,
        documents=documents, evidence_by_document=evidence_by_document,
        sheets=sheets, punches=punches, witnesses=witnesses, tasks=tasks,
        equipment=equipment, gates=gates, readiness_passed=readiness_passed,
        unsigned_sheets=unsigned_sheets, unapproved_documents=unapproved_documents,
        open_critical_punches=open_critical_punches, open_other_punches=open_other_punches,
        pending_holds=pending_holds, incomplete_tasks=incomplete_tasks,
        dossier_requirements=dossier_requirements,
        document_requirement_results=document_requirement_results,
        dossier_revisions=dossier_revisions,
        dossier_reviews_by_revision=dossier_reviews_by_revision,
        can_manage_dossiers=any(has_permission(project.id, p) for p in ("dossier.manage", "project.manage")),
        can_review_dossiers=any(has_permission(project.id, p) for p in ("dossier.review", "project.manage")),
        can_issue_dossiers=any(has_permission(project.id, p) for p in ("dossier.issue", "project.manage")),
    )


@commissioning_bp.post("/projects/<int:project_id>/subsystems/<int:subsystem_id>/dossiers")
@login_required
def create_dossier_revision(project_id, subsystem_id):
    """Create a frozen point-in-time dossier draft for a project subsystem."""
    _need(project_id, "dossier.manage", "project.manage")
    project = get_project(project_id)
    subsystem = CommissioningSubsystem.query.join(
        CommissioningSystem, CommissioningSystem.id == CommissioningSubsystem.system_id,
    ).filter(
        CommissioningSubsystem.id == subsystem_id,
        CommissioningSubsystem.company_name == project.company_name,
        CommissioningSystem.project_id == project.id,
    ).first_or_404()
    previous = CommissioningDossierRevision.query.filter_by(
        company_name=project.company_name, project_id=project.id, subsystem_id=subsystem.id,
    ).order_by(CommissioningDossierRevision.revision_number.desc()).first()
    if previous and previous.status not in (
        DossierRevisionStatus.ISSUED, DossierRevisionStatus.REJECTED,
    ):
        abort(409, description="Complete or reject the current dossier revision before creating another.")
    revision_number = previous.revision_number + 1 if previous else 1
    snapshot, _ = build_subsystem_dossier_snapshot(
        project.company_name, project.id, subsystem.id,
    )
    snapshot["export_classification"] = "CONTROLLED_DOSSIER_REVISION"
    snapshot["notice"] = (
        "Controlled point-in-time OPERA dossier revision. Approval and issue status "
        "are maintained in the dossier revision register."
    )
    snapshot["dossier_revision"] = {"revision_number": revision_number}
    revision = CommissioningDossierRevision(
        company_name=project.company_name, project_id=project.id,
        subsystem_id=subsystem.id, revision_number=revision_number,
        supersedes_id=previous.id if previous else None,
        title=f"{subsystem.subsystem_code} Completion Dossier",
        status=DossierRevisionStatus.DRAFT, snapshot_json=snapshot,
        snapshot_sha256=_dossier_snapshot_digest(snapshot),
        created_by_id=current_user.id,
    )
    db.session.add(revision)
    db.session.flush()
    add_audit_event(
        project.company_name, "CommissioningDossierRevision", revision.id,
        "DOSSIER_REVISION_CREATED",
        after={"revision_number": revision_number, "subsystem_id": subsystem.id,
               "snapshot_sha256": revision.snapshot_sha256},
    )
    db.session.commit()
    flash(f"Dossier revision {revision_number} created as a frozen draft.", "success")
    return redirect(url_for(
        "commissioning.subsystem_dossier", project_id=project.id, subsystem_id=subsystem.id,
    ))


@commissioning_bp.post("/dossiers/<int:dossier_id>/submit")
@login_required
def submit_dossier_revision(dossier_id):
    revision = CommissioningDossierRevision.query.filter_by(
        id=dossier_id, company_name=current_user.company_name,
    ).first_or_404()
    _need(revision.project_id, "dossier.manage", "project.manage")
    if revision.status not in (DossierRevisionStatus.DRAFT, DossierRevisionStatus.REJECTED):
        abort(409, description="Only a draft or rejected dossier revision can be submitted.")
    if _dossier_snapshot_digest(revision.snapshot_json) != revision.snapshot_sha256:
        abort(409, description="The dossier snapshot failed its integrity check.")
    before = {"status": revision.status.value}
    revision.status = DossierRevisionStatus.IN_REVIEW
    revision.submitted_at = datetime.utcnow()
    revision.rejection_reason = None
    add_audit_event(
        revision.company_name, "CommissioningDossierRevision", revision.id,
        "DOSSIER_REVISION_SUBMITTED", before=before,
        after={"status": revision.status.value},
    )
    db.session.commit()
    flash("Dossier revision submitted for independent review.", "success")
    return redirect(url_for(
        "commissioning.subsystem_dossier", project_id=revision.project_id,
        subsystem_id=revision.subsystem_id,
    ))


@commissioning_bp.post("/dossiers/<int:dossier_id>/decision")
@login_required
def decide_dossier_revision(dossier_id):
    revision = CommissioningDossierRevision.query.filter_by(
        id=dossier_id, company_name=current_user.company_name,
    ).first_or_404()
    _need(revision.project_id, "dossier.review", "project.manage")
    if revision.status != DossierRevisionStatus.IN_REVIEW:
        abort(409, description="Only a dossier revision in review can receive a decision.")
    if revision.created_by_id == current_user.id:
        abort(403, description="The dossier author cannot review their own revision.")
    decision = (request.form.get("decision") or "").strip().upper()
    comments = (request.form.get("comments") or "").strip()[:3000]
    if decision not in ("APPROVE", "REJECT"):
        abort(400, description="Decision must be APPROVE or REJECT.")
    if decision == "REJECT" and not comments:
        abort(400, description="A reason is required when rejecting a dossier revision.")
    if _dossier_snapshot_digest(revision.snapshot_json) != revision.snapshot_sha256:
        abort(409, description="The dossier snapshot failed its integrity check.")
    if decision == "APPROVE":
        if not revision.snapshot_json.get("readiness", {}).get("mc_dossier_checks_passed"):
            abort(409, description="Dossier completeness/readiness checks must pass before approval.")
        _dossier_revision_attachments(revision)
        revision.status = DossierRevisionStatus.APPROVED
        revision.approved_by_id = current_user.id
        revision.approved_at = datetime.utcnow()
        review_decision = DossierReviewDecision.APPROVED
    else:
        revision.status = DossierRevisionStatus.REJECTED
        revision.rejection_reason = comments
        review_decision = DossierReviewDecision.REJECTED
    review = CommissioningDossierReview(
        company_name=revision.company_name, dossier_revision_id=revision.id,
        reviewer_id=current_user.id, decision=review_decision, comments=comments or None,
    )
    db.session.add(review)
    add_audit_event(
        revision.company_name, "CommissioningDossierRevision", revision.id,
        "DOSSIER_REVISION_REVIEWED",
        before={"status": DossierRevisionStatus.IN_REVIEW.value},
        after={"status": revision.status.value, "decision": decision,
               "reviewer_id": current_user.id, "comments": comments or None},
    )
    db.session.commit()
    flash("Dossier revision decision recorded.", "success")
    return redirect(url_for(
        "commissioning.subsystem_dossier", project_id=revision.project_id,
        subsystem_id=revision.subsystem_id,
    ))


@commissioning_bp.post("/dossiers/<int:dossier_id>/issue")
@login_required
def issue_dossier_revision(dossier_id):
    revision = CommissioningDossierRevision.query.filter_by(
        id=dossier_id, company_name=current_user.company_name,
    ).first_or_404()
    _need(revision.project_id, "dossier.issue", "project.manage")
    if revision.status != DossierRevisionStatus.APPROVED:
        abort(409, description="Only an approved dossier revision can be issued.")
    if current_user.id in (revision.created_by_id, revision.approved_by_id):
        abort(403, description="The dossier author and approver cannot issue the same revision.")
    if _dossier_snapshot_digest(revision.snapshot_json) != revision.snapshot_sha256:
        abort(409, description="The dossier snapshot failed its integrity check.")
    if not revision.snapshot_json.get("readiness", {}).get("mc_dossier_checks_passed"):
        abort(409, description="The approved dossier no longer satisfies its recorded readiness checks.")
    _dossier_revision_attachments(revision)
    before = {"status": revision.status.value}
    revision.status = DossierRevisionStatus.ISSUED
    revision.issued_by_id = current_user.id
    revision.issued_at = datetime.utcnow()
    add_audit_event(
        revision.company_name, "CommissioningDossierRevision", revision.id,
        "DOSSIER_REVISION_ISSUED", before=before,
        after={"status": revision.status.value, "issued_by_id": current_user.id,
               "issued_at": revision.issued_at.isoformat(),
               "snapshot_sha256": revision.snapshot_sha256},
    )
    db.session.commit()
    flash(f"Dossier revision {revision.revision_number} issued.", "success")
    return redirect(url_for(
        "commissioning.subsystem_dossier", project_id=revision.project_id,
        subsystem_id=revision.subsystem_id,
    ))


@commissioning_bp.get("/dossiers/<int:dossier_id>/export.pdf")
@login_required
def issued_dossier_pdf_export(dossier_id):
    revision, snapshot, _attachments = _require_issued_dossier(dossier_id)
    payload = render_subsystem_dossier_pdf(snapshot)
    response = send_file(
        BytesIO(payload), mimetype="application/pdf", as_attachment=True,
        download_name=f"OPERA-dossier-R{revision.revision_number}.pdf", max_age=0,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@commissioning_bp.get("/dossiers/<int:dossier_id>/export.zip")
@login_required
def issued_dossier_zip_export(dossier_id):
    revision, snapshot, attachments = _require_issued_dossier(dossier_id)
    payload = render_subsystem_dossier_zip(snapshot, attachments)
    response = send_file(
        BytesIO(payload), mimetype="application/zip", as_attachment=True,
        download_name=f"OPERA-dossier-R{revision.revision_number}-evidence.zip", max_age=0,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


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



@commissioning_bp.get("/projects/<int:project_id>/subsystems/<int:subsystem_id>/dossier/export.pdf")
@login_required
def subsystem_dossier_pdf_export(project_id, subsystem_id):
    """Download a point-in-time, explicitly uncontrolled subsystem dossier PDF."""
    _need(project_id, "structure.view", "handover.view", "handover.manage",
          "handover.accept", "reports.view", "project.manage")
    snapshot, _attachments = build_subsystem_dossier_snapshot(
        current_user.company_name, project_id, subsystem_id,
    )
    payload = render_subsystem_dossier_pdf(snapshot)
    response = send_file(
        BytesIO(payload), mimetype="application/pdf", as_attachment=True,
        download_name="OPERA-subsystem-dossier.pdf", max_age=0,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@commissioning_bp.get("/projects/<int:project_id>/subsystems/<int:subsystem_id>/dossier/export.zip")
@login_required
def subsystem_dossier_zip_export(project_id, subsystem_id):
    """Download a PDF, JSON manifest and checksum-verified evidence bundle."""
    _need(project_id, "structure.view", "handover.view", "handover.manage",
          "handover.accept", "reports.view", "project.manage")
    snapshot, attachments = build_subsystem_dossier_snapshot(
        current_user.company_name, project_id, subsystem_id,
    )
    payload = render_subsystem_dossier_zip(snapshot, attachments)
    response = send_file(
        BytesIO(payload), mimetype="application/zip", as_attachment=True,
        download_name="OPERA-subsystem-dossier-evidence.zip", max_age=0,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response
