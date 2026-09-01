from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import smart_context_regime as cr
import smart_signal_agent as sa
import smart_signal_quality as sq
import smart_signal_weights as sw
import smart_v2_engine as e


def draws(seed=1, n=40):
    rng = np.random.default_rng(seed)
    return np.array([np.sort(rng.choice(e.NUMBERS, 6, replace=False)) for _ in range(n)], dtype=int)


def make_excel(path: Path, ds, contests=None):
    contests = np.arange(1, len(ds) + 1) if contests is None else np.asarray(contests)
    rows = []
    for c, d in zip(contests, ds):
        row = {'Concurso': int(c)}
        row.update({f'Bola{i}': int(d[i - 1]) for i in range(1, 7)})
        rows.append(row)
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def test_engine_hash_placebo_ablation_simulate_and_empty_walk(tmp_path):
    p = tmp_path / 'a.bin'; p.write_bytes(b'abc')
    assert e.sha256(p) == hashlib.sha256(b'abc').hexdigest()
    ds = draws(10, 18); cs = np.arange(1, 19)
    empty = e.walk_forward(ds, cs, start=len(ds))
    assert empty.rows == [] and empty.final_weights == {} and empty.family_weights == {}
    pl = e.placebo_walk(ds, start=10, seed=123)
    assert pl['expected'] == pytest.approx(8 * 0.6)
    abl = e.ablation(ds, cs, start=14)
    assert set(abl) == set(e.precompute_scores(e.onehot(ds)))
    mc = e.simulate_null(trials=2, steps=18, warmup=14, seed=123)
    assert mc['trials'] == 2 and mc['steps'] == 18


def test_engine_load_draws_additional_errors(tmp_path):
    p = tmp_path / 'bad.xlsx'
    pd.DataFrame([{'Concurso': 1, 'Bola1': 1}]).to_excel(p, index=False)
    with pytest.raises(ValueError, match='colunas'):
        e.load_draws(p)
    df = pd.DataFrame([{'Concurso': 'bad', **{f'Bola{i}': i for i in range(1, 7)}}])
    df.to_excel(p, index=False)
    with pytest.raises(ValueError, match='ausente ou nao inteiro'):
        e.load_draws(p)


def test_engine_regularize_edge_paths():
    # one expert above cap forces clipping and the no-free branch
    r = e.regularize({'a': 1.0}, prior_mix=0.0, cap=0.4)
    assert r['a'] == pytest.approx(1.0)
    # multiple experts force clipping and redistribution
    r = e.regularize({'a': .99, 'b': .005, 'c': .005}, prior_mix=0.0, cap=0.6)
    assert sum(r.values()) == pytest.approx(1.0)
    assert max(r.values()) <= 0.6000001
    assert e.family_of('freq25') == 'freq'
    assert e.family_of('ewma10') == 'ewma'


def test_engine_audit_executes_report_path(tmp_path, monkeypatch):
    ds = draws(11, 20); data = make_excel(tmp_path / 'd.xlsx', ds); out = tmp_path / 'audit.json'
    monkeypatch.setattr(e, 'ablation', lambda *a, **k: {'x': {'hits_without': 1, 'delta_full_minus_without': 0}})
    monkeypatch.setattr(e, 'simulate_null', lambda *a, **k: {'trials': 1, 'steps': 1, 'warmup': 0, 'mean_excess': 0.0, 'std_excess': 0.0, 'p95_excess': 0.0, 'p99_excess': 0.0, 'positive_excess_rate': 0.0, 'false_positive_rate_z_ge_2': 0.0})
    rep = e.audit(data, out, start=15, mc_trials=1)
    assert rep['schema'] == 'SMART_V2_AUDIT_2' and out.exists()


def test_quality_error_and_metric_paths():
    s = sq.SignalQualityState('x', 'freq')
    with pytest.raises(ValueError, match='60 values'):
        s.update_profile(np.zeros(59))
    bad = np.zeros(60); bad[0] = np.nan
    with pytest.raises(ValueError, match='non-finite'):
        s.update_profile(bad)
    with pytest.raises(ValueError, match='hits'):
        s.update(7)
    assert s.std_hits == 0.0
    s.update(0); s.update(2)
    assert s.std_hits > 0
    m = s.metrics(-2.0, freshness=2.0)
    assert m['redundancy_penalty'] == pytest.approx(0.05)
    assert m['freshness'] == pytest.approx(1.0)
    a = s.audit_state(0.5)
    assert a['name'] == 'x' and a['family'] == 'freq'


def test_weights_all_guard_paths():
    with pytest.raises(ValueError, match='mass'):
        sw._normalize({'a': 0.0})
    with pytest.raises(ValueError, match='empty'):
        sw.dynamic_weights({}, {})
    with pytest.raises(ValueError, match='missing factors'):
        sw.dynamic_weights({'a': {'utility': 1}}, {'a': 'freq'})
    assert sw._family_cap({'a': 1.0}, {'a': 'freq'}) == {'a': 1.0}
    capped = sw._family_cap({'a': .8, 'b': .1, 'c': .1}, {'a': 'freq', 'b': 'ewma', 'c': 'ewma'})
    assert capped['a'] <= sw.FAMILY_CAP + 1e-12
    # Path in which all members are over an artificially tiny cap.
    x = sw._expert_cap({'a': .5, 'b': .5}, cap=.2)
    assert sum(x.values()) == pytest.approx(1.0)


def test_context_all_paths():
    with pytest.raises(ValueError, match='six unique'):
        cr._onehot_draw([1, 2, 3, 4, 5, 5])
    assert cr.signal_memory('freq_global') == 1000
    assert cr.signal_memory('freq25') == 25
    assert cr.signal_memory('ewma10') == 10
    with pytest.raises(ValueError, match='unknown signal'):
        cr.signal_memory('x')
    eng = cr.ContextRegimeEngine()
    assert eng._score() == 0.0 and not eng.active
    assert eng.factor_for_signal('freq25') == 1.0
    # Stable biased regime then a shifted regime, sufficient for calibrated detector.
    rng = np.random.default_rng(55)
    w1 = np.ones(60); w1[:6] = 4
    w2 = np.ones(60); w2[30:36] = 4
    for _ in range(cr.REFERENCE_WINDOW):
        p = w1 / w1.sum(); eng.update(np.sort(rng.choice(e.NUMBERS, 6, replace=False, p=p)))
    for _ in range(cr.RECENT_WINDOW + 100):
        p = w2 / w2.sum(); eng.update(np.sort(rng.choice(e.NUMBERS, 6, replace=False, p=p)))
    assert eng.detection_count >= 1
    eng.cooldown = 2
    eng.update(np.sort(rng.choice(e.NUMBERS, 6, replace=False, p=w2/w2.sum())))
    assert eng.active
    assert eng.factor_for_signal('freq_global') == pytest.approx(0.35)
    assert eng.factor_for_signal('ewma10') > 0.35
    assert eng.metrics()['schema'] == 'SMART_CONTEXT_REGIME_1'


def test_agent_guard_and_default_paths(monkeypatch):
    ds = draws(77, 30); cs = np.arange(1, 31)
    a = sa.SmartSignalAgent(start=10)
    with pytest.raises(ValueError, match='length mismatch'):
        a.replay_history(ds, cs[:-1])
    with pytest.raises(ValueError, match='insufficient'):
        sa.SmartSignalAgent(start=30).replay_history(ds, cs)
    real_pre = e.precompute_scores
    monkeypatch.setattr(e, 'precompute_scores', lambda X: {})
    with pytest.raises(ValueError, match='missing expected signals'):
        a.replay_history(ds, cs)
    monkeypatch.setattr(e, 'precompute_scores', real_pre)
    pre = real_pre(e.onehot(ds))
    sc = {n: pre[n][10] for n in sa.SIGNAL_NAMES}
    p = sa.SmartSignalAgent(start=10)._predict_from_scores(sc, 10, 11, utility_base=None, penalties=None, audit_detail=False)
    assert p.raw_signals == {} and p.state_summary == {}
    with pytest.raises(ValueError, match='strictly after'):
        sa.SmartSignalAgent(start=10).predict_next(ds, cs, target_contest=30)


def test_agent_state_write(tmp_path):
    a = sa.SmartSignalAgent(start=5)
    doc = a.state_document('abc')
    p = tmp_path / 'state.json'
    h = sa.write_state(p, doc)
    assert len(h) == 64 and p.exists() and doc['context_regime']['causal'] is True




def test_family_cap_handles_zero_mass_other_family():
    from smart_signal_weights import _family_cap
    weights = {'a': 1.0, 'b': 0.0}
    families = {'a': 'freq', 'b': 'ewma'}
    out = _family_cap(weights, families, cap=0.70)
    assert abs(sum(out.values()) - 1.0) < 1e-12
    assert out['a'] <= 0.7000001
    assert out['b'] >= 0.2999999


def test_regularize_caps_and_redistributes_without_dead_break():
    out = e.regularize({'a': 0.9, 'b': 0.1}, prior_mix=0.0, cap=0.6)
    assert abs(sum(out.values()) - 1.0) < 1e-12
    assert out['a'] <= 0.6000001
    assert out['b'] >= 0.3999999

