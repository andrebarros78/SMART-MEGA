import json
from pathlib import Path

import pytest

from smart_portfolio_optimizer import PortfolioConfig
from smart_portfolio_pipeline import CANONICAL_PORTFOLIO_CONFIG, build_portfolio_package
from smart_portfolio_backtest import _game_metrics, _uniform_baseline


def _freeze(tmp_path: Path):
    scores = {str(i): float(61 - i) for i in range(1, 61)}
    payload = {
        "target_contest": 10,
        "cutoff_contest": 9,
        "frozen_before_result": True,
        "champion": {"top6": [1, 2, 3, 4, 5, 6], "aggregate_scores": scores},
    }
    path = tmp_path / "freeze.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_pipeline_preserves_single_game_and_proves_small_optimum(tmp_path):
    path = _freeze(tmp_path)
    cfg = PortfolioConfig(game_count=2, candidate_pool_size=9, max_pairwise_overlap=3, coverage_bonus=2.0, time_limit_seconds=5)
    result = build_portfolio_package(path, config=cfg)
    assert result["status"] == "PASS"
    assert result["checks"]["single_game_preserved"] is True
    assert result["portfolio"]["solver_status"] == "OPTIMAL"
    assert result["portfolio"]["metrics"]["max_pairwise_overlap_observed"] <= 3


def test_pipeline_rejects_retrospective_freeze(tmp_path):
    path = _freeze(tmp_path)
    payload = json.loads(path.read_text())
    payload["frozen_before_result"] = False
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        build_portfolio_package(path, config=PortfolioConfig(game_count=1, candidate_pool_size=6))


def test_uniform_baseline_has_known_mean_hits():
    baseline = _uniform_baseline(4, 100)
    assert baseline["expected_mean_hits_per_game"] == 0.6
    assert baseline["expected_sum_game_hits"] == pytest.approx(240.0)
    assert baseline["expected_contests_any_3plus_independent_games"] > 0


def test_game_metrics_counts_union_and_best():
    m = _game_metrics([[1,2,3,4,5,6],[4,5,6,7,8,9]], [1,2,3,7,8,9])
    assert m["game_hits"] == [3,3]
    assert m["sum_game_hits"] == 6
    assert m["best_game_hits"] == 3
    assert m["union_hits"] == 6
    assert m["any_3plus"] == 1


def test_canonical_policy_is_frozen_contract():
    assert CANONICAL_PORTFOLIO_CONFIG.game_count == 4
    assert CANONICAL_PORTFOLIO_CONFIG.candidate_pool_size == 12
    assert CANONICAL_PORTFOLIO_CONFIG.max_pairwise_overlap == 2
    assert CANONICAL_PORTFOLIO_CONFIG.require_full_candidate_coverage is True
    assert CANONICAL_PORTFOLIO_CONFIG.min_number_exposure == 2
    assert CANONICAL_PORTFOLIO_CONFIG.max_number_exposure == 2


