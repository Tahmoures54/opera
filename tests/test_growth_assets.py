from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_production_env_template_exists():
    assert (ROOT/'.env.example').exists()
    assert not (ROOT/'.env').exists()

def test_marketing_pages_exist():
    for name in ['demo.html','pricing.html','contact.html']:
        assert (ROOT/'templates'/'marketing'/name).exists()
    home = ROOT/'templates'/'Home.html'
    assert home.exists()
    content = home.read_text(encoding='utf-8')
    assert 'images/marketing/opera-hero.jpg' in content
    assert 'Create your account' in content
    assert 'Punch management' in content
    assert (ROOT/'static'/'images'/'marketing'/'opera-hero.jpg').exists()

def test_health_and_wsgi_exist():
    assert (ROOT/'wsgi.py').exists()
    assert (ROOT/'blueprints'/'health.py').exists()
    health = (ROOT/'blueprints'/'health.py').read_text(encoding='utf-8')
    assert '/health/live' in health
    assert '/health/ready' in health

def test_production_docker_assets_exist():
    assert (ROOT/'Dockerfile.production').exists()
    assert (ROOT/'docker-compose.production.yml').exists()

def test_commissioning_workspace_is_the_only_operational_workspace():
    assert (ROOT/'blueprints'/'commissioning'/'workflow.py').exists()
    assert (ROOT/'templates'/'commissioning'/'dashboard.html').exists()
    assert not (ROOT/'role_workspace.py').exists()
    assert not (ROOT/'templates'/'workspaces').exists()
