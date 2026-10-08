from pathlib import Path

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
