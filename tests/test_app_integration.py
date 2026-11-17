"""Flask integration tests for MaterialHub."""
import pytest

flask = pytest.importorskip("flask")

from app import create_app
from extensions import db
from models import AccessLevel, ContactInquiry, User


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_liveness_and_readiness(client):
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.get_json()["check"] == "liveness"
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.get_json()["status"] == "ready"


def test_public_landing_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"OPERA" in response.data
    assert b"Commissioning" in response.data


def test_growth_pages_are_registered(client):
    assert client.get("/demo").status_code == 200
    assert client.get("/pricing").status_code == 200
    assert client.get("/contact").status_code == 200


def test_help_center_is_at_canonical_url(client):
    assert client.get("/help/").status_code == 200
    assert client.get("/getting-started").status_code in (200, 302)


def test_legacy_workspace_routes_are_removed(client):
    assert client.get("/workspace/", follow_redirects=False).status_code == 404
    assert client.get("/workspace/engineering", follow_redirects=False).status_code == 404


def test_auth_aliases(client):
    assert client.get("/register", follow_redirects=False).status_code == 302
    assert client.get("/login", follow_redirects=False).status_code == 302


def test_contact_inquiry_is_persisted(client, app):
    response = client.post("/contact", data={
        "name": "Sara Engineer",
        "email": "sara@example.com",
        "company": "EPC Co",
        "message": "Need a warehouse demo",
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        inquiry = ContactInquiry.query.filter_by(email="sara@example.com").first()
        assert inquiry is not None
        assert inquiry.company == "EPC Co"


def test_observability_endpoints(client):
    assert client.get("/metrics").status_code == 200
    assert client.get("/health/live").headers.get("X-Request-ID")
    assert client.get("/health/ready").headers.get("X-Request-ID")


def _authenticate_session(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(getattr(user, "id", user))
        session["_fresh"] = True


def _persist_user(app, email, role=AccessLevel.engineering, company="Auth EPC", admin=False):
    with app.app_context():
        user = User(
            company_name=company,
            company_email=email,
            company_phone="+989129999999",
            full_name="Auth Test User",
            company_address="Test Address",
            country="IR",
            access_level=role,
            is_admin=admin,
            totp_secret=User.encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
            totp_confirmed=True,
        )
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        db.session.expunge(user)
        return user


def test_authenticated_home_and_logout(client, app):
    user = _persist_user(app, "logout@example.com")
    _authenticate_session(client, user)
    assert client.get("/").status_code in (200, 302)
    response = client.get("/auth/logout", follow_redirects=False)
    assert response.status_code == 302


def test_auth_invalid_totp_and_unknown_user(client, app):
    user = _persist_user(app, "totp@example.com")
    invalid_code_response = client.post("/auth/login", data={
        "email": user.company_email,
        "totp_code": "000000",
        "submit": "Login",
    })
    missing_user_response = client.post("/auth/login", data={
        "email": "missing@example.com",
        "totp_code": "000000",
        "submit": "Login",
    })
    assert invalid_code_response.status_code == missing_user_response.status_code == 200
    generic_message = b"Unable to sign in with those details"
    assert generic_message in invalid_code_response.data
    assert generic_message in missing_user_response.data
    assert b"No account found" not in missing_user_response.data

def test_auth_reset_and_change_password_pages(client, app):
    assert client.get("/auth/reset_password_request").status_code == 200
    assert client.get("/auth/change_password", follow_redirects=False).status_code in (302, 401)
    user = _persist_user(app, "change@example.com")
    _authenticate_session(client, user)
    assert client.get("/auth/change_password", follow_redirects=True).status_code == 200








def test_public_robots_and_sitemap(client):
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert b"Disallow: /admin" in robots.data
    assert b"Sitemap:" in robots.data

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert sitemap.mimetype in ("application/xml", "text/xml")
    for path in ("/", "/demo", "/pricing", "/contact"):
        assert path.encode() in sitemap.data






def test_contact_form_accepts_database_aligned_max_lengths(client, app):
    email = ("a" * 242) + "@example.com"
    response = client.post("/contact", data={
        "name": "N" * 120,
        "email": email,
        "company": "C" * 160,
        "message": "M",
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        inquiry = ContactInquiry.query.filter_by(email=email).first()
        assert inquiry is not None
        assert len(inquiry.email) == 254
        assert len(inquiry.company) == 160


def test_materialhub_business_routes_are_removed(client):
    for path in (
        "/material_requisitions/", "/purchase_order/", "/quality_control/",
        "/delivery/", "/warehouse/", "/supplier/", "/material_marketplace",
        "/inventory", "/tender",
    ):
        assert client.get(path).status_code == 404, path
