"""Safety tests for the isolated OPERA demonstration seed script."""
import importlib.util
import os
from pathlib import Path

import pytest

from extensions import db
from models import AccessLevel, User
from models_commissioning import CommissioningMembership, CommissioningProject

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "seed_commissioning_demo.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("seed_commissioning_demo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _user(company, email, name):
    return User(
        company_name=company, company_email=email, full_name=name,
        company_address="Office", country="DE",
        access_level=AccessLevel.project_manager, password="test-password-123",
    )


@pytest.fixture
def demo_user(app):
    with app.app_context():
        user = _user("Demo Contractor", "demo-seed-owner@example.com", "Demo Owner")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return user_id


@pytest.fixture
def seed_app(app, monkeypatch):
    """Make the script use the test application instead of building its own."""
    seed = _load_script()
    monkeypatch.setattr(seed, "create_app", lambda *a, **k: app)
    return seed


def _run(seed, monkeypatch, *args):
    monkeypatch.setattr("sys.argv", ["seed_commissioning_demo.py", *args])
    seed.main()


def test_seed_refuses_without_explicit_environment_flag(seed_app, demo_user, monkeypatch):
    monkeypatch.delenv("SEED_COMMISSIONING_DEMO", raising=False)
    with pytest.raises(SystemExit, match="Refusing to seed"):
        _run(seed_app, monkeypatch, "--company", "Demo Contractor", "--user-id", str(demo_user))


def test_seed_refuses_user_outside_requested_company(seed_app, demo_user, monkeypatch, app):
    monkeypatch.setenv("SEED_COMMISSIONING_DEMO", "1")
    with pytest.raises(SystemExit, match="does not exist"):
        _run(seed_app, monkeypatch, "--company", "Another Company", "--user-id", str(demo_user))
    with app.app_context():
        assert CommissioningProject.query.count() == 0


def test_seed_creates_fictional_project_without_creating_users(seed_app, demo_user, monkeypatch, app):
    monkeypatch.setenv("SEED_COMMISSIONING_DEMO", "1")
    with app.app_context():
        users_before = User.query.count()

    _run(seed_app, monkeypatch, "--company", "Demo Contractor", "--user-id", str(demo_user))

    with app.app_context():
        project = CommissioningProject.query.filter_by(
            company_name="Demo Contractor", project_code="OPERA-DEMO",
        ).one()
        assert project.name == "OPERA Demonstration Project"
        assert project.client == "Demo Client"
        assert User.query.count() == users_before
        assert CommissioningMembership.query.filter_by(
            company_name="Demo Contractor", project_id=project.id, user_id=demo_user,
        ).count() == 1


def test_seed_refuses_duplicate_project_and_changes_nothing(seed_app, demo_user, monkeypatch, app):
    monkeypatch.setenv("SEED_COMMISSIONING_DEMO", "1")
    _run(seed_app, monkeypatch, "--company", "Demo Contractor", "--user-id", str(demo_user))
    with app.app_context():
        before = CommissioningProject.query.count()

    with pytest.raises(SystemExit, match="already exists"):
        _run(seed_app, monkeypatch, "--company", "Demo Contractor", "--user-id", str(demo_user))

    with app.app_context():
        assert CommissioningProject.query.count() == before
