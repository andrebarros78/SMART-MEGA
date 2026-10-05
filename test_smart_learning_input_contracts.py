import numpy as np
import pytest

from smart_rank_score_calibration import RankScoreCalibrator
from smart_signal_marginal_utility import evaluate_incremental_utility
from smart_signal_quality import SignalQualityState


INVALID_RESULTS = [
    [True, 2, 3, 4, 5, 6],
    [np.bool_(True), 2, 3, 4, 5, 6],
    [1.9, 2, 3, 4, 5, 6],
    [float("nan"), 2, 3, 4, 5, 6],
    [float("inf"), 2, 3, 4, 5, 6],
    [1, 2, 3, 4, 5, 6, 6],
    [1, 2, 3, 4, 5],
    [1, 2, 3, 4, 5, 5],
    [1, 2, 3, 4, 5, 61],
]


@pytest.mark.parametrize("actual", INVALID_RESULTS)
def test_bad_outcome_cannot_update_calibration(actual):
    calibrator = RankScoreCalibrator()
    before = calibrator.state()
    with pytest.raises(ValueError):
        calibrator.update(list(range(1, 61)), actual)
    assert calibrator.state() == before


@pytest.mark.parametrize("actual", INVALID_RESULTS)
def test_bad_outcome_cannot_create_marginal_utility_evidence(actual):
    scores = {"a": np.arange(60, dtype=float), "b": np.arange(59, -1, -1, dtype=float)}
    with pytest.raises(ValueError):
        evaluate_incremental_utility(scores, {"a": 0.6, "b": 0.4}, actual)


@pytest.mark.parametrize("first", [True, np.bool_(True), 1.9])
def test_coerced_ranking_cannot_update_calibration(first):
    calibrator = RankScoreCalibrator()
    ranking = list(range(1, 61))
    ranking[0] = first
    before = calibrator.state()
    with pytest.raises(ValueError):
        calibrator.update(ranking, [1, 2, 3, 4, 5, 6])
    assert calibrator.state() == before


@pytest.mark.parametrize("hits", [True, np.bool_(True), 6.9, 2.5, -0.1, 7, float("inf"), float("nan"), "3"])
def test_invalid_hit_count_cannot_mutate_signal_quality(hits):
    state = SignalQualityState("freq25", "freq")
    before = state.audit_state()
    with pytest.raises(ValueError):
        state.update(hits)
    assert state.audit_state() == before


def test_numpy_integral_outcomes_remain_supported():
    actual = np.arange(1, 7, dtype=np.int64)
    ranking = np.arange(1, 61, dtype=np.int64)
    calibrator = RankScoreCalibrator()
    row = calibrator.update(ranking, actual)
    assert row["brier"] == pytest.approx(0.09)
    assert calibrator.observations == 1
    scores = {"a": np.arange(60, dtype=float)}
    report = evaluate_incremental_utility(scores, {"a": 1.0}, actual)
    assert report["actual_numbers"] == list(range(1, 7))
    quality = SignalQualityState("freq25", "freq")
    quality.update(np.int64(6))
    assert quality.n == 1 and quality.mean_hits == 6.0
