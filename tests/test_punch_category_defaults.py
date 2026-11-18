"""P2 tests: default Punch categories, idempotent seeding and dual write."""
from extensions import db
from models import AccessLevel, User
from models_commissioning import (
    CommissioningMembership, CommissioningPunchCategory, CommissioningProject,
    CommissioningSubsystem, CommissioningSystem, MembershipRole, PunchItem,
)
from services.commissioning_punch_categories import ensure_default_punch_categories


def _user(company, email, access=AccessLevel.project_manager):
    return User(
        company_name=company, company_email=email, full_name="Defaults Tester",
        company_address="Office", country="DE", access_level=access,
        password="test-password-123",
    )


def _login(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def _seed_project(app):
    with app.app_context():
        owner = _user("Contractor A", "defaults-owner@example.com")
        db.session.add(owner)
        db.session.flush()
        project = CommissioningProject(
            company_name="Contractor A", project_code="DEF-01", name="Defaults", created_by_id=owner.id,
        )
        db.session.add(project)
        db.session.flush()
        system = CommissioningSystem(company_name="Contractor A", project_id=project.id, system_code="SYS-D", name="Sys")
        db.session.add(system)
        db.session.flush()
        subsystem = CommissioningSubsystem(company_name="Contractor A", system_id=system.id, subsystem_code="SUB-D", name="Sub")
        db.session.add(subsystem)
        db.session.flush()
        db.session.add(CommissioningMembership(
            company_name="Contractor A", project_id=project.id, user_id=owner.id,
            role=MembershipRole.COMMISSIONING_MANAGER, is_active=True, created_by_id=owner.id,
        ))
        db.session.commit()
        return {"owner": owner.id, "project": project.id, "subsystem": subsystem.id}


def test_default_categories_are_seeded_once(app):
    ids = _seed_project(app)
    with app.app_context():
        created_first = ensure_default_punch_categories("Contractor A", ids["project"])
        db.session.commit()
        created_second = ensure_default_punch_categories("Contractor A", ids["project"])
        db.session.commit()
        assert created_first == ["A", "B", "C", "D"]
        assert created_second == []
        codes = sorted(c.code for c in CommissioningPunchCategory.query.filter_by(project_id=ids["project"]))
        assert codes == ["A", "B", "C", "D"]


def test_seeding_never_overwrites_project_edits(app):
    ids = _seed_project(app)
    with app.app_context():
        ensure_default_punch_categories("Contractor A", ids["project"])
        db.session.commit()
        cat = CommissioningPunchCategory.query.filter_by(project_id=ids["project"], code="B").one()
        cat.label = "Critical punch"
        cat.is_active = False
        db.session.commit()
        ensure_default_punch_categories("Contractor A", ids["project"])
        db.session.commit()
        cat = CommissioningPunchCategory.query.filter_by(project_id=ids["project"], code="B").one()
        assert cat.label == "Critical punch"
        assert cat.is_active is False


def test_raising_a_punch_records_category_code(client, app):
    ids = _seed_project(app)
    with app.app_context():
        ensure_default_punch_categories("Contractor A", ids["project"])
        db.session.commit()
    _login(client, ids["owner"])
    response = client.post(
        f"/commissioning/projects/{ids['project']}/punch",
        data={"subsystem_id": str(ids["subsystem"]), "category": "B",
              "severity": "HIGH", "description": "Leaking flange"},
    )
    assert response.status_code == 302
    with app.app_context():
        item = PunchItem.query.filter_by(project_id=ids["project"]).one()
        assert item.category.value == "B"
        assert item.category_code == "B"
        assert item.punch_number.startswith("DEF-01-PUNCH-B-")


def test_creating_a_project_seeds_default_categories(client, app):
    with app.app_context():
        manager = _user("Contractor C", "defaults-manager@example.com")
        db.session.add(manager)
        db.session.commit()
        manager_id = manager.id
    _login(client, manager_id)
    response = client.post("/commissioning/projects/new", data={
        "project_code": "DEF-NEW", "name": "New defaults project",
    })
    assert response.status_code == 302
    with app.app_context():
        project = CommissioningProject.query.filter_by(company_name="Contractor C", project_code="DEF-NEW").one()
        codes = sorted(c.code for c in CommissioningPunchCategory.query.filter_by(project_id=project.id))
        assert codes == ["A", "B", "C", "D"]
