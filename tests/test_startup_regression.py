from pathlib import Path
import ast, re

ROOT = Path(__file__).resolve().parents[1]



def test_python_sources_parse():
    errors=[]
    for p in ROOT.rglob("*.py"):
        if ".venv" in p.parts or "__pycache__" in p.parts:
            continue
        try:
            ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except Exception as exc:
            errors.append((str(p), str(exc)))
    assert not errors, errors


def test_auth_uses_moved_register_template():
    auth = (ROOT / "blueprints" / "auth.py").read_text(encoding="utf-8")
    assert "auth/register.html" in auth
    assert "render_template(\n        'register.html'" not in auth
    assert "'register.html'" not in auth


def test_legacy_warehouse_blueprint_is_not_part_of_the_application():
    from app import create_app

    app = create_app("testing")
    assert "warehouse" not in app.blueprints
    assert all(not rule.rule.startswith("/warehouse") for rule in app.url_map.iter_rules())


def test_legacy_materialhub_utility_modules_are_not_shipped():
    assert not (ROOT / "utils.py").exists()
    assert not (ROOT / "models_intelligence.py").exists()
