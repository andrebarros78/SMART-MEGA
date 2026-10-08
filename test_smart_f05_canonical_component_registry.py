from pathlib import Path

from smart_canonical_component_registry import AUTHORITY_OVERRIDES, build_registry

ROOT = Path(__file__).resolve().parent


def _row(registry, source):
    return next(c for c in registry["components"] if c["implementation"] == source)


def test_f05_registry_gate_is_fail_closed_and_complete():
    registry = build_registry(ROOT)
    assert registry["gate"] == {"status": "PASS", "errors": []}
    assert registry["summary"]["component_count"] == len(registry["components"])
    assert registry["summary"]["active"] > 0
    assert registry["summary"]["deprecated"] >= 1
    assert all(c["state"] != "ACTIVE" or c["production_reachable"] is True for c in registry["components"])
    assert all(c["state"] == "ACTIVE" or c["production_reachable"] is False for c in registry["components"])


def test_f05_material_authority_requires_explicit_active_allowlist():
    registry = build_registry(ROOT)
    authority_rows = [
        c for c in registry["components"]
        if c["predictive_authority"] != "NONE"
        or c["weight_authority"] != "NONE"
        or c["freeze_authority"] != "NONE"
    ]
    assert {c["implementation"] for c in authority_rows} == set(AUTHORITY_OVERRIDES)
    assert all(c["state"] == "ACTIVE" for c in authority_rows)


def test_f05_core_authority_semantics_are_explicit():
    registry = build_registry(ROOT)
    signal = _row(registry, "smart_signal_agent.py")
    fine = _row(registry, "smart_ai_fine_tuning.py")
    freeze = _row(registry, "smart_champion_challenger.py")
    card = _row(registry, "smart_primary_card_selector.py")
    legacy = _row(registry, "smart_3054_terminal_executor.py")

    assert signal["weight_authority"] == "DIRECT_DYNAMIC_WEIGHT_COMPUTATION"
    assert fine["weight_authority"] == "INDIRECT_BOUNDED_HYPERPARAMETER_GOVERNANCE"
    assert freeze["freeze_authority"] == "PRE_RESULT_FREEZE_WRITER"
    assert card["predictive_authority"] == "POST_SCORING_CARD_SELECTION"
    assert legacy["state"] == "DEPRECATED"
    assert legacy["production_reachable"] is False
    assert legacy["retirement_status"] == "RETIRED_FROM_CANONICAL_RUNTIME"


def test_f05_persisted_registry_matches_live_code():
    import json
    persisted = json.loads((ROOT / "SMART_CANONICAL_COMPONENT_REGISTRY.json").read_text(encoding="utf-8"))
    assert persisted == build_registry(ROOT)
