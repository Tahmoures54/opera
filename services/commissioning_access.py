"""Project-scoped authorization helpers for OPERA."""
from functools import wraps

from flask import abort
from flask_login import current_user

from extensions import db
from models_commissioning import CommissioningMembership, CommissioningProject, MembershipRole


ROLE_PERMISSIONS = {
    MembershipRole.COMMISSIONING_MANAGER: frozenset({"project.manage", "structure.manage", "checksheets.manage", "punch.raise", "punch.assign", "punch.verify", "witness.manage", "handover.manage", "handover.accept", "reports.view", "members.manage"}),
    MembershipRole.COMMISSIONING_ENGINEER: frozenset({"structure.view", "checksheets.create", "checksheets.fill", "punch.raise", "witness.view", "reports.view"}),
    MembershipRole.QC_INSPECTOR: frozenset({"structure.view", "checksheets.view", "punch.verify", "witness.attend", "reports.view"}),
    MembershipRole.CLIENT_REPRESENTATIVE: frozenset({"structure.view", "checksheets.view", "checksheets.sign", "punch.view", "witness.view", "reports.view"}),
    MembershipRole.OPERATIONS_LEAD: frozenset({"structure.view", "checksheets.view", "punch.view", "handover.accept", "reports.view"}),
    MembershipRole.VIEWER: frozenset({"structure.view", "checksheets.view", "punch.view", "witness.view", "handover.view", "reports.view"}),
}


def get_project(project_id, company_name=None):
    """Return a project only inside the active user's company boundary."""
    company_name = company_name or getattr(current_user, "company_name", None)
    if not company_name:
        abort(403)
    project = CommissioningProject.query.filter_by(id=project_id, company_name=company_name).first()
    if project is None:
        abort(404)
    return project


def project_role(project_id):
    """Return the active user's OPERA role for a project, if assigned."""
    if getattr(current_user, "is_admin", False):
        return MembershipRole.COMMISSIONING_MANAGER
    membership = CommissioningMembership.query.filter_by(
        project_id=project_id,
        user_id=current_user.id,
        company_name=current_user.company_name,
        is_active=True,
    ).first()
    return membership.role if membership else None


def has_permission(project_id, permission):
    role = project_role(project_id)
    return bool(role and permission in ROLE_PERMISSIONS.get(role, ()))


def require_project_permission(permission):
    """Authorize a view using its ``project_id`` URL argument."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            project_id = kwargs.get("project_id")
            if project_id is None:
                abort(400)
            get_project(project_id)
            if not has_permission(project_id, permission):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def add_audit_event(company_name, entity_type, entity_id, action, before=None, after=None, user_id=None):
    """Append a tenant-scoped audit event in the caller's transaction."""
    from models_commissioning import CommissioningAuditLog
    from flask import request, has_request_context

    event = CommissioningAuditLog(
        company_name=company_name,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id or (current_user.id if getattr(current_user, "is_authenticated", False) else None),
        ip_address=request.remote_addr if has_request_context() else None,
        user_agent=(request.user_agent.string[:500] if has_request_context() else None),
        before_json=before,
        after_json=after,
    )
    db.session.add(event)
    return event
