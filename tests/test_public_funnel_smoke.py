"""Smoke and honesty checks for the public acquisition funnel.

Route availability is covered in test_app_integration.py. These tests add
input-validation and claim-safety checks that the public pages must keep.
"""
from extensions import db
from models import ContactInquiry


def _inquiry_count(app):
    with app.app_context():
        return ContactInquiry.query.count()


def test_home_page_has_search_metadata_and_viewport(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'name="viewport"' in body
    assert 'rel="canonical"' in body
    assert 'property="og:title"' in body


def test_home_page_contains_no_unverified_metrics(client):
    body = client.get("/").get_data(as_text=True)
    assert "Illustrative readiness" not in body
    assert "68%" not in body


def test_pricing_page_states_no_prices(client):
    body = client.get("/pricing").get_data(as_text=True)
    for marker in ("$", "€", "£", "USD", "EUR", "per month", "/month"):
        assert marker not in body, marker


def test_contact_rejects_missing_email_without_storing_inquiry(client, app):
    before = _inquiry_count(app)
    response = client.post("/contact", data={"name": "Engineer", "email": "", "message": "Hello"})
    assert response.status_code == 200
    assert _inquiry_count(app) == before


def test_contact_rejects_overlong_name_without_storing_inquiry(client, app):
    before = _inquiry_count(app)
    response = client.post("/contact", data={
        "name": "N" * 121, "email": "buyer@example.com", "message": "Hello",
    })
    assert response.status_code == 200
    assert _inquiry_count(app) == before


def test_contact_valid_submission_is_stored(client, app):
    before = _inquiry_count(app)
    response = client.post("/contact", data={
        "name": "Commissioning Manager", "email": "manager@example.com",
        "company": "Example EPC", "message": "Request a demo",
    })
    assert response.status_code == 302
    assert _inquiry_count(app) == before + 1
    with app.app_context():
        stored = ContactInquiry.query.filter_by(email="manager@example.com").one()
        assert stored.source == "website"
