"""P1 schema tests for project-defined Punch categories (additive step)."""
import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import AccessLevel, User
from models_commissioning import (
    CommissioningPunchCategory, CommissioningProject, PunchCategory, validate_punch_category_code,
)


def _user(company, email):
    return User(
        company_name=company, company_email=email, full_name="Category Owner",
        company_address="Office", country="DE",
        access_level=AccessLevel.project_manager, password="test-password-123",
    )


@pytest.fixture
def project_id(app):
    with app.app_context():
        owner = _user("Contractor A", "punch-category-owner@example.com")
        db.session.add(owner)
        db.session.flush()
        project = CommissioningProject(
            company_name="Contractor A", project_code="PCAT-01", name="Category Project",
            created_by_id=owner.id,
        )
        db.session.add(project)
        db.session.commit()
        return project.id


@pytest.mark.parametrize("code", ["A", "B", "MC-1", "RFSU_2", "X"])
def test_valid_punch_category_codes_are_accepted(code):
    assert validate_punch_category_code(code) == code


@pytest.mark.parametrize("code", ["", "a", "Ab", "TOOLONGCODE", "A B", "Ä", "A/B", None, 7])
def test_invalid_punch_category_codes_are_rejected(code):
    with pytest.raises(ValueError):
        validate_punch_category_code(code)


def test_category_definition_is_created_with_trimmed_label(app, project_id):
    with app.app_context():
        category = CommissioningPunchCategory(
            company_name="Contractor A", project_id=project_id, code="A",
            label="  Safety critical  ", sort_order=1, is_active=True,
        )
        db.session.add(category)
        db.session.commit()
        stored = CommissioningPunchCategory.query.filter_by(project_id=project_id, code="A").one()
        assert stored.label == "Safety critical"
        assert stored.is_active is True


def test_duplicate_code_within_a_project_is_rejected(app, project_id):
    with app.app_context():
        db.session.add(CommissioningPunchCategory(
            company_name="Contractor A", project_id=project_id, code="C", label="Cosmetic",
        ))
        db.session.commit()
        db.session.add(CommissioningPunchCategory(
            company_name="Contractor A", project_id=project_id, code="C", label="Other",
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_same_code_is_allowed_in_another_project(app, project_id):
    with app.app_context():
        owner = User.query.filter_by(company_email="punch-category-owner@example.com").one()
        other = CommissioningProject(
            company_name="Contractor A", project_code="PCAT-02", name="Second Project",
            created_by_id=owner.id,
        )
        db.session.add(other)
        db.session.flush()
        db.session.add(CommissioningPunchCategory(
            company_name="Contractor A", project_id=project_id, code="D", label="Minor",
        ))
        db.session.add(CommissioningPunchCategory(
            company_name="Contractor A", project_id=other.id, code="D", label="Minor",
        ))
        db.session.commit()
        assert CommissioningPunchCategory.query.filter_by(code="D").count() == 2


def test_legacy_punch_enum_still_works_without_category_code(app, project_id):
    from models_commissioning import PunchItem, PunchSeverity, PunchStatus, CommissioningSystem, CommissioningSubsystem
    with app.app_context():
        owner = User.query.filter_by(company_email="punch-category-owner@example.com").one()
        system = CommissioningSystem(company_name="Contractor A", project_id=project_id, system_code="SYS-P", name="Sys")
        db.session.add(system)
        db.session.flush()
        subsystem = CommissioningSubsystem(company_name="Contractor A", system_id=system.id, subsystem_code="SUB-P", name="Sub")
        db.session.add(subsystem)
        db.session.flush()
        item = PunchItem(
            company_name="Contractor A", project_id=project_id, subsystem_id=subsystem.id,
            punch_number="PCAT-01-PUNCH-A-00001", category=PunchCategory.A,
            severity=PunchSeverity.HIGH, description="Legacy item",
            raised_by_id=owner.id, status=PunchStatus.OPEN,
        )
        db.session.add(item)
        db.session.commit()
        stored = db.session.get(PunchItem, item.id)
        assert stored.category is PunchCategory.A
        assert stored.category_code is None
