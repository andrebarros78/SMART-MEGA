from __future__ import annotations

import numpy as np

from smart_frontier_signal_lab import (
    CANDIDATES,
    FrontierState,
    holm_adjust,
    scores_to_probabilities,
    sign_flip_pvalue,
)


def draw(*values):
    return np.asarray(values, dtype=int)


def trained_state():
    state = FrontierState(recent_window=4)
    state.update(draw(1, 2, 3, 4, 5, 6), 0)
    state.update(draw(7, 8, 9, 10, 11, 12), 2)
    state.update(draw(1, 13, 14, 15, 16, 17), 5)
    return state


def test_frontier_prediction_contains_all_independent_families():
    document = trained_state().predict(0).document()
    assert set(document) == set(CANDIDATES)
    assert len({row["family"] for row in document.values()}) == len(CANDIDATES)
    for row in document.values():
        assert len(row["top6"]) == 6
        assert len(set(row["top6"])) == 6
        assert abs(row["probability_sum"] - 6.0) < 1e-8
        assert row["production_authority"] is False


def test_state_is_causal_until_future_is_observed():
    left = trained_state()
    right = trained_state()
    before_left = left.predict(3).document()
    before_right = right.predict(3).document()
    right.update(draw(40, 41, 42, 43, 44, 45), 3)
    assert before_left == before_right
    assert right.predict(3).document() != before_right


def test_scores_to_probabilities_is_bounded_and_sums_to_six():
    values = np.zeros(60)
    values[0] = 1000000
    probabilities = scores_to_probabilities(values)
    assert np.all(probabilities >= 0.0)
    assert np.all(probabilities <= 1.0)
    assert abs(float(probabilities.sum()) - 6.0) < 1e-8


def test_sign_flip_does_not_claim_nonpositive_advantage():
    assert sign_flip_pvalue([0, -1, 0, 1], seed=1, replications=100) == 1.0


def test_holm_adjustment_controls_family_and_is_monotone():
    adjusted = holm_adjust({"a": 0.001, "b": 0.02, "c": 0.2})
    assert adjusted["a"] == 0.003
    assert adjusted["b"] >= adjusted["a"]
    assert adjusted["c"] >= adjusted["b"]


def test_probability_and_state_guards():
    import pytest
    from smart_frontier_signal_lab import _minmax, brier, sign_flip_pvalue

    assert np.all(_minmax(np.ones(60)) == 0.0)
    bad = np.ones(60)
    bad[0] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        _minmax(bad)
    state = FrontierState()
    with pytest.raises(ValueError, match="weekday"):
        state.predict(7)
    with pytest.raises(ValueError, match="six unique"):
        state.update(draw(1, 1, 2, 3, 4, 5), 0)
    assert sign_flip_pvalue([], seed=1, replications=10) == 1.0
    assert 0.0 < sign_flip_pvalue([1, 1, 1], seed=1, replications=100) <= 1.0
    assert brier(np.full(60, 0.1), draw(1, 2, 3, 4, 5, 6)) == pytest.approx(0.09)


def test_split_and_summary_boundaries():
    from smart_frontier_signal_lab import _split_name, _summarize

    assert _split_name(2200) == "calibration"
    assert _split_name(2201) == "validation"
    assert _split_name(2701) == "holdout"
    assert _summarize([]) == {"n": 0}
    row = {"hits": 6, "champion_hits": 1, "delta_hits": 5, "brier": 0.01, "novelty": 1.0}
    summary = _summarize([row])
    assert summary["events_3plus"] == summary["events_4plus"] == summary["events_5plus"] == summary["events_6"] == 1


def test_run_historical_executes_causal_walk(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import pandas as pd
    import smart_frontier_signal_lab as module

    data = tmp_path / "tiny.xlsx"
    pd.DataFrame({"Data do Sorteio": ["01/01/2026", "02/01/2026", "03/01/2026", "04/01/2026"]}).to_excel(data, index=False)
    draws = np.asarray([
        [1, 2, 3, 4, 5, 6],
        [7, 8, 9, 10, 11, 12],
        [13, 14, 15, 16, 17, 18],
        [19, 20, 21, 22, 23, 24],
    ])
    contests = np.asarray([2200, 2201, 2701, 2702])
    monkeypatch.setattr(module.e, "load_draws", lambda path: (draws, contests))
    rows = [{"contest": int(contests[i]), "top6": draws[i].tolist(), "hits": 6} for i in range(1, 4)]
    monkeypatch.setattr(module.e, "walk_forward", lambda d, c, start: SimpleNamespace(rows=rows))
    result, state, frame = module.run_historical(data, start_index=1)
    assert result["evaluated_contests"] == 3
    assert result["future_leakage"] is False
    assert state.step == 4
    assert len(frame) == 4
    assert all(len(candidate_rows) == 3 for candidate_rows in result["rows"].values())


def test_run_historical_rejects_date_draw_mismatch(monkeypatch, tmp_path):
    import pandas as pd
    import pytest
    import smart_frontier_signal_lab as module

    data = tmp_path / "tiny.xlsx"
    pd.DataFrame({"Data do Sorteio": ["01/01/2026"]}).to_excel(data, index=False)
    monkeypatch.setattr(module.e, "load_draws", lambda path: (np.asarray([[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]]), np.asarray([1, 2])))
    with pytest.raises(ValueError, match="lengths differ"):
        module.run_historical(data, 1)


def test_register_and_freeze_shadow_contract(tmp_path):
    import json
    import pytest
    from smart_frontier_signal_lab import freeze_shadow, register_candidates, sha256_json

    data = tmp_path / "data.bin"
    data.write_bytes(b"data")
    report = tmp_path / "report.json"
    report.write_text("{}", encoding="utf-8")
    registry = tmp_path / "registry.json"
    first = register_candidates(registry, 9)
    second = register_candidates(registry, 9)
    assert first["snapshot"]["candidates"].keys() == second["snapshot"]["candidates"].keys()

    freeze_path = tmp_path / "freeze.json"
    freeze = freeze_shadow(trained_state(), data, 10, "05/09/2026", report, freeze_path, registry)
    assert freeze["status"] == "FROZEN_SHADOW_ONLY"
    canonical = dict(freeze)
    canonical.pop("sha256")
    assert freeze["sha256"] == sha256_json(canonical)
    with pytest.raises(FileExistsError, match="overwrite"):
        freeze_shadow(trained_state(), data, 10, "05/09/2026", report, freeze_path, registry)
