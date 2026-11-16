"""Project-scoped OPERA role and permission tests."""
import pytest
from flask_login import login_user

from extensions import db
from models import AccessLevel, User
from models_commissioning import CommissioningMembership, CommissioningProject, MembershipRole
from services.commissioning_access import has_permission, project_role


@pytest.fixture(autouse=True)
def _application_context(app):
    with app.app_context():
        yield


def test_opera_membership_does_not_change_legacy_user_role(app):
    user = User(
        company_name="Contractor A",
        company_email="opera-manager@example.com",
        full_name="OPERA Manager",
        company_address="Office",
        country="DE",
        access_level=AccessLevel.project_manager,
        password="test-password-123",
    )
    db.session.add(user)
    db.session.flush()
    project = CommissioningProject(company_name="Contractor A", project_code="OP-01", name="OPERA Project")
    db.session.add(project)
    db.session.flush()
    db.session.add(CommissioningMembership(company_name="Contractor A", project_id=project.id, user_id=user.id, role=MembershipRole.COMMISSIONING_MANAGER))
    db.session.commit()

    with app.test_request_context("/"):
        login_user(user)
        assert project_role(project.id) is MembershipRole.COMMISSIONING_MANAGER
        assert has_permission(project.id, "project.manage")
        assert has_permission(project.id, "punch.verify")
        assert user.access_level is AccessLevel.project_manager
