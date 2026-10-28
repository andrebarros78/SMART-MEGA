"""Fail closed: retrospective matched holdout never authorizes production."""
from smart_ai_fine_tuning import adjudicate_selected


def test_retrospective_only_significance_never_promotes():
    lo = 2851
    baseline_trace = {str(i): 0 for i in range(lo, lo + 120)}
    candidate_trace = {str(i): (1 if i < lo + 30 else 0) for i in range(lo, lo + 120)}

    def row(name, trace, hits):
        is_base = name == "baseline"
        return {
            "candidate": {"candidate_id": name},
            "calibration": {"hits": 100},
            "validation": {"hits": 100 if is_base else 105},
            "global": {"hits": 100 if is_base else 130},
            "holdout": {"start": lo, "end": lo + 119, "n": 120, "hits": hits},
            "decisions": {"2851": [1, 2, 3, 4, 5, 6] if is_base else [1, 2, 3, 4, 5, 7]},
            "hit_trace": trace,
        }

    result = adjudicate_selected(
        [row("baseline", baseline_trace, 0), row("synthetic", candidate_trace, 30)],
        {"selected_candidate_id": "synthetic"},
    )
    assert result["holdout_statistical_evidence"]["verified"] is True
    assert result["holdout_statistical_evidence"]["prospective_superiority_proven"] is False
    assert result["promotion_authorized"] is False
    assert result["effective_candidate_id"] == "baseline"
