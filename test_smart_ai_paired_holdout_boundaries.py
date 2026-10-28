"""Paired holdout evidence must bind both candidates to the same declared window."""
import smart_ai_fine_tuning as ft


def _pair(count=100):
    contests = range(ft.HOLDOUT_START, ft.HOLDOUT_START + count)
    upper = ft.HOLDOUT_START + count - 1
    baseline = {
        "hit_trace": {str(k): 0 for k in contests},
        "holdout": {"start": ft.HOLDOUT_START, "end": upper,
                    "n": count, "hits": 0},
    }
    candidate = {
        "hit_trace": {str(k): 1 for k in contests},
        "holdout": {"start": ft.HOLDOUT_START, "end": upper,
                    "n": count, "hits": count},
    }
    return baseline, candidate


def test_rejects_inconsistent_declared_holdout_end_even_if_traces_match():
    baseline, candidate = _pair()
    baseline["holdout"]["end"] += 1
    result = ft._paired_holdout_evidence(baseline, candidate)
    assert result["verified"] is False, result


def test_rejects_inconsistent_declared_holdout_start_even_if_traces_match():
    baseline, candidate = _pair()
    baseline["holdout"]["start"] += 1
    result = ft._paired_holdout_evidence(baseline, candidate)
    assert result["verified"] is False, result


def test_rejects_holdout_summary_with_missing_boundaries():
    baseline, candidate = _pair()
    del baseline["holdout"]["end"]
    del candidate["holdout"]["end"]
    result = ft._paired_holdout_evidence(baseline, candidate)
    assert result["verified"] is False, result


def test_rejects_noninteger_summary_counts_without_coercion():
    baseline, candidate = _pair()
    baseline["holdout"]["hits"] = 0.8
    result = ft._paired_holdout_evidence(baseline, candidate)
    assert result["verified"] is False, result