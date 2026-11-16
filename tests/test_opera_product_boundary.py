"""OPERA must not expose inherited MaterialHub business routes by default."""
from config.config import TestingConfig
from app import create_app


def test_opera_product_surface_keeps_shared_auth_but_hides_legacy_modules(monkeypatch):
    monkeypatch.setattr(TestingConfig, "ENABLE_LEGACY_MODULES", False)
    app = create_app("testing")

    rules = {rule.rule for rule in app.url_map.iter_rules()}
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}

    assert "/auth/login" in rules
    assert "/commissioning/" in rules
    assert "/health/ready" in rules
    assert "auth.login" in endpoints
    assert "commissioning.dashboard" in endpoints

    for legacy_path in (
        "/warehouse/",
        "/material_requisitions/",
        "/purchase_order/",
        "/quality_control/",
        "/workspace/",
        "/admin/",
    ):
        assert legacy_path not in rules

    legacy_blueprints = (
        "supplier.", "material_requisition.", "purchase_order.",
        "quality_control.", "delivery.", "warehouse.",
        "project_dashboard.", "report.", "reports.", "admin.",
        "control_center.", "intelligence.", "operations_copilot.",
        "material_reconciliation.", "material_master.", "role_workspace.",
    )
    assert not any(
        endpoint.startswith(prefix)
        for endpoint in endpoints
        for prefix in legacy_blueprints
    )
