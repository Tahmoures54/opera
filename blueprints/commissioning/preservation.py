"""Project-scoped equipment preservation plans, inspections and compliance reporting."""
import csv
from datetime import date, timedelta
from io import BytesIO, StringIO

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from blueprints.commissioning import commissioning_bp
from extensions import db
from models import User
from models_commissioning import (
    CommissioningAttachment,
    CommissioningEquipment,
    CommissioningPreservationInspection,
    CommissioningPreservationPlan,
)
from services.commissioning_access import add_audit_event, get_project, has_permission


def _require(project_id, *permissions):
    project = get_project(project_id)
    if not any(has_permission(project_id, permission) for permission in permissions):
        abort(403)
    return project


def _required(name, limit=200):
    value = (request.form.get(name) or "").strip()
    if not value:
        abort(400, description=f"{name.replace('_', ' ').title()} is required.")
    if len(value) > limit:
        abort(400, description=f"{name.replace('_', ' ').title()} is too long.")
    return value


def _parse_date(name):
    value = _required(name, 10)
    try:
        return date.fromisoformat(value)
    except ValueError:
        abort(400, description=f"{name.replace('_', ' ').title()} must be YYYY-MM-DD.")


def _plan_snapshot(plan):
    return {
        "plan_number": plan.plan_number,
        "equipment_id": plan.equipment_id,
        "activity": plan.activity,
        "procedure_reference": plan.procedure_reference,
        "procedure_revision": plan.procedure_revision,
        "interval_days": plan.interval_days,
        "next_due_date": plan.next_due_date.isoformat() if plan.next_due_date else None,
        "status": plan.status,
    }


def _due_status(plan, today):
    if plan.status in ("SUSPENDED", "CLOSED", "ACTION_REQUIRED"):
        return plan.status
    if plan.next_due_date < today:
        return "OVERDUE"
    if plan.next_due_date <= today + timedelta(days=7):
        return "DUE_SOON"
    return "ON_SCHEDULE"


_PRESERVATION_REPORT_FILTERS = {
    "ALL", "OVERDUE", "DUE_SOON", "ACTION_REQUIRED", "ACTIVE", "SUSPENDED", "CLOSED",
}


def _preservation_report_data(project, today, status_filter="ALL", equipment_id=None):
    query = CommissioningPreservationPlan.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    )
    if equipment_id is not None:
        query = query.filter_by(equipment_id=equipment_id)
    plans = query.order_by(
        CommissioningPreservationPlan.next_due_date,
        CommissioningPreservationPlan.plan_number,
    ).all()
    equipment = CommissioningEquipment.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).order_by(CommissioningEquipment.tag_number).all()
    equipment_by_id = {item.id: item for item in equipment}
    user_ids = {plan.assigned_to_id for plan in plans if plan.assigned_to_id is not None}
    users = User.query.filter(
        User.company_name == project.company_name, User.id.in_(user_ids or [-1]),
    ).all()
    user_by_id = {user.id: user for user in users}
    rows = []
    for plan in plans:
        due_status = _due_status(plan, today)
        if status_filter != "ALL" and status_filter != due_status and status_filter != plan.status:
            continue
        latest = plan.inspections[0] if plan.inspections else None
        rows.append({
            "plan": plan,
            "equipment": equipment_by_id.get(plan.equipment_id),
            "due_status": due_status,
            "last_inspection": latest,
            "assigned_user": user_by_id.get(plan.assigned_to_id),
        })
    counts = {
        "total": len(rows),
        "overdue": sum(1 for row in rows if row["due_status"] == "OVERDUE"),
        "due_soon": sum(1 for row in rows if row["due_status"] == "DUE_SOON"),
        "action_required": sum(1 for row in rows if row["due_status"] == "ACTION_REQUIRED"),
        "suspended": sum(1 for row in rows if row["due_status"] == "SUSPENDED"),
        "closed": sum(1 for row in rows if row["due_status"] == "CLOSED"),
        "on_schedule": sum(1 for row in rows if row["due_status"] == "ON_SCHEDULE"),
    }
    return rows, counts, equipment, status_filter, equipment_id


def _csv_safe(value):
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


@commissioning_bp.get("/projects/<int:project_id>/preservation")
@login_required
def preservation_index(project_id):
    project = _require(project_id, "preservation.view", "preservation.manage", "project.manage")
    plans = CommissioningPreservationPlan.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).order_by(
        CommissioningPreservationPlan.next_due_date,
        CommissioningPreservationPlan.plan_number,
    ).all()
    today = date.today()
    plan_rows = [{"plan": plan, "due_status": _due_status(plan, today)} for plan in plans]
    equipment = CommissioningEquipment.query.filter_by(
        company_name=project.company_name, project_id=project.id,
    ).order_by(CommissioningEquipment.tag_number).all()
    users = User.query.filter_by(company_name=project.company_name).order_by(User.full_name).all()
    equipment_by_id = {item.id: item for item in equipment}
    user_by_id = {item.id: item for item in users}
    inspection_ids = [inspection.id for plan in plans for inspection in plan.inspections]
    attachments = CommissioningAttachment.query.filter(
        CommissioningAttachment.company_name == project.company_name,
        CommissioningAttachment.entity_type == "CommissioningPreservationInspection",
        CommissioningAttachment.entity_id.in_(inspection_ids or [-1]),
    ).all()
    attachments_by_inspection = {}
    for attachment in attachments:
        attachments_by_inspection.setdefault(attachment.entity_id, []).append(attachment)
    counts = {
        "total": len(plans),
        "overdue": sum(1 for row in plan_rows if row["due_status"] == "OVERDUE"),
        "due_soon": sum(1 for row in plan_rows if row["due_status"] == "DUE_SOON"),
        "action_required": sum(1 for row in plan_rows if row["due_status"] == "ACTION_REQUIRED"),
    }
    return render_template(
        "commissioning/preservation.html",
        project=project, plan_rows=plan_rows, equipment=equipment, users=users,
        equipment_by_id=equipment_by_id, user_by_id=user_by_id,
        attachments_by_inspection=attachments_by_inspection,
        counts=counts, today=today, can_manage=has_permission(project.id, "preservation.manage"),
        can_execute=any(has_permission(project.id, p) for p in ("preservation.execute", "preservation.manage")),
    )


@commissioning_bp.get("/projects/<int:project_id>/preservation/report")
@login_required
def preservation_report(project_id):
    project = _require(project_id, "preservation.view", "preservation.manage", "project.manage")
    status_filter = (request.args.get("status") or "ALL").strip().upper()
    if status_filter not in _PRESERVATION_REPORT_FILTERS:
        abort(400, description="Invalid preservation report status filter.")
    equipment_id = request.args.get("equipment_id", type=int)
    if request.args.get("equipment_id") and equipment_id is None:
        abort(400, description="Equipment filter must be a numeric equipment ID.")
    if equipment_id is not None:
        CommissioningEquipment.query.filter_by(
            id=equipment_id, company_name=project.company_name, project_id=project.id,
        ).first_or_404()
    rows, counts, equipment, status_filter, equipment_id = _preservation_report_data(
        project, date.today(), status_filter, equipment_id,
    )
    return render_template(
        "commissioning/preservation_report.html",
        project=project, rows=rows, counts=counts, equipment=equipment,
        status_filter=status_filter, selected_equipment_id=equipment_id,
        today=date.today(), filters=sorted(_PRESERVATION_REPORT_FILTERS),
    )


@commissioning_bp.get("/projects/<int:project_id>/preservation/report.csv")
@login_required
def preservation_report_csv(project_id):
    project = _require(project_id, "preservation.view", "preservation.manage", "project.manage")
    status_filter = (request.args.get("status") or "ALL").strip().upper()
    if status_filter not in _PRESERVATION_REPORT_FILTERS:
        abort(400, description="Invalid preservation report status filter.")
    equipment_id = request.args.get("equipment_id", type=int)
    if request.args.get("equipment_id") and equipment_id is None:
        abort(400, description="Equipment filter must be a numeric equipment ID.")
    if equipment_id is not None:
        CommissioningEquipment.query.filter_by(
            id=equipment_id, company_name=project.company_name, project_id=project.id,
        ).first_or_404()
    rows, _counts, _equipment, _status_filter, _equipment_id = _preservation_report_data(
        project, date.today(), status_filter, equipment_id,
    )
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "Project", "Plan Number", "Equipment Tag", "Activity", "Procedure Reference",
        "Procedure Revision", "Interval Days", "Last Inspection", "Last Result",
        "Next Due Date", "Due Status", "Responsible Company", "Assigned User",
        "Latest Findings", "Corrective Action",
    ])
    for row in rows:
        plan = row["plan"]
        latest = row["last_inspection"]
        equipment_item = row["equipment"]
        assigned_user = row["assigned_user"]
        values = [
            project.project_code, plan.plan_number,
            equipment_item.tag_number if equipment_item else "Equipment unavailable",
            plan.activity, plan.procedure_reference, plan.procedure_revision,
            plan.interval_days,
            latest.performed_at.isoformat() if latest else "",
            latest.result if latest else "",
            plan.next_due_date.isoformat(), row["due_status"],
            plan.responsible_company or "",
            assigned_user.full_name if assigned_user else "",
            latest.findings if latest else "",
            latest.corrective_action if latest else "",
        ]
        writer.writerow([_csv_safe(value) for value in values])
    payload = BytesIO(output.getvalue().encode("utf-8-sig"))
    response = send_file(
        payload, mimetype="text/csv; charset=utf-8", as_attachment=True,
        download_name=f"{project.project_code}-preservation-{date.today().isoformat()}.csv",
        max_age=0,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@commissioning_bp.post("/projects/<int:project_id>/preservation-plans")
@login_required
def save_preservation_plan(project_id):
    project = _require(project_id, "preservation.manage", "project.manage")
    equipment_id = request.form.get("equipment_id", type=int)
    equipment = CommissioningEquipment.query.filter_by(
        id=equipment_id, company_name=project.company_name, project_id=project.id,
    ).first_or_404()
    plan_number = _required("plan_number", 80)
    activity = _required("activity", 200)
    procedure_reference = _required("procedure_reference", 150)
    procedure_revision = _required("procedure_revision", 50)
    try:
        interval_days = int(_required("interval_days", 5))
    except ValueError:
        abort(400, description="Interval must be a whole number of days.")
    if interval_days < 1:
        abort(400, description="Interval must be a positive number of days.")
    next_due_date = _parse_date("next_due_date")
    assigned_to_id = request.form.get("assigned_to_id", type=int)
    if assigned_to_id is not None and not User.query.filter_by(
        id=assigned_to_id, company_name=project.company_name,
    ).first():
        abort(400, description="Assigned user must belong to this company.")
    duplicate = CommissioningPreservationPlan.query.filter_by(
        company_name=project.company_name, project_id=project.id, plan_number=plan_number,
    ).first()
    if duplicate:
        abort(409, description="Preservation plan number already exists in this project.")

    plan = CommissioningPreservationPlan(
        company_name=project.company_name, project_id=project.id,
        equipment_id=equipment.id, plan_number=plan_number, activity=activity,
        procedure_reference=procedure_reference, procedure_revision=procedure_revision,
        interval_days=interval_days, next_due_date=next_due_date,
        responsible_company=(request.form.get("responsible_company") or "").strip()[:150] or None,
        assigned_to_id=assigned_to_id, status="ACTIVE",
        notes=(request.form.get("notes") or "").strip() or None,
        created_by_id=current_user.id,
    )
    db.session.add(plan)
    db.session.flush()
    add_audit_event(
        project.company_name, "CommissioningPreservationPlan", plan.id,
        "PRESERVATION_PLAN_CREATED", after=_plan_snapshot(plan),
    )
    db.session.commit()
    flash("Preservation plan created.", "success")
    return redirect(url_for("commissioning.preservation_index", project_id=project.id))


@commissioning_bp.post("/projects/<int:project_id>/preservation-plans/<int:plan_id>/inspect")
@login_required
def record_preservation_inspection(project_id, plan_id):
    project = _require(project_id, "preservation.execute", "preservation.manage", "project.manage")
    plan = CommissioningPreservationPlan.query.filter_by(
        id=plan_id, company_name=project.company_name, project_id=project.id,
    ).first_or_404()
    if plan.status in ("SUSPENDED", "CLOSED"):
        abort(409, description="Suspended or closed preservation plans cannot be inspected.")
    performed_at = _parse_date("performed_at")
    if performed_at > date.today():
        abort(400, description="Inspection date cannot be in the future.")
    if plan.last_performed_at and performed_at < plan.last_performed_at:
        abort(409, description="Inspection date cannot precede the latest recorded inspection.")
    result = _required("result", 30).upper()
    if result not in ("COMPLIANT", "NON_COMPLIANT", "NOT_APPLICABLE"):
        abort(400, description="Invalid preservation inspection result.")
    findings = (request.form.get("findings") or "").strip() or None
    environmental_conditions = (request.form.get("environmental_conditions") or "").strip() or None
    corrective_action = (request.form.get("corrective_action") or "").strip() or None
    if result == "NON_COMPLIANT" and not corrective_action:
        abort(400, description="Corrective action is required for a non-compliant inspection.")

    before = _plan_snapshot(plan)
    next_due_after = plan.next_due_date
    inspection = CommissioningPreservationInspection(
        company_name=project.company_name, project_id=project.id, plan_id=plan.id,
        performed_at=performed_at, result=result, findings=findings,
        environmental_conditions=environmental_conditions,
        corrective_action=corrective_action,
        procedure_reference_snapshot=plan.procedure_reference,
        procedure_revision_snapshot=plan.procedure_revision,
        interval_days_snapshot=plan.interval_days,
        performed_by_id=current_user.id,
    )
    if result == "COMPLIANT":
        plan.last_performed_at = performed_at
        plan.next_due_date = performed_at + timedelta(days=plan.interval_days)
        plan.status = "ACTIVE"
        next_due_after = plan.next_due_date
    elif result == "NON_COMPLIANT":
        plan.last_performed_at = performed_at
        plan.next_due_date = performed_at
        plan.status = "ACTION_REQUIRED"
        next_due_after = plan.next_due_date
    inspection.next_due_date_after = next_due_after
    db.session.add(inspection)
    db.session.flush()
    add_audit_event(
        project.company_name, "CommissioningPreservationInspection", inspection.id,
        "PRESERVATION_INSPECTION_RECORDED",
        after={
            "plan_id": plan.id, "plan_number": plan.plan_number,
            "performed_at": performed_at.isoformat(), "result": result,
            "findings": findings, "environmental_conditions": environmental_conditions,
            "corrective_action": corrective_action,
            "procedure_reference": inspection.procedure_reference_snapshot,
            "procedure_revision": inspection.procedure_revision_snapshot,
            "interval_days": inspection.interval_days_snapshot,
            "next_due_date_after": next_due_after.isoformat() if next_due_after else None,
        },
    )
    add_audit_event(
        project.company_name, "CommissioningPreservationPlan", plan.id,
        "PRESERVATION_PLAN_STATUS_UPDATED",
        before=before, after=_plan_snapshot(plan),
    )
    db.session.commit()
    flash("Preservation inspection recorded.", "success")
    return redirect(url_for("commissioning.preservation_index", project_id=project.id))


@commissioning_bp.post("/projects/<int:project_id>/preservation-plans/<int:plan_id>/status")
@login_required
def update_preservation_plan_status(project_id, plan_id):
    project = _require(project_id, "preservation.manage", "project.manage")
    plan = CommissioningPreservationPlan.query.filter_by(
        id=plan_id, company_name=project.company_name, project_id=project.id,
    ).first_or_404()
    new_status = _required("status", 30).upper()
    if new_status not in ("ACTIVE", "SUSPENDED", "CLOSED"):
        abort(400, description="Invalid preservation plan status.")
    if plan.status == "CLOSED" and new_status != "CLOSED":
        abort(409, description="Closed preservation plans cannot be reactivated.")
    if plan.status == "ACTION_REQUIRED" and new_status in ("ACTIVE", "SUSPENDED"):
        abort(409, description="Record a compliant inspection before reactivating or suspending an action-required plan; it may only be closed.")
    before = _plan_snapshot(plan)
    plan.status = new_status
    add_audit_event(
        project.company_name, "CommissioningPreservationPlan", plan.id,
        "PRESERVATION_PLAN_STATUS_UPDATED", before=before, after=_plan_snapshot(plan),
    )
    db.session.commit()
    flash("Preservation plan status updated.", "success")
    return redirect(url_for("commissioning.preservation_index", project_id=project.id))
