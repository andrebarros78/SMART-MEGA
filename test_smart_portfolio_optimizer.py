from pathlib import Path

import pytest

from smart_portfolio_optimizer import PortfolioConfig, optimize_from_freeze, optimize_portfolio


def _descending_scores():
    return {n: float(61 - n) for n in range(1, 61)}


def test_single_game_matches_score_top6():
    result = optimize_portfolio(
        _descending_scores(),
        PortfolioConfig(game_count=1, candidate_pool_size=12),
    )
    assert result["games"] == [[1, 2, 3, 4, 5, 6]]
    assert result["contract"]["predictive_scores_unchanged"] is True
    assert result["contract"]["portfolio_only"] is True


def test_multi_game_respects_overlap_and_adds_coverage():
    result = optimize_portfolio(
        _descending_scores(),
        PortfolioConfig(
            game_count=3,
            candidate_pool_size=14,
            max_pairwise_overlap=3,
            coverage_bonus=0.75,
        ),
    )
    assert len(result["games"]) == 3
    assert all(len(game) == 6 for game in result["games"])
    assert len({tuple(game) for game in result["games"]}) == 3
    assert result["metrics"]["max_pairwise_overlap_observed"] <= 3
    assert result["metrics"]["unique_number_count"] > 6


def test_optimizer_is_deterministic():
    cfg = PortfolioConfig(game_count=2, candidate_pool_size=12, max_pairwise_overlap=4, random_seed=7)
    first = optimize_portfolio(_descending_scores(), cfg)
    second = optimize_portfolio(_descending_scores(), cfg)
    assert first["games"] == second["games"]
    assert first["metrics"] == second["metrics"]


def test_invalid_overlap_rejected():
    with pytest.raises(ValueError):
        PortfolioConfig(max_pairwise_overlap=6).validate()


def test_3053_single_game_preserves_champion_top6():
    freeze = Path(__file__).with_name("SMART_3053_CHAMPION_CHALLENGER_FREEZE.json")
    result = optimize_from_freeze(
        freeze,
        PortfolioConfig(game_count=1, candidate_pool_size=18),
        head="champion",
    )
    assert result["source"]["target_contest"] == 3053
    assert result["games"] == [[10, 11, 27, 30, 38, 46]]
