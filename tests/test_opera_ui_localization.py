"""Regression checks for the English-only OPERA interface."""
import re


PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")


def test_public_and_help_pages_use_english_shell(client):
    paths = (
        "/",
        "/auth/login",
        "/auth/register",
        "/help/",
        "/help/getting-started",
        "/help/user-guide",
        "/help/about",
        "/privacy_policy",
        "/terms_of_service",
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.get_data(as_text=True)
        assert 'lang="en"' in html, path
        assert not PERSIAN_RE.search(html), path


def test_persian_user_guide_has_a_dedicated_route(client):
    response = client.get("/help/user-guide/fa")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'dir="rtl"' in html
    assert "راهنمای کاربر OPERA" in html


def test_legacy_auth_home_uses_opera_landing(client):
    response = client.get("/auth/")
    assert response.status_code in (301, 302, 303, 307, 308)
    assert response.headers["Location"].endswith("/")
