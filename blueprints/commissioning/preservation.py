"""Project-scoped equipment preservation plans and inspection workflow."""
from datetime import date, timedelta

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from blueprints.commissioning import commissioning_bp
from extensions import db
from models import User
from models_commissioning import (
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
    users = User.query.filter_by(company_name=project.company_name, is_active=True).order_by(User.username).all()
    counts = {
        "total": len(plans),
        "overdue": sum(1 for row in plan_rows if row["due_status"] == "OVERDUE"),
        "due_soon": sum(1 for row in plan_rows if row["due_status"] == "DUE_SOON"),
        "action_required": sum(1 for row in plan_rows if row["due_status"] == "ACTION_REQUIRED"),
    }
    return render_template(
        "commissioning/preservation.html",
        project=project, plan_rows=plan_rows, equipment=equipment, users=users,
        counts=counts, today=today, can_manage=has_permission(project.id, "preservation.manage"),
        can_execute=any(has_permission(project.id, p) for p in ("preservation.execute", "preservation.manage")),
    )


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
    if not 1 <= interval_days <= 3650:
        abort(400, description="Interval must be between 1 and 3650 days.")
    next_due_date = _parse_date("next_due_date")
    assigned_to_id = request.form.get("assigned_to_id", type=int)
    if assigned_to_id is not None and not User.query.filter_by(
        id=assigned_to_id, company_name=project.company_name, is_active=True,
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
    corrective_action = (request.form.get("corrective_action") or "").strip() or None
    if result == "NON_COMPLIANT" and not corrective_action:
        abort(400, description="Corrective action is required for a non-compliant inspection.")

    before = _plan_snapshot(plan)
    next_due_after = plan.next_due_date
    inspection = CommissioningPreservationInspection(
        company_name=project.company_name, project_id=project.id, plan_id=plan.id,
        performed_at=performed_at, result=result, findings=findings,
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
            "findings": findings, "corrective_action": corrective_action,
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
    if plan.status == "ACTION_REQUIRED" and new_status == "ACTIVE":
        abort(409, description="Record a compliant inspection before reactivating an action-required plan.")
    before = _plan_snapshot(plan)
    plan.status = new_status
    add_audit_event(
        project.company_name, "CommissioningPreservationPlan", plan.id,
        "PRESERVATION_PLAN_STATUS_UPDATED", before=before, after=_plan_snapshot(plan),
    )
    db.session.commit()
    flash("Preservation plan status updated.", "success")
    return redirect(url_for("commissioning.preservation_index", project_id=project.id))
