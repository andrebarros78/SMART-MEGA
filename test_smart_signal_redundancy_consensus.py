from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import smart_v2_engine as e
from smart_signal_agent import SmartSignalAgent
from smart_signal_redundancy_consensus import (
    DEFAULT_CORRELATION_THRESHOLD,
    _components,
    _correlation_matrix,
    consensus_penalties,
    sha256_json,
)
from smart_signal_weights import dynamic_weights


def _vec(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(size=60)


def test_consensus_validation_and_determinism():
    with pytest.raises(ValueError, match='empty'):
        consensus_penalties({})
    with pytest.raises(ValueError, match='threshold'):
        consensus_penalties({'a': _vec(1)}, threshold=1.0)
    with pytest.raises(ValueError, match='60 finite'):
        consensus_penalties({'a': np.ones(59)})
    with pytest.raises(ValueError, match='match'):
        consensus_penalties({'a': _vec(1)}, {'b': 1.0})
    with pytest.raises(ValueError, match='positive mass'):
        consensus_penalties({'a': _vec(1)}, {'a': 0.0})
    scores = {'a': _vec(2), 'b': _vec(3), 'c': _vec(4)}
    p1, a1 = consensus_penalties(scores, threshold=0.9)
    p2, a2 = consensus_penalties(scores, threshold=0.9)
    assert p1 == p2
    assert a1 == a2
    assert a1['sha256'] == sha256_json({k: v for k, v in a1.items() if k != 'sha256'})


def test_correlation_components_and_constant_signal_branch():
    a = np.arange(60, dtype=float)
    b = a.copy()
    c = -a.copy()
    d = np.ones(60)
    arrays = {'a': a, 'b': b, 'c': c, 'd': d}
    corr = _correlation_matrix(arrays)
    assert corr['a']['b'] == pytest.approx(1.0)
    assert corr['a']['c'] == pytest.approx(-1.0)
    assert corr['a']['d'] == 0.0
    groups = _components(corr, 0.9)
    assert ['a', 'b', 'c'] in groups
    assert ['d'] in groups


def test_duplicate_votes_are_penalized_and_growth_is_sublinear():
    independent = _vec(10)
    duplicate = _vec(11)
    scores = {f'dup{i}': duplicate.copy() for i in range(4)}
    scores['independent'] = independent
    base = {n: 1.0 / len(scores) for n in scores}
    penalties, audit = consensus_penalties(scores, base, threshold=0.9)
    dup_penalties = [penalties[f'dup{i}'] for i in range(4)]
    assert max(dup_penalties) == pytest.approx(min(dup_penalties))
    assert penalties['independent'] > dup_penalties[0]
    assert any(set(row['members']) == {f'dup{i}' for i in range(4)} for row in audit['clusters'])

    naive_metrics = {n: {'utility': 1, 'quality': 1, 'confidence': 1, 'context': 1, 'redundancy_penalty': 1} for n in scores}
    penalized_metrics = {n: {'utility': 1, 'quality': 1, 'confidence': 1, 'context': 1, 'redundancy_penalty': penalties[n]} for n in scores}
    fam = {n: 'x' for n in scores}
    naive, _ = dynamic_weights(naive_metrics, fam)
    adjusted, _ = dynamic_weights(penalized_metrics, fam)
    naive_dup_mass = sum(naive[f'dup{i}'] for i in range(4))
    adjusted_dup_mass = sum(adjusted[f'dup{i}'] for i in range(4))
    assert naive_dup_mass == pytest.approx(0.8)
    assert adjusted_dup_mass < naive_dup_mass
    assert adjusted['independent'] > naive['independent']


def test_independent_signals_remain_singletons_and_not_overpenalized():
    scores = {f's{i}': _vec(100 + i) for i in range(4)}
    penalties, audit = consensus_penalties(scores, threshold=0.9)
    assert all(row['size'] == 1 for row in audit['clusters'])
    assert all(0.4 <= penalties[n] <= 1.0 for n in scores)


def test_agent_exposes_effective_p03_audit_and_default_threshold():
    rng = np.random.default_rng(303)
    draws = np.array([np.sort(rng.choice(e.NUMBERS, 6, replace=False)) for _ in range(180)], dtype=int)
    contests = np.arange(1, len(draws) + 1)
    agent = SmartSignalAgent(start=50)
    pred, _ = agent.predict_next(draws, contests, target_contest=181)
    assert pred.redundancy_consensus['schema'] == 'SMART_FALSE_CONSENSUS_REDUNDANCY_1'
    assert pred.redundancy_consensus['threshold'] == DEFAULT_CORRELATION_THRESHOLD == 0.90
    assert pred.redundancy_consensus['penalties']
    for n in pred.weights:
        assert pred.quality_metrics[n]['redundancy_penalty'] == pytest.approx(pred.redundancy_consensus['penalties'][n])


def test_predeclared_threshold_validation_rejects_exploratory_overfit():
    path = Path('SMART_P03_THRESHOLD_VALIDATION.json')
    if not path.exists():
        pytest.skip('validation artifact created during P03 execution')
    obj = json.loads(path.read_text(encoding='utf-8'))
    assert obj['legacy']['holdout_hits'] == 541
    assert obj['candidates']['0.9']['holdout_hits'] >= obj['legacy']['holdout_hits']
    assert obj['candidates']['0.95']['holdout_hits'] < obj['legacy']['holdout_hits']
