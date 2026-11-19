"""Initial OPERA project, system and subsystem CRUD."""
from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models_commissioning import (
    CommissioningMembership, CommissioningProject, CommissioningSystem,
    CommissioningSubsystem, CommissioningEquipment, CheckSheet, PunchItem, HandoverPackage, MembershipRole, ProjectStatus, PunchCategory, CheckSheetType,
    CommissioningTaskType,
)
from services.commissioning_access import add_audit_event, get_project, has_permission
from services.commissioning_punch_categories import ensure_default_punch_categories
from services.commissioning_readiness_policy import GATES, normalize_readiness_policy
from blueprints.commissioning import commissioning_bp


def _text(name, limit=200, required=False):
    value = (request.form.get(name) or "").strip()
    if required and not value:
        abort(400, description=f"{name} is required")
    if len(value) > limit:
        abort(400, description=f"{name} is too long")
    return value or None


def _parse_date(name):
    value = (request.form.get(name) or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        abort(400, description=f"Invalid date: {name}")


@commissioning_bp.get("/")
@login_required
def dashboard():
    query = CommissioningProject.query.filter_by(company_name=current_user.company_name)
    if not getattr(current_user, "is_admin", False):
        query = query.join(
            CommissioningMembership,
            CommissioningMembership.project_id == CommissioningProject.id,
        ).filter(
            CommissioningMembership.company_name == current_user.company_name,
            CommissioningMembership.user_id == current_user.id,
            CommissioningMembership.is_active.is_(True),
        ).distinct()
    projects = query.order_by(CommissioningProject.updated_at.desc()).all()
    account_role = getattr(getattr(current_user, "access_level", None), "value", getattr(current_user, "access_level", None))
    can_create_project = bool(getattr(current_user, "is_admin", False) or account_role == "project_manager")
    return render_template("commissioning/dashboard.html", projects=projects, can_create_project=can_create_project)


@commissioning_bp.route("/projects/new", methods=["GET", "POST"])
@login_required
def create_project():
    account_role = getattr(getattr(current_user, "access_level", None), "value", getattr(current_user, "access_level", None))
    if not (getattr(current_user, "is_admin", False) or account_role == "project_manager"):
        abort(403)
    if request.method == "POST":
        code = _text("project_code", 50, True)
        name = _text("name", 200, True)
        if CommissioningProject.query.filter_by(company_name=current_user.company_name, project_code=code).first():
            flash("This project code is already in use.", "warning")
            return render_template("commissioning/project_form.html"), 409
        project = CommissioningProject(
            company_name=current_user.company_name,
            project_code=code,
            name=name,
            client=_text("client"),
            contractor=_text("contractor"),
            start_date=_parse_date("start_date"),
            target_end_date=_parse_date("target_end_date"),
            status=ProjectStatus.PLANNING,
            description=_text("description", 5000),
            created_by_id=current_user.id,
        )
        db.session.add(project)
        db.session.flush()
        db.session.add(CommissioningMembership(
            company_name=current_user.company_name,
            project_id=project.id,
            user_id=current_user.id,
            role=MembershipRole.COMMISSIONING_MANAGER,
            is_active=True,
            created_by_id=current_user.id,
        ))
        ensure_default_punch_categories(current_user.company_name, project.id, created_by_id=current_user.id)
        add_audit_event(current_user.company_name, "CommissioningProject", project.id, "PROJECT_CREATED", after={"project_code": code, "name": name})
        db.session.commit()
        flash("OPERA project created successfully.", "success")
        return redirect(url_for("commissioning.project_detail", project_id=project.id))
    return render_template("commissioning/project_form.html")


@commissioning_bp.get("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    project = get_project(project_id)
    if not has_permission(project_id, "structure.view") and not has_permission(project_id, "project.manage"):
        abort(403)
    systems = CommissioningSystem.query.filter_by(company_name=current_user.company_name, project_id=project.id).filter(CommissioningSystem.status != "ARCHIVED").order_by(CommissioningSystem.system_code).all()
    system_subsystems = {system.id: CommissioningSubsystem.query.filter_by(company_name=current_user.company_name, system_id=system.id).filter(CommissioningSubsystem.status != "ARCHIVED").order_by(CommissioningSubsystem.subsystem_code).all() for system in systems}
    return render_template("commissioning/project_structure.html", project=project, systems=systems, system_subsystems=system_subsystems)



@commissioning_bp.route("/projects/<int:project_id>/readiness-policy", methods=["GET", "POST"])
@login_required
def edit_readiness_policy(project_id):
    """Configure project-specific MC/RFC/RFSU blockers and evidence requirements."""
    project = get_project(project_id)
    if not has_permission(project_id, "project.manage"):
        abort(403)

    policy, errors = normalize_readiness_policy(project.readiness_policy_json)
    if request.method == "POST":
        updated = {
            "punch_blocking_categories": {
                gate: request.form.getlist(f"punch_{gate}") for gate in GATES
            },
            "hold_point_blocking_gates": request.form.getlist("hold_point_blocking_gates"),
            "required_check_sheet_types": {
                gate: request.form.getlist(f"sheets_{gate}") for gate in GATES
            },
            "require_check_sheet_presence": request.form.get("require_check_sheet_presence") == "on",
            "require_all_tasks_complete_for_rfsu": request.form.get("require_all_tasks_complete_for_rfsu") == "on",
            "mc_required_task_types": request.form.getlist("mc_required_task_types"),
            "presence_required_gates": request.form.getlist("presence_required_gates"),
        }
        normalized, validation_errors = normalize_readiness_policy(updated)
        if validation_errors:
            abort(400, description="; ".join(validation_errors))
        before = policy
        project.readiness_policy_json = normalized
        add_audit_event(
            project.company_name, "CommissioningProject", project.id,
            "READINESS_POLICY_UPDATED", before=before, after=normalized,
        )
        db.session.commit()
        flash("Project readiness policy saved.", "success")
        return redirect(url_for("commissioning.edit_readiness_policy", project_id=project.id))

    return render_template(
        "commissioning/readiness_policy.html",
        project=project,
        policy=policy,
        gates=GATES,
        punch_categories=list(PunchCategory),
        check_sheet_types=list(CheckSheetType),
        task_types=list(CommissioningTaskType),
        policy_errors=errors,
    )



@commissioning_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(project_id):
    project = get_project(project_id)
    if not has_permission(project_id, "project.manage"):
        abort(403)
    if request.method == "POST":
        before = {"name": project.name, "client": project.client, "contractor": project.contractor, "status": project.status.value}
        project.name = _text("name", 200, True)
        project.client = _text("client")
        project.contractor = _text("contractor")
        project.start_date = _parse_date("start_date")
        project.target_end_date = _parse_date("target_end_date")
        project.description = _text("description", 5000)
        add_audit_event(project.company_name, "CommissioningProject", project.id, "PROJECT_UPDATED", before=before, after={"name": project.name, "client": project.client, "contractor": project.contractor})
        db.session.commit()
        flash("Project details updated successfully.", "success")
        return redirect(url_for("commissioning.project_detail", project_id=project.id))
    return render_template("commissioning/project_form.html", project=project)


@commissioning_bp.post("/projects/<int:project_id>/archive")
@login_required
def archive_project(project_id):
    project = get_project(project_id)
    if not has_permission(project_id, "project.manage"):
        abort(403)
    if CommissioningSystem.query.filter_by(company_name=project.company_name, project_id=project.id).filter(CommissioningSystem.status != "ARCHIVED").first():
        abort(409, description="Archive systems and subsystems through their own controlled lifecycle before archiving this project.")
    before = {"status": project.status.value}
    project.status = ProjectStatus.CANCELLED
    add_audit_event(project.company_name, "CommissioningProject", project.id, "PROJECT_ARCHIVED", before=before, after={"status": project.status.value})
    db.session.commit()
    return redirect(url_for("commissioning.dashboard"))


@commissioning_bp.route("/systems/<int:system_id>/edit", methods=["GET", "POST"])
@login_required
def edit_system(system_id):
    system = CommissioningSystem.query.filter_by(id=system_id, company_name=current_user.company_name).first_or_404()
    project = get_project(system.project_id)
    if not has_permission(project.id, "structure.manage") and not has_permission(project.id, "project.manage"):
        abort(403)
    if request.method == "POST":
        before = {"name": system.name, "weight_percent": system.weight_percent, "p_and_id_ref": system.p_and_id_ref}
        system.name = _text("name", 200, True)
        system.p_and_id_ref = _text("p_and_id_ref")
        try:
            weight = float(request.form.get("weight_percent") or 0)
        except ValueError:
            abort(400, description="Invalid weight")
        if not 0 <= weight <= 100:
            abort(400, description="weight_percent must be between 0 and 100")
        system.weight_percent = weight
        system.description = _text("description", 5000)
        add_audit_event(project.company_name, "CommissioningSystem", system.id, "SYSTEM_UPDATED", before=before, after={"name": system.name, "weight_percent": weight, "p_and_id_ref": system.p_and_id_ref})
        db.session.commit()
        return redirect(url_for("commissioning.project_detail", project_id=project.id))
    return render_template("commissioning/structure_form.html", kind="system", project=project, system=system, edit=True)


@commissioning_bp.route("/subsystems/<int:subsystem_id>/edit", methods=["GET", "POST"])
@login_required
def edit_subsystem(subsystem_id):
    subsystem = CommissioningSubsystem.query.filter_by(id=subsystem_id, company_name=current_user.company_name).first_or_404()
    system = CommissioningSystem.query.filter_by(id=subsystem.system_id, company_name=current_user.company_name).first_or_404()
    project = get_project(system.project_id)
    if not has_permission(project.id, "structure.manage") and not has_permission(project.id, "project.manage"):
        abort(403)
    if request.method == "POST":
        before = {"name": subsystem.name, "weight_percent": subsystem.weight_percent}
        subsystem.name = _text("name", 200, True)
        try:
            weight = float(request.form.get("weight_percent") or 0)
        except ValueError:
            abort(400, description="Invalid weight")
        if not 0 <= weight <= 100:
            abort(400, description="weight_percent must be between 0 and 100")
        subsystem.weight_percent = weight
        subsystem.mc_target_date = _parse_date("mc_target_date")
        subsystem.rf_target_date = _parse_date("rf_target_date")
        subsystem.description = _text("description", 5000)
        add_audit_event(project.company_name, "CommissioningSubsystem", subsystem.id, "SUBSYSTEM_UPDATED", before=before, after={"name": subsystem.name, "weight_percent": weight})
        db.session.commit()
        return redirect(url_for("commissioning.project_detail", project_id=project.id))
    return render_template("commissioning/structure_form.html", kind="subsystem", project=project, system=system, subsystem=subsystem, edit=True)


@commissioning_bp.route("/projects/<int:project_id>/systems/new", methods=["GET", "POST"])
@login_required
def create_system(project_id):
    project = get_project(project_id)
    if not has_permission(project_id, "structure.manage") and not has_permission(project_id, "project.manage"):
        abort(403)
    if request.method == "POST":
        code = _text("system_code", 50, True)
        if CommissioningSystem.query.filter_by(company_name=project.company_name, project_id=project.id, system_code=code).first():
            flash("This system code is already in use.", "warning")
            return render_template("commissioning/structure_form.html", kind="system", project=project), 409
        try:
            weight = float(request.form.get("weight_percent") or 0)
        except ValueError:
            abort(400, description="Invalid weight")
        if not 0 <= weight <= 100:
            abort(400, description="weight_percent must be between 0 and 100")
        system = CommissioningSystem(company_name=project.company_name, project_id=project.id, system_code=code, name=_text("name", 200, True), p_and_id_ref=_text("p_and_id_ref"), weight_percent=weight, description=_text("description", 5000))
        db.session.add(system)
        db.session.flush()
        add_audit_event(project.company_name, "CommissioningSystem", system.id, "SYSTEM_CREATED", after={"system_code": code, "name": system.name})
        db.session.commit()
        return redirect(url_for("commissioning.project_detail", project_id=project.id))
    return render_template("commissioning/structure_form.html", kind="system", project=project)


@commissioning_bp.post("/systems/<int:system_id>/archive")
@login_required
def archive_system(system_id):
    system = CommissioningSystem.query.filter_by(id=system_id, company_name=current_user.company_name).first_or_404()
    project = get_project(system.project_id)
    if not has_permission(project.id, "project.manage"):
        abort(403)
    if CommissioningSubsystem.query.filter_by(company_name=project.company_name, system_id=system.id).filter(CommissioningSubsystem.status != "ARCHIVED").first():
        abort(409, description="System still contains subsystems")
    system.status = "ARCHIVED"
    add_audit_event(project.company_name, "CommissioningSystem", system.id, "SYSTEM_ARCHIVED", after={"status": system.status})
    db.session.commit()
    return redirect(url_for("commissioning.project_detail", project_id=project.id))


@commissioning_bp.post("/subsystems/<int:subsystem_id>/archive")
@login_required
def archive_subsystem(subsystem_id):
    subsystem = CommissioningSubsystem.query.filter_by(id=subsystem_id, company_name=current_user.company_name).first_or_404()
    system = CommissioningSystem.query.filter_by(id=subsystem.system_id, company_name=current_user.company_name).first_or_404()
    project = get_project(system.project_id)
    if not has_permission(project.id, "project.manage"):
        abort(403)
    has_records = any((
        CommissioningEquipment.query.filter_by(company_name=project.company_name, subsystem_id=subsystem.id).first(),
        CheckSheet.query.filter_by(company_name=project.company_name, subsystem_id=subsystem.id).first(),
        PunchItem.query.filter_by(company_name=project.company_name, subsystem_id=subsystem.id).first(),
        HandoverPackage.query.filter_by(company_name=project.company_name, subsystem_id=subsystem.id).first(),
    ))
    if has_records:
        abort(409, description="Subsystem has commissioning records and cannot be archived")
    subsystem.status = "ARCHIVED"
    add_audit_event(project.company_name, "CommissioningSubsystem", subsystem.id, "SUBSYSTEM_ARCHIVED", after={"status": subsystem.status})
    db.session.commit()
    return redirect(url_for("commissioning.project_detail", project_id=project.id))


@commissioning_bp.route("/systems/<int:system_id>/subsystems/new", methods=["GET", "POST"])
@login_required
def create_subsystem(system_id):
    system = CommissioningSystem.query.filter_by(id=system_id, company_name=current_user.company_name).first_or_404()
    project = get_project(system.project_id)
    if not has_permission(project.id, "structure.manage") and not has_permission(project.id, "project.manage"):
        abort(403)
    if request.method == "POST":
        code = _text("subsystem_code", 50, True)
        if CommissioningSubsystem.query.filter_by(company_name=project.company_name, system_id=system.id, subsystem_code=code).first():
            flash("This subsystem code is already in use.", "warning")
            return render_template("commissioning/structure_form.html", kind="subsystem", project=project), 409
        try:
            weight = float(request.form.get("weight_percent") or 0)
        except ValueError:
            abort(400, description="Invalid weight")
        if not 0 <= weight <= 100:
            abort(400, description="weight_percent must be between 0 and 100")
        subsystem = CommissioningSubsystem(company_name=project.company_name, system_id=system.id, subsystem_code=code, name=_text("name", 200, True), weight_percent=weight, mc_target_date=_parse_date("mc_target_date"), rf_target_date=_parse_date("rf_target_date"), description=_text("description", 5000))
        db.session.add(subsystem)
        db.session.flush()
        add_audit_event(project.company_name, "CommissioningSubsystem", subsystem.id, "SUBSYSTEM_CREATED", after={"subsystem_code": code, "name": subsystem.name})
        db.session.commit()
        return redirect(url_for("commissioning.project_detail", project_id=project.id))
    return render_template("commissioning/structure_form.html", kind="subsystem", project=project, system=system)
