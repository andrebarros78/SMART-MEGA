"""Regression: the final policy must include the last *observed* draw.

The last row of walk_forward is a pre-result prediction for that contest.
The returned final weights must instead represent the next contest's policy.
"""
import math

import numpy as np

import freeze_next_research
import smart_v2_engine as e
import smart_v2_next_policy as successor


def test_final_weights_replay_current_next_draw_policy():
    rng = np.random.default_rng(3096)
    draws = np.array(
        [np.sort(rng.choice(e.NUMBERS, size=6, replace=False)) for _ in range(135)],
        dtype=int,
    )
    contests = np.arange(1, len(draws) + 1)
    result = successor.walk_forward_next(draws, contests, start=60)
    next_policy = freeze_next_research.current_policy(draws, start=60)
    assert len(result.rows) == 75

    for key, weight in next_policy["expert_weights"].items():
        assert math.isclose(result.final_weights[key], weight, rel_tol=1e-12, abs_tol=1e-12)
    for key, weight in next_policy["family_weights"].items():
        assert math.isclose(result.family_weights[key], weight, rel_tol=1e-12, abs_tol=1e-12)

    assert math.isclose(sum(result.final_weights.values()), 1.0, abs_tol=1e-12)


def test_history_rows_remain_past_only_and_final_weights_are_next_period():
    rng = np.random.default_rng(20261031)
    draws = np.array(
        [np.sort(rng.choice(e.NUMBERS, size=6, replace=False)) for _ in range(120)],
        dtype=int,
    )
    draws[-1] = [3, 13, 23, 33, 43, 53]
    contests = np.arange(1, len(draws) + 1)
    result = successor.walk_forward_next(draws, contests, start=50)
    earlier = successor.walk_forward_next(draws[:-1], contests[:-1], start=50)

    assert result.rows[-1]["contest"] == 120
    for name, weight in earlier.final_weights.items():
        assert math.isclose(result.rows[-1]["weights"][name], weight, rel_tol=1e-12, abs_tol=1e-12)
    for name, weight in earlier.family_weights.items():
        assert math.isclose(result.rows[-1]["family_weights"][name], weight, rel_tol=1e-12, abs_tol=1e-12)
    assert result.rows[-1]["weights"] != result.final_weights


def test_versioned_successor_preserves_all_historical_prediction_rows():
    rng = np.random.default_rng(31415)
    draws = np.array([np.sort(rng.choice(e.NUMBERS, size=6, replace=False)) for _ in range(85)], dtype=int)
    contests = np.arange(1, 86)
    legacy = e.walk_forward(draws, contests, start=30)
    updated = successor.walk_forward_next(draws, contests, start=30)
    assert legacy.rows == updated.rows
    assert legacy.total_hits == updated.total_hits
    assert legacy.max_abs_corr == updated.max_abs_corr
    assert updated.final_weights != legacy.final_weights
    assert successor.next_policy_snapshot(draws, contests, start=30)["production_switch_authorized"] is False


def test_versioned_successor_rejects_invalid_experts_and_eta():
    rng = np.random.default_rng(777)
    draws = np.array([np.sort(rng.choice(e.NUMBERS, size=6, replace=False)) for _ in range(65)], dtype=int)
    contests = np.arange(1, 66)
    import pytest
    with pytest.raises(ValueError, match="distinct"):
        successor.walk_forward_next(draws, contests, start=30, allowed=["freq25", "freq25"])
    with pytest.raises(ValueError, match="positive"):
        successor.walk_forward_next(draws, contests, start=30, eta=float("nan"))
