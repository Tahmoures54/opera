"""OPERA must never expose inherited MaterialHub business routes."""
from app import create_app


def test_opera_product_surface_keeps_shared_auth_and_commissioning_only():
    app = create_app("testing")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}

    assert "/auth/login" in rules
    assert "/commissioning/" in rules
    assert "/health/ready" in rules
    assert "auth.login" in endpoints
    assert "commissioning.dashboard" in endpoints

    legacy_paths = (
        "/warehouse/", "/material_requisitions/", "/purchase_order/",
        "/quality_control/", "/delivery/", "/supplier/",
        "/project_dashboard/", "/inventory", "/material_marketplace",
        "/add_material", "/edit_material", "/tender", "/workspace/",
        "/admin/", "/control-center/",
    )
    for legacy_path in legacy_paths:
        assert legacy_path not in rules, legacy_path

    legacy_blueprints = (
        "supplier.", "material_requisition.", "purchase_order.",
        "quality_control.", "delivery.", "warehouse.",
        "project_dashboard.", "report.", "reports.", "admin.",
        "control_center.", "intelligence.", "operations_copilot.",
        "material_reconciliation.", "material_master.", "role_workspace.",
    )
    assert not any(endpoint.startswith(prefix) for endpoint in endpoints for prefix in legacy_blueprints)


def test_legacy_materialhub_urls_return_not_found(client):
    for path in (
        "/warehouse/", "/material_requisitions/", "/purchase_order/",
        "/quality_control/", "/delivery/", "/supplier/",
        "/project_dashboard/", "/inventory", "/material_marketplace",
        "/add_material", "/tender", "/workspace/", "/admin/",
    ):
        response = client.get(path)
        assert response.status_code == 404, (path, response.status_code)


def test_registration_only_offers_opera_account_roles(app):
    from forms.auth_forms import RegisterForm

    with app.test_request_context("/auth/register"):
        form = RegisterForm()
        values = {value for value, _label in form.access_level.choices}
        assert values == {"", "project_manager", "engineering"}
        assert not hasattr(form, "store_name")


def test_public_ui_assets_only_offer_opera_navigation():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    palette = (root / "static" / "js" / "command-palette.js").read_text(encoding="utf-8")
    workspace = (root / "static" / "js" / "workspace.js").read_text(encoding="utf-8")
    assert "/commissioning/" in palette
    assert "/commissioning/projects/new" in palette
    for retired_path in ("/workspace", "/warehouse", "/purchase_order", "/material_requisitions", "/intelligence"):
        assert retired_path not in palette, retired_path
    assert "MaterialHub" not in workspace
    assert "opera-theme" in workspace
