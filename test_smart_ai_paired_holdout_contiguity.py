import smart_ai_fine_tuning as ft


def _synthetic_pair(*, missing_one):
    contests = list(range(ft.HOLDOUT_START, ft.HOLDOUT_START + 101))
    if missing_one:
        contests.remove(ft.HOLDOUT_START + 50)
    end = ft.HOLDOUT_START + 100
    baseline = {
        "hit_trace": {str(i): 0 for i in contests},
        "holdout": {"start": ft.HOLDOUT_START, "end": end,
                    "n": len(contests), "hits": 0},
    }
    candidate = {
        "hit_trace": {str(i): 1 for i in contests},
        "holdout": {"start": ft.HOLDOUT_START, "end": end,
                    "n": len(contests), "hits": len(contests)},
    }
    return baseline, candidate


def test_paired_holdout_rejects_missing_internal_contest():
    baseline, candidate = _synthetic_pair(missing_one=True)
    result = ft._paired_holdout_evidence(baseline, candidate)
    assert result["verified"] is False, result


def test_paired_holdout_accepts_complete_synthetic_contests():
    baseline, candidate = _synthetic_pair(missing_one=False)
    result = ft._paired_holdout_evidence(baseline, candidate)
    assert result["verified"] is True, result