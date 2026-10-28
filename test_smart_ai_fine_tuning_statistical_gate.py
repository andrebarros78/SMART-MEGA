"""Predictive model promotion must be supported by paired, untouched holdout evidence."""
from __future__ import annotations

import smart_ai_fine_tuning as tuning


def _candidate(candidate_id, calibration, validation, holdout_hits, hit_trace=None):
    base_card = [1, 2, 3, 4, 5, 6]
    altered_card = [1, 2, 3, 4, 5, 7]
    return {
        "candidate": {"candidate_id": candidate_id, "eta": 0.5,
                      "redundancy_threshold": 0.85, "meta_strength": 0.06},
        "calibration": {"hits": calibration, "n": 500, "mean_hits": calibration / 500},
        "validation": {"hits": validation, "n": 351, "mean_hits": validation / 351},
        "holdout": {"start": 2851, "end": 2950, "hits": holdout_hits, "n": 100, "mean_hits": holdout_hits / 100},
        "global": {"hits": calibration + validation + holdout_hits,
                   "n": 951, "mean_hits": (calibration + validation + holdout_hits) / 951},
        "decisions": {"2851": base_card if candidate_id == "baseline" else altered_card},
        "hit_trace": hit_trace,
    }


def _trace(base_hits, challenger_hits):
    assert len(base_hits) == len(challenger_hits) == 100
    return (
        {str(2851 + j): int(value) for j, value in enumerate(base_hits)},
        {str(2851 + j): int(value) for j, value in enumerate(challenger_hits)},
    )


def test_tiny_validation_advantage_is_not_enough_for_predictive_promotion():
    """Old code promoted +1 validation hit and 0 holdout gain with zero paired evidence."""
    base = _candidate("baseline", 100, 100, 60)
    challenger = _candidate("candidate", 101, 101, 60)
    selected = tuning.select_without_holdout([base, challenger])
    assert selected["selected_candidate_id"] == "candidate"
    outcome = tuning.adjudicate_selected([base, challenger], selected)
    assert outcome["promotion_authorized"] is False
    assert outcome["effective_candidate_id"] == "baseline"
    assert outcome["holdout_statistical_evidence"]["verified"] is False


def test_significant_paired_holdout_superiority_can_be_authorized():
    """A genuine predeclared candidate should be eligible when a clean 100-draw holdout proves a gain."""
    b, c = _trace([0] * 100, [1] * 75 + [0] * 25)
    base = _candidate("baseline", 290, 205, 0, b)
    challenger = _candidate("candidate", 300, 215, 75, c)
    outcome = tuning.adjudicate_selected(
        [base, challenger], tuning.select_without_holdout([base, challenger])
    )
    evidence = outcome["holdout_statistical_evidence"]
    assert outcome["retrospective_eligible"] is True
    assert outcome["promotion_authorized"] is False
    assert outcome["effective_candidate_id"] == "baseline"
    assert evidence["verified"] is True
    assert evidence["paired_contests"] == 100
    assert evidence["positive_differences"] == 75
    assert evidence["one_sided_p_value"] < 0.01


def test_one_extra_hit_in_holdout_is_not_statistically_sufficient():
    b, c = _trace([0] * 100, [1] * 26 + [0] * 74)
    # Replace 25 records to create a 26:25 paired win/loss with only one additional hit.
    b = {str(2851 + j): 1 if 26 <= j < 51 else 0 for j in range(100)}
    base = _candidate("baseline", 290, 205, 25, b)
    challenger = _candidate("candidate", 300, 215, 26, c)
    outcome = tuning.adjudicate_selected(
        [base, challenger], tuning.select_without_holdout([base, challenger])
    )
    assert outcome["promotion_authorized"] is False
    assert outcome["holdout_statistical_evidence"]["one_sided_p_value"] > 0.01


def test_incomplete_or_inconsistent_holdout_evidence_fails_closed():
    b, c = _trace([0] * 100, [1] * 75 + [0] * 25)
    bad = dict(c)
    del bad["2851"]
    base = _candidate("baseline", 290, 205, 0, b)
    challenger = _candidate("candidate", 300, 215, 75, bad)
    outcome = tuning.adjudicate_selected(
        [base, challenger], tuning.select_without_holdout([base, challenger])
    )
    assert outcome["promotion_authorized"] is False
    assert outcome["holdout_statistical_evidence"]["verified"] is False
