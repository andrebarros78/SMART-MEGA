"""G04/G05 paired research replay: scientific metrics without production authority."""
from pathlib import Path

import pytest

from smart_native_signal_research import make_contribution
from smart_native_research_metrics import (
    build_pre_result_paired_comparison,
    adjudicate_paired_comparison,
    hard_selection_brier,
    rank_comparison,
)


def _inputs(tmp_path: Path):
    path = tmp_path / "cutoff.bin"
    path.write_bytes(b"historical-only controlled fixture")
    a = make_contribution(
        "frontier_gap_hazard",
        {str(n): float(n) for n in range(1, 61)},
        data_path=path, target_contest=501, epoch_id="REPLAY-501",
    )
    b = make_contribution(
        "frontier_recent_lift",
        {str(n): float(61 - n) for n in range(1, 61)},
        data_path=path, target_contest=501, epoch_id="REPLAY-501",
    )
    # Kept as pre-result policy *reference*, not a real prediction performance claim.
    champion = {
        "top6": list(range(1, 7)),
        "ranking60": list(range(1, 61)),
        "aggregate_scores": {str(n): float(61-n)/60 for n in range(1,61)},
    }
    return path, [a,b], champion


def test_hard_selection_brier_is_explicit_binary_not_calibrated():
    actual = [1,2,3,4,5,6]
    assert hard_selection_brier(actual, actual) == pytest.approx(0.0)
    assert hard_selection_brier([7,8,9,10,11,12], actual) == pytest.approx(0.2)
    assert hard_selection_brier([1,2,3,7,8,9], actual) == pytest.approx(0.1)
    with pytest.raises(ValueError):
        hard_selection_brier([1,2,3,4,5,5], actual)


def test_rank_similarity_and_reversal():
    ranking = list(range(1,61))
    same = rank_comparison(ranking, ranking)
    assert same["spearman_rho"] == pytest.approx(1.0)
    assert same["mean_absolute_rank_shift"] == pytest.approx(0.0)
    reversed_ = rank_comparison(ranking, ranking[::-1])
    assert reversed_["spearman_rho"] == pytest.approx(-1.0)
    assert reversed_["mean_absolute_rank_shift"] > 20


def test_pre_result_arms_are_frozen_without_target_outcome(tmp_path):
    data, rows, champion = _inputs(tmp_path)
    weights = {rows[0]["producer_id"]: 0.08, rows[1]["producer_id"]: 0.07}
    comparison = build_pre_result_paired_comparison(
        rows, weights, champion, data_path=data, epoch_id="REPLAY-501",
        target_contest=501, champion_engine_sha256="b" * 64,
    )
    assert comparison["target_result_used"] is False
    assert comparison["production_authority"] is False
    assert comparison["champion"]["top6"] == champion["top6"]
    assert len(comparison["arms"]["full"]["ranking60"]) == 60
    assert len(comparison["arms"]["without_each_producer"]) == 2
    assert len(comparison["arms"]["without_each_family"]) >= 1
    assert len(comparison["arms"]["uniform"]["top6"]) == 6
    assert len(comparison["comparisons_vs_full"]["by_producer"]) == 2
    assert comparison == build_pre_result_paired_comparison(
        rows, weights, champion, data_path=data, epoch_id="REPLAY-501",
        target_contest=501, champion_engine_sha256="b" * 64,
    )


def test_post_result_requires_bound_verified_source(tmp_path):
    data, rows, champion = _inputs(tmp_path)
    weights = {rows[0]["producer_id"]: 0.08, rows[1]["producer_id"]: 0.07}
    frozen = build_pre_result_paired_comparison(
        rows, weights, champion, data_path=data, epoch_id="REPLAY-501",
        target_contest=501, champion_engine_sha256="b" * 64,
    )
    result = {
        "contest": 501, "numbers": [1,2,3,4,5,6],
        "source_sha256": "a"*64, "source_kind": "HISTORICAL_REPLAY",
    }
    with pytest.raises(ValueError, match="source"):
        adjudicate_paired_comparison(frozen, result, source_verified=False)
    adjudicated = adjudicate_paired_comparison(frozen, result, source_verified=True)
    assert adjudicated["pre_result_freeze_sha256"] == frozen["sha256"]
    assert adjudicated["champion"]["hits"] == 6
    assert adjudicated["champion"]["selection_brier"] == 0.0
    assert adjudicated["brier_semantics"] == "HARD_TOP6_BINARY_SELECTION_NOT_CALIBRATED_PROBABILITY"
    assert len(adjudicated["without_each_producer"]) == 2
    assert len(adjudicated["by_producer_contribution"]) == 2
    assert adjudicated["predictive_gain_proven"] is False
    assert adjudicated == adjudicate_paired_comparison(frozen, result, source_verified=True)


def test_pre_result_rejects_invalid_champion_and_future_contamination(tmp_path):
    data, rows, champion = _inputs(tmp_path)
    weights = {rows[0]["producer_id"]: 0.08, rows[1]["producer_id"]: 0.07}
    with pytest.raises(ValueError):
        build_pre_result_paired_comparison(
            rows, weights, {**champion, "top6":[1,1,2,3,4,5]},
            data_path=data, epoch_id="REPLAY-501", target_contest=501,
            champion_engine_sha256="b"*64,
        )
    with pytest.raises(ValueError):
        build_pre_result_paired_comparison(
            rows, weights, champion, data_path=data, epoch_id="REPLAY-501",
            target_contest=501, champion_engine_sha256="not-a-sha",
        )
