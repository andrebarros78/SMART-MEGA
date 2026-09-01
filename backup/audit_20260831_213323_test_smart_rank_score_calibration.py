import math

import numpy as np
import pytest

import smart_v2_engine as e
from smart_rank_score_calibration import (
    N_NUMBERS, UNIFORM_PROB, RankScoreCalibrator, _pava_nonincreasing, brier_score,
)
from smart_signal_agent import SmartSignalAgent


def ranking():
    return list(range(1, 61))


def test_initial_calibration_is_uniform_and_sums_to_six():
    c = RankScoreCalibrator()
    probs, audit = c.predict(ranking())
    assert len(probs) == 60
    assert all(abs(v - 0.1) < 1e-12 for v in probs.values())
    assert abs(sum(probs.values()) - 6.0) < 1e-10
    assert audit['neutralized'] is True
    assert audit['monotonic_after_isotonic'] is True
    assert audit['mean_brier'] is None
    assert audit['aggregate_score_range'] is None


def test_online_updates_learn_rank_gradient_without_future_leakage():
    c = RankScoreCalibrator(strength=1.0, prior_strength=5.0)
    before, _ = c.predict(ranking())
    for _ in range(120):
        c.update(ranking(), [1, 2, 3, 4, 5, 6])
    after, audit = c.predict(ranking())
    assert before['1'] == before['60'] == 0.1
    assert after['1'] > after['60']
    arr = np.array(audit['calibrated_probability_by_rank'])
    assert np.all(arr[:-1] >= arr[1:] - 1e-15)
    assert abs(arr.sum() - 6.0) < 1e-10
    assert c.observations == 120


def test_zero_strength_neutralizes_even_after_learning():
    c = RankScoreCalibrator(strength=0.0)
    for _ in range(30):
        c.update(ranking(), [1, 2, 3, 4, 5, 6])
    probs, audit = c.predict(ranking())
    assert all(abs(v - UNIFORM_PROB) < 1e-12 for v in probs.values())
    assert audit['neutralized'] is True


def test_brier_and_update_accounting():
    c = RankScoreCalibrator(strength=0.0)
    probs, _ = c.predict(ranking())
    u = brier_score(probs, [1, 2, 3, 4, 5, 6])
    assert abs(u - 0.09) < 1e-12
    row = c.update(ranking(), [1, 2, 3, 4, 5, 6], probs)
    assert abs(row['brier'] - 0.09) < 1e-12
    assert abs(row['uniform_brier'] - 0.09) < 1e-12
    assert abs(row['delta_vs_uniform']) < 1e-12
    state = c.state()
    assert state['observations'] == 1
    assert state['mean_brier'] == pytest.approx(0.09)
    assert state['mean_uniform_brier'] == pytest.approx(0.09)
    assert len(state['sha256']) == 64


def test_update_can_generate_its_own_pre_result_probabilities():
    c = RankScoreCalibrator()
    out = c.update(ranking(), [7, 8, 9, 10, 11, 12])
    assert math.isfinite(out['brier'])
    assert c.observations == 1


def test_pava_enforces_nonincreasing_and_preserves_weighted_mean():
    vals = np.linspace(0.2, 0.01, 60)
    vals[10] = 0.25
    weights = np.arange(1, 61, dtype=float)
    out = _pava_nonincreasing(vals, weights)
    assert np.all(out[:-1] >= out[1:] - 1e-15)
    assert np.average(out, weights=weights) == pytest.approx(np.average(vals, weights=weights))


def test_constructor_and_pava_guards():
    with pytest.raises(ValueError, match='strength'):
        RankScoreCalibrator(strength=-0.1)
    with pytest.raises(ValueError, match='strength'):
        RankScoreCalibrator(strength=float('nan'))
    with pytest.raises(ValueError, match='prior_strength'):
        RankScoreCalibrator(prior_strength=0)
    with pytest.raises(ValueError, match='PAVA expects'):
        _pava_nonincreasing([1, 2], [1, 1])
    bad = np.ones(60); bad[0] = np.nan
    with pytest.raises(ValueError, match='PAVA inputs'):
        _pava_nonincreasing(bad, np.ones(60))
    with pytest.raises(ValueError, match='PAVA inputs'):
        _pava_nonincreasing(np.ones(60), np.r_[0.0, np.ones(59)])


def test_ranking_actual_probability_and_score_guards():
    c = RankScoreCalibrator()
    with pytest.raises(ValueError, match='ranking60'):
        c.predict(list(range(1, 60)))
    with pytest.raises(ValueError, match='six unique'):
        c.update(ranking(), [1, 1, 2, 3, 4, 5])
    with pytest.raises(ValueError, match='60 values'):
        c.predict(ranking(), {'1': 0.1})
    missing = {str(i): 0.1 for i in range(1, 61)}; missing.pop('60'); missing['x'] = 0.1
    with pytest.raises(ValueError, match='keys 1..60'):
        c.predict(ranking(), missing)
    nonfinite = {str(i): 0.1 for i in range(1, 61)}; nonfinite['3'] = float('inf')
    with pytest.raises(ValueError, match='finite'):
        c.predict(ranking(), nonfinite)
    with pytest.raises(ValueError, match='60 numbers'):
        brier_score({'1': 0.1}, [1, 2, 3, 4, 5, 6])
    p = {str(i): 0.1 for i in range(1, 61)}; p.pop('60'); p['x'] = 0.1
    with pytest.raises(ValueError, match='keys 1..60'):
        brier_score(p, [1, 2, 3, 4, 5, 6])
    p = {str(i): 0.1 for i in range(1, 61)}; p['5'] = 1.1
    with pytest.raises(ValueError, match='finite in'):
        brier_score(p, [1, 2, 3, 4, 5, 6])


def test_predict_records_aggregate_score_range():
    c = RankScoreCalibrator()
    scores = {str(i): float(i) / 60.0 for i in range(1, 61)}
    _, audit = c.predict(ranking(), scores)
    assert audit['aggregate_score_range'][0] == pytest.approx(1 / 60)
    assert audit['aggregate_score_range'][1] == pytest.approx(1.0)


def test_agent_integrates_rank_calibration_strictly_after_results():
    rng = np.random.default_rng(606)
    draws = np.array([np.sort(rng.choice(e.NUMBERS, 6, replace=False)) for _ in range(70)], dtype=int)
    contests = np.arange(1, 71)
    agent = SmartSignalAgent(start=30, calibration_strength=0.5)
    pred, back = agent.predict_next(draws, contests, target_contest=71)
    assert len(back['rows']) == 40
    assert agent.rank_calibrator.observations == 40
    assert pred.rank_score_calibration['observations'] == 40
    probs = pred.rank_score_calibration['probabilities_by_number']
    assert len(probs) == 60
    assert abs(sum(probs.values()) - 6.0) < 1e-8
    assert pred.rank_score_calibration['monotonic_after_isotonic'] is True
    state = agent.state_document()
    assert state['schema'] == 'SMART_SIGNAL_STATE_9'
    assert state['rank_score_calibration']['observations'] == 40
    # The row stores the prediction made before learning that same row's outcome.
    assert back['rows'][0]['rank_calibration_before_result']['observations'] == 0
    assert back['rows'][0]['rank_calibration_brier_after_result']['uniform_brier'] == pytest.approx(0.09)


def _frozen_calibration_snapshot():
    from test_smart_signal_interactions import make_snapshot
    snap = make_snapshot()
    snap['rank_score_calibration'] = {
        'strength': 0.0,
        'calibration_mode': 'NEUTRALIZED',
        'probabilities_by_number': {str(i): 0.1 for i in range(1, 61)},
        'monotonic_violations_before_isotonic': 3,
        'monotonic_after_isotonic': True,
    }
    return snap


def test_future_adjudication_appends_rank_calibration_evaluation(tmp_path):
    import json
    import pandas as pd
    import adjudicate_signal_challenger as adj
    import smart_champion_challenger as cc
    freeze = tmp_path / 'f.json'; freeze.write_text('{}'); fh = cc.sha256(freeze)
    fr = {'event_type':'FREEZE','target_contest':77,'freeze_file':str(freeze),'freeze_sha256':fh,
          'frozen_before_result':True,'causal_cutoff':True,'snapshot':_frozen_calibration_snapshot(),
          'champion_top6':[1,2,3,4,5,6],'challenger_top6':[1,2,3,4,5,7]}
    lp = tmp_path / 'ledger.json'; cc.write_ledger(lp, {'schema':cc.LEDGER_SCHEMA,'events':[fr]})
    row = {'Concurso':77}; row.update({f'Bola{i}':i for i in range(1,7)})
    result = tmp_path / 'result.xlsx'; pd.DataFrame([row]).to_excel(result,index=False)
    out = adj.adjudicate(result,77,lp)
    assert len(out['rank_score_calibration_evaluation_sha256']) == 64
    ledger = json.loads(lp.read_text())
    events = [x for x in ledger['events'] if x.get('event_type') == 'RANK_SCORE_CALIBRATION']
    assert len(events) == 1
    ev = events[0]
    assert ev['analysis']['brier'] == pytest.approx(0.09)
    assert ev['analysis']['delta_vs_uniform'] == pytest.approx(0.0)
    assert ev['policy_effect'] == 'POST_RESULT_EVALUATION_ONLY'


def test_adjudication_rejects_predated_rank_calibration_and_bad_frozen_probabilities(tmp_path):
    import pandas as pd
    import adjudicate_signal_challenger as adj
    import smart_champion_challenger as cc
    freeze = tmp_path / 'f.json'; freeze.write_text('{}'); fh = cc.sha256(freeze)
    snap = _frozen_calibration_snapshot()
    fr = {'event_type':'FREEZE','target_contest':78,'freeze_file':str(freeze),'freeze_sha256':fh,
          'frozen_before_result':True,'causal_cutoff':True,'snapshot':snap,
          'champion_top6':[1,2,3,4,5,6],'challenger_top6':[1,2,3,4,5,7]}
    row = {'Concurso':78}; row.update({f'Bola{i}':i for i in range(1,7)})
    result = tmp_path / 'result.xlsx'; pd.DataFrame([row]).to_excel(result,index=False)
    lp = tmp_path / 'predated.json'
    cc.write_ledger(lp, {'schema':cc.LEDGER_SCHEMA,'events':[fr,{'event_type':'RANK_SCORE_CALIBRATION','target_contest':78}]})
    with pytest.raises(ValueError, match='rank calibration cannot predate'):
        adj.adjudicate(result,78,lp)
    lp2 = tmp_path / 'bad.json'
    bad = dict(fr); bad['snapshot'] = _frozen_calibration_snapshot(); bad['snapshot']['rank_score_calibration']['probabilities_by_number'] = {'1':0.1}
    cc.write_ledger(lp2, {'schema':cc.LEDGER_SCHEMA,'events':[bad]})
    with pytest.raises(ValueError, match='60 probabilities'):
        adj.adjudicate(result,78,lp2)

