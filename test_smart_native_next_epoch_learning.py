"""Controlled G05 research learning tests; not a prediction-performance claim."""
from pathlib import Path
import pytest

from smart_native_signal_research import (
    ADJ_SCHEMA, build_research_challenger, hash_document,
    make_contribution, next_epoch_research_weights,
)


def _case(tmp_path: Path):
    data = tmp_path / "cutoff_only.bin"
    data.write_bytes(b"controlled snapshot with no next result")
    ids = ("frontier_gap_hazard", "frontier_recent_lift", "frontier_weekday_bayes")
    # Use independent vectors: alias-equivalent signals must be rejected
    # by the consumer, not accepted as a valid learning test fixture.
    vectors = {
        ids[0]: {str(i): float(i / 60) for i in range(1, 61)},
        ids[1]: {str(i): float((61 - i) / 60) for i in range(1, 61)},
        ids[2]: {str(i): 0.0 for i in range(1, 61)},
    }
    signals = [make_contribution(
        name, vectors[name],
        data_path=data, target_contest=200, epoch_id="EPOCH-200",
    ) for name in ids]
    weights = {ids[0]: 0.05, ids[1]: 0.1, ids[2]: 0.0}
    frozen = build_research_challenger(signals, weights)
    receipt = hash_document({
        "schema": ADJ_SCHEMA,
        "research_only": True,
        "historical_replay": True,
        "target_contest": 200,
        "freeze_sha256": frozen["sha256"],
        "result_source_verified": True,  # controlled simulated receipt, NOT real official evidence
        "learning_update": {
            "from_epoch": "EPOCH-200",
            "to_next_epoch": "AFTER-200",
            "promotion_authorized": False,
            "weights_effective_next": weights,
            "proposed_centered_logits": {
                ids[0]: 0.3, ids[1]: -0.3, ids[2]: 0.0,
            },
        },
    })
    return frozen, receipt, weights


def test_next_epoch_only_after_authorized_prior_result(tmp_path):
    frozen, receipt, weights = _case(tmp_path)
    observed = next_epoch_research_weights(
        frozen, receipt, next_target_contest=201, research_authorized=True
    )
    assert observed == next_epoch_research_weights(
        frozen, receipt, next_target_contest=201, research_authorized=True
    )
    following = observed["weights_effective_next_research"]
    assert following["frontier_gap_hazard"] > weights["frontier_gap_hazard"]
    assert following["frontier_recent_lift"] < weights["frontier_recent_lift"]
    assert following["frontier_weekday_bayes"] == 0.0
    assert sum(following.values()) == pytest.approx(0.15)
    assert observed["research_only"] is True
    assert observed["production_authority"] is False
    assert observed["prospective_advantage_proven"] is False


def test_next_epoch_fails_closed_when_authority_or_source_missing(tmp_path):
    frozen, receipt, weights = _case(tmp_path)
    with pytest.raises(PermissionError, match="authorization"):
        next_epoch_research_weights(
            frozen, receipt, next_target_contest=201, research_authorized=False
        )
    with pytest.raises(ValueError, match="exactly one"):
        next_epoch_research_weights(
            frozen, receipt, next_target_contest=202, research_authorized=True
        )
    bad = hash_document({**receipt, "result_source_verified": False})
    with pytest.raises(ValueError, match="verified result"):
        next_epoch_research_weights(
            frozen, bad, next_target_contest=201, research_authorized=True
        )
    forged = hash_document({**receipt, "freeze_sha256": "0" * 64})
    with pytest.raises(ValueError, match="verified result"):
        next_epoch_research_weights(
            frozen, forged, next_target_contest=201, research_authorized=True
        )
