from pathlib import Path
import pytest

from smart_agent_skill_orchestration import _resolve_project_file


def test_b7_rebases_legacy_absolute_runtime_path(tmp_path):
    root = tmp_path / "SMART-MEGA-B7"
    target = root / "runtime" / "epoch" / "freeze.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")
    legacy = Path("C:/New Projet/SMART-MEGA/runtime/epoch/freeze.json")
    assert _resolve_project_file(root, str(legacy), label="freeze") == target.resolve()


def test_b7_keeps_external_escape_blocked(tmp_path):
    root = tmp_path / "SMART-MEGA-B7"
    root.mkdir()
    with pytest.raises(ValueError, match="escapes project root"):
        _resolve_project_file(root, "C:/outside/not-project/secret.json", label="external")