"""Regression checks for removal of the inherited MaterialHub role workspace."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_materialhub_role_workspace_sources_and_templates_are_not_shipped():
    assert not (ROOT / "role_workspace.py").exists()
    assert not (ROOT / "templates" / "workspaces").exists()


def test_commissioning_access_control_remains_in_the_opera_domain():
    assert (ROOT / "services" / "commissioning_access.py").is_file()
    assert (ROOT / "tests" / "test_commissioning_access.py").is_file()
