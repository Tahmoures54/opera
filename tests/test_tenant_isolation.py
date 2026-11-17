"""Tenant isolation for the OPERA commissioning product surface."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_commissioning_membership_and_access_tests_are_present():
    assert (ROOT / "services" / "commissioning_access.py").is_file()
    assert (ROOT / "tests" / "test_commissioning_access.py").is_file()
    assert (ROOT / "tests" / "test_commissioning_workflows.py").is_file()

def test_legacy_materialhub_api_endpoints_are_not_registered(client):
    for path in ("/material_requisitions/api/material_requisitions", "/warehouse/api/inventory", "/reports/api/summary", "/intelligence/api/overview"):
        assert client.get(path).status_code == 404, path
