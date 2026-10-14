"""Consumer-to-card proof tests use the already immutable 3070 freeze as a fixture."""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from test_smart_consumer_audit_support import evaluate


@pytest.fixture
def specimen() -> dict:
    root = Path(__file__).resolve().parent
    epoch = next(root.glob("runtime/learning_epochs/operator-3070-*/SMART_3070_PRIMARY_CARD.json")).parent
    card = json.loads((epoch / "SMART_3070_PRIMARY_CARD.json").read_text(encoding="utf-8"))
    return {
        "root": root,
        "target": 3070,
        "epoch_id": card["run_id"],
        "freeze_path": root / card["freeze_file"],
        "portfolio_path": root / card["portfolio_file"],
        "primary_card": card,
        "pre_gate": json.loads((epoch / "PRE_FREEZE_TOTAL_INTEGRATION.json").read_text(encoding="utf-8")),
        "post_gate": json.loads((epoch / "POST_FREEZE_TOTAL_INTEGRATION.json").read_text(encoding="utf-8")),
    }


def test_real_frozen_3070_consumer_chain_passes(specimen):
    result = evaluate(**specimen)
    assert result["status"] == "PASS"
    assert all(result["checks"].values())
    assert result["card_numbers"] == [10, 11, 27, 38, 43, 53]
    assert result["effective_decision_head"] == "champion"
    assert result["challenger_weight_role"] == "SHADOW_UNLESS_EVIDENCE_PROMOTED"
    assert result["predictive_advantage_proven"] is False


def test_altered_primary_card_fails_closed(specimen):
    changed = {**specimen, "primary_card": copy.deepcopy(specimen["primary_card"])}
    changed["primary_card"]["numbers"][0] = 2
    with pytest.raises(RuntimeError, match="six_numbers_exactly_from_selector_and_portfolio"):
        evaluate(**changed)


def test_quarantined_external_claim_fails_closed(specimen):
    changed = {**specimen, "post_gate": copy.deepcopy(specimen["post_gate"])}
    changed["post_gate"]["skill_inventory"][0]["external_skill_source_executed"] = True
    with pytest.raises(RuntimeError, match="external_third_party_code_quarantined"):
        evaluate(**changed)


def test_tampered_challenger_weight_fails_closed(specimen, tmp_path):
    changed = dict(specimen)
    freeze = json.loads(specimen["freeze_path"].read_text(encoding="utf-8"))
    freeze["challenger"]["weights"]["freq25"] = 100.0
    fp = tmp_path / "freeze.json"
    pp = tmp_path / "portfolio.json"
    fp.write_text(json.dumps(freeze), encoding="utf-8")
    shutil.copyfile(specimen["portfolio_path"], pp)
    changed.update(root=tmp_path, freeze_path=fp, portfolio_path=pp)
    with pytest.raises(RuntimeError, match="twelve_valid_challenger_signal_weights"):
        evaluate(**changed)


def test_frozen_champion_scores_reproduce_selector_without_sdk_assumptions(specimen):
    """The actual decision can be replayed from its frozen champion score input."""
    from smart_primary_card_selector import PrimaryCardSelectorConfig, select_primary_card

    freeze = json.loads(specimen["freeze_path"].read_text(encoding="utf-8"))
    scores = freeze["champion"]["aggregate_scores"]
    card = specimen["primary_card"]
    saved = card["selector"]
    ranking = sorted(range(1, 61), key=lambda n: (-float(scores[str(n)]), n))
    replay = select_primary_card(
        scores,
        ranking60=ranking,
        config=PrimaryCardSelectorConfig(**saved["config"]),
    )
    # The frozen rescue was shadow-only: there were no effective score deltas.
    assert card["false_negative_rescue"]["nonzero_deltas"] == {}
    assert replay == saved
    assert replay["selected_numbers"] == card["numbers"]


def test_counterfactual_champion_score_reaches_card_without_freeze_mutation(specimen):
    """In-memory ablation checks score sensitivity; it is NOT predictive gain."""
    from smart_primary_card_selector import PrimaryCardSelectorConfig, select_primary_card

    saved_freeze_bytes = specimen["freeze_path"].read_bytes()
    freeze = json.loads(saved_freeze_bytes)
    scores = dict(freeze["champion"]["aggregate_scores"])
    card = specimen["primary_card"]
    # 60 is absent from the immutable 3070 primary card.
    assert 60 not in card["numbers"]
    scores["60"] = max(scores.values()) + 1_000_000.0
    ranking = sorted(range(1, 61), key=lambda n: (-float(scores[str(n)]), n))
    counterfactual = select_primary_card(
        scores,
        ranking60=ranking,
        config=PrimaryCardSelectorConfig(**card["selector"]["config"]),
    )
    assert counterfactual["selected_numbers"] != card["numbers"]
    assert specimen["freeze_path"].read_bytes() == saved_freeze_bytes


def test_forged_post_gate_still_marked_pass_is_rejected(specimen):
    changed = {**specimen, "post_gate": copy.deepcopy(specimen["post_gate"])}
    changed["post_gate"]["claim_boundary"] = "TAMPERED_WITHOUT_REHASH"
    assert changed["post_gate"]["status"] == "PASS"
    with pytest.raises(RuntimeError, match="gate_evidence_hashes_valid"):
        evaluate(**changed)


def test_forged_primary_card_metadata_is_rejected(specimen):
    changed = {**specimen, "primary_card": copy.deepcopy(specimen["primary_card"])}
    changed["primary_card"]["generated_utc"] = "2099-01-01T00:00:00Z"
    with pytest.raises(RuntimeError, match="primary_card_hash_valid"):
        evaluate(**changed)


def test_mismatched_epoch_identity_is_rejected(specimen):
    changed = {**specimen, "epoch_id": "WRONG_EPOCH"}
    with pytest.raises(RuntimeError, match="epoch_identity_matches_card"):
        evaluate(**changed)


def test_duplicate_native_skill_invocation_cannot_fake_full_coverage(specimen):
    changed = {**specimen, "post_gate": copy.deepcopy(specimen["post_gate"])}
    rows = changed["post_gate"]["native_invocations"]
    assert len(rows) == 37
    rows[-1] = copy.deepcopy(rows[0])
    # Even if an upstream gate claimed PASS, no repeated invocation covers a missing skill.
    with pytest.raises(RuntimeError, match="37_native_skill_aliases_invoked"):
        evaluate(**changed)


def test_real_3070_quality_to_weight_to_shadow_score_while_champion_remains_authorized(specimen):
    """Prove causal shadow scoring without asserting unearned predictive advantage."""
    import numpy as np
    from smart_signal_weights import dynamic_weights
    from smart_primary_card_selector import PrimaryCardSelectorConfig, select_primary_card

    frozen_bytes = specimen["freeze_path"].read_bytes()
    portfolio_bytes = specimen["portfolio_path"].read_bytes()
    freeze = json.loads(frozen_bytes)
    challenger = freeze["challenger"]
    metrics = copy.deepcopy(challenger["quality_metrics"])
    families = {k: v["family"] for k, v in challenger["raw_signals"].items()}
    weights, _ = dynamic_weights(metrics, families)
    assert len(weights) == 12
    assert max(abs(weights[k] - challenger["weights"][k]) for k in weights) < 1e-10

    def weighted_scores(w):
        out = np.zeros(60, dtype=float)
        for name, value in w.items():
            raw = challenger["raw_signals"][name]["values"]
            out += value * np.array([raw[str(i)] for i in range(1, 61)])
        return out

    original = weighted_scores(weights)
    expected = np.array([challenger["aggregate_scores"][str(i)] for i in range(1, 61)])
    assert np.allclose(original, expected, rtol=0.0, atol=1e-10)

    # Controlled intervention affects dynamic weights and shadow scores only.
    metrics["freq25"]["quality"] *= 0.1
    changed_weights, _ = dynamic_weights(metrics, families)
    assert abs(changed_weights["freq25"] - weights["freq25"]) > 1e-5
    assert np.max(np.abs(weighted_scores(changed_weights) - original)) > 1e-8

    assert freeze["production_switch_performed"] is False
    assert freeze["champion_remains_active"] is True
    scores = freeze["champion"]["aggregate_scores"]
    ranking = sorted(range(1, 61), key=lambda n: (-scores[str(n)], n))
    replay = select_primary_card(
        scores, ranking60=ranking,
        config=PrimaryCardSelectorConfig(**specimen["primary_card"]["selector"]["config"]),
    )
    assert replay == specimen["primary_card"]["selector"]
    assert specimen["freeze_path"].read_bytes() == frozen_bytes
    assert specimen["portfolio_path"].read_bytes() == portfolio_bytes
