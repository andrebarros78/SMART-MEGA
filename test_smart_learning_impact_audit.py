from pathlib import Path

from smart_learning_impact_audit import _ranking_changes, _weight_changes, audit


def test_weight_impact_audit_counts_all_adjusted_signals():
    result = _weight_changes({"a": 0.5, "b": 0.5}, {"a": 0.6, "b": 0.4})
    assert result["signals"] == 2
    assert result["signals_changing_weight"] == 2
    assert abs(result["total_absolute_weight_change"] - 0.2) < 1e-12


def test_rank_impact_audit_does_not_confuse_reordering_with_changed_top_six():
    original = list(range(1, 61))
    changed = [2, 1, *range(3, 61)]
    result = _ranking_changes(original, changed)
    assert result["numbers_changing_rank"] == 2
    assert result["top6_changed"] is False


def test_canonical_impact_is_observational_and_requires_real_frozen_cards():
    root = Path(__file__).resolve().parent
    if not (root / "SMART_CANONICAL_ROOT.json").is_file():
        return
    before = (root / "SMART_OPERATIONAL_LIFECYCLE.json").read_bytes()
    result = audit(root)
    assert result["status"] == "OBSERVATION_ONLY"
    assert result["mutates_state"] is False
    assert result["predictive_weight_authority"] is False
    assert result["prospective_superiority_proven"] is False
    transitions = {(r["from_target"], r["to_target"]): r for r in result["transitions"]}
    assert (3067, 3068) in transitions
    assert (3070, 3071) in transitions
    assert transitions[(3067, 3068)]["single_result_attributable"] is True
    assert transitions[(3070, 3071)]["primary_card_changed"] is False
    assert (root / "SMART_OPERATIONAL_LIFECYCLE.json").read_bytes() == before


def test_raw_signal_change_audit_counts_only_real_value_movements():
    from smart_learning_impact_audit import _raw_signal_changes
    baseline = {"freq25": {"values": {str(n): 0.5 for n in range(1, 61)}}}
    updated = {"freq25": {"values": {str(n): (0.6 if n == 1 else 0.5) for n in range(1, 61)}}}
    proof = _raw_signal_changes(baseline, updated)
    assert proof["signals"] == 1
    assert proof["signals_with_changed_values"] == 1
    assert proof["total_changed_number_cells"] == 1
    assert abs(proof["total_absolute_signal_change"] - 0.1) < 1e-12
