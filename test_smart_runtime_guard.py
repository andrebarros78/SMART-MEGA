from pathlib import Path
import sys
from smart_runtime_guard import audit

ROOT=Path(__file__).resolve().parent

def test_runtime_guard_passes_inside_project_venv():
    r=audit(ROOT)
    assert r['checks']['canonical_python_exists']
    assert r['checks']['required_modules_available']
    assert r['checks']['direct_requirements_fully_pinned']
    assert r['checks']['direct_requirements_match_lock_and_environment']
    assert r['checks']['no_external_project_path_in_sys_path'] is True

def test_runtime_guard_detects_cross_project_sys_path(monkeypatch):
    monkeypatch.setattr(sys,'path',[*sys.path,r'C:\New Projet\WMCP 3.1\src'])
    r=audit(ROOT)
    assert r['checks']['no_external_project_path_in_sys_path'] is False
    assert any('WMCP 3.1' in x for x in r['external_project_paths'])
