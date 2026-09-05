from pathlib import Path
from smart_runtime_guard import audit

def test_runtime_guard_passes_inside_project_venv():
    r=audit(Path(__file__).resolve().parent)
    assert r['checks']['canonical_python_exists']
    assert r['checks']['required_modules_available']
