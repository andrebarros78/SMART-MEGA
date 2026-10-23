from pathlib import Path

import pytest

from smart_component_reachability import build_registry


ROOT = Path(__file__).resolve().parent


def _component(registry, path):
    return next(c for c in registry["components"] if c["source_file"] == path)


def test_f01_reachability_gate_is_fail_closed():
    registry = build_registry(ROOT)
    assert registry["gate"]["status"] == "PASS"
    assert registry["gate"]["parse_errors"] == []
    assert registry["gate"]["execution_dependency_errors"] == []
    assert registry["gate"]["unclassified"] == []
    assert registry["gate"]["production_unreachable"] == []
    assert registry["gate"]["required_production_missing"] == []
    assert registry["gate"]["required_production_unreachable"] == []


def test_f01_canonical_chain_is_production_reachable():
    registry = build_registry(ROOT)
    for path in registry["required_production_files"]:
        component = _component(registry, path)
        assert component["role"] == "PRODUCTION", path
        assert component["production_reachable"] is True, path
        assert component["entrypoints"], path


def test_f01_known_debts_are_observed_not_hidden():
    registry = build_registry(ROOT)
    debt = registry["known_debt_observations"]
    assert isinstance(debt["operator_pipeline_cycle_detected"], bool)
    assert isinstance(debt["legacy_3054_terminal_executor_reachable"], bool)


def test_f01_registry_file_matches_live_source_graph():
    registry_path = ROOT / "SMART_COMPONENT_REACHABILITY_REGISTRY.json"
    assert registry_path.exists()
    import json
    persisted = json.loads(registry_path.read_text(encoding="utf-8"))
    assert persisted == build_registry(ROOT)



def test_f01_entrypoints_use_external_execution_not_github_actions():
    registry = build_registry(ROOT)
    assert registry["entrypoint_authority"] == "SMART_GITHUB_CANONICAL_EXTERNAL_EXECUTION_NO_ACTIONS_20261021"
    assert registry["workflow_entrypoints"]["smart_github_operator.py"] == [
        "EXTERNAL_EXECUTOR:SMART_GITHUB_CANONICAL_EXTERNAL_EXECUTION_NO_ACTIONS_20261021"
    ]
    assert all(
        not any(".github/workflows/" in x for x in values)
        for values in registry["workflow_entrypoints"].values()
    )


def test_f01_rejects_any_runnable_github_actions_file(tmp_path):
    from smart_component_reachability import _workflow_entrypoints
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("on: push\n", encoding="utf-8")
    with pytest.raises(ValueError, match="GitHub Actions is forbidden"):
        _workflow_entrypoints(tmp_path, {"smart_github_operator.py": "smart_github_operator"})



def test_f01_external_native_policy_and_linux_runner_are_reachable():
    registry = build_registry(ROOT)
    by_path = {row["source_file"]: row for row in registry["components"]}
    for name in ("smart_github_native_policy.py", "smart_linux_ci.py"):
        row = by_path[name]
        assert row["role"] == "PRODUCTION"
        assert row["production_reachable"] is True
        assert row["predictive_authority"] == "NOT_ESTABLISHED_BY_STATIC_REACHABILITY"

def test_f01_source_hash_is_eol_independent():
    import hashlib
    from smart_component_reachability import _source_hash
    canonical = b"print(1)\nprint(2)\n"
    crlf = canonical.replace(b"\n", b"\r\n")
    assert _source_hash(canonical) == _source_hash(crlf)
    assert _source_hash(canonical) == hashlib.sha256(canonical).hexdigest()
