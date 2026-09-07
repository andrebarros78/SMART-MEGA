import json
import math

import numpy as np
import pytest

import smart_b7_predictive_edge as b7


def _probs_uniform():
    return {str(i): 0.1 for i in range(1, 61)}


def _probs_good(actual):
    p = {str(i): 0.05 for i in range(1, 61)}
    # 54*0.05 = 2.7; remaining 3.3 / 6 = .55 on actual => sum 6
    for n in actual:
        p[str(n)] = 0.55
    return p


def test_uniform_scores_are_exact_baseline():
    actual = [1, 2, 3, 4, 5, 6]
    y = b7._actual_vector(actual)
    p = b7.probability_vector(_probs_uniform())
    assert b7.brier_score(p, y) == pytest.approx(0.09)
    assert b7.binary_log_loss(p, y) == pytest.approx(-(0.1*math.log(.1)+.9*math.log(.9)))


def test_candidate_edge_positive_when_probabilities_concentrate_on_outcome():
    actual = [1, 2, 3, 4, 5, 6]
    p = _probs_good(actual)
    y = b7._actual_vector(actual)
    row = {"contest": 100, "cutoff_contest": 99, "hits": 6, "probabilities": p,
           "brier": b7.brier_score(b7.probability_vector(p), y)}
    result = b7.audit_candidate([row], {100: actual})
    assert result["brier_edge_pct"] > 0
    assert result["log_loss_edge_pct"] > 0
    assert result["prospective_edge_pct"] > 0
    assert result["proper_scores_both_better_than_uniform"] is True


def test_brier_must_reproduce_from_retained_probabilities():
    actual = [1, 2, 3, 4, 5, 6]
    row = {"contest": 100, "cutoff_contest": 99, "hits": 0, "probabilities": _probs_uniform(), "brier": 0.01}
    with pytest.raises(ValueError, match="reproduce"):
        b7.audit_candidate([row], {100: actual})


def test_causal_cutoff_is_mandatory():
    actual = [1, 2, 3, 4, 5, 6]
    row = {"contest": 100, "cutoff_contest": 100, "hits": 0, "probabilities": _probs_uniform(), "brier": 0.09}
    with pytest.raises(ValueError, match="causal cutoff"):
        b7.audit_candidate([row], {100: actual})
