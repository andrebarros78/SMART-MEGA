from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import smart_signal_attribution as a


def snapshot_three():
    values_a = {str(i): 0.0 for i in range(1, 61)}
    values_b = {str(i): 0.0 for i in range(1, 61)}
    values_c = {str(i): 0.0 for i in range(1, 61)}
    # A strongly supports actual 1..6.
    for i in range(1, 7):
        values_a[str(i)] = 1.0
    # B strongly supports wrong 7..12.
    for i in range(7, 13):
        values_b[str(i)] = 1.0
    # C duplicates B to exercise redundancy/coalitions.
    for i in range(7, 13):
        values_c[str(i)] = 0.9
    return {
        'raw_signals': {
            'a': {'values': values_a},
            'b': {'values': values_b},
            'c': {'values': values_c},
        },
        'weights': {'a': 0.40, 'b': 0.35, 'c': 0.25},
    }


def test_attribution_is_deterministic_and_explains_marginal_coalitions():
    snap = snapshot_three()
    r1 = a.analyze_attribution(snap, [1, 2, 3, 4, 5, 6])
    r2 = a.analyze_attribution(snap, [1, 2, 3, 4, 5, 6])
    assert r1['attribution_sha256'] == r2['attribution_sha256']
    assert r1['retroactive_optimization_prohibited'] is True
    assert r1['base']['hits'] in range(7)
    assert set(r1['per_signal']) == {'a', 'b', 'c'}
    assert r1['coalition_analysis']['coalitions_tested'] == 6
    assert r1['per_signal']['b']['redundancy']['most_redundant_peer'] == 'c'
    assert r1['per_signal']['c']['redundancy']['max_abs_correlation'] > 0.99
    assert len(r1['attribution_sha256']) == 64


def test_attribution_tracks_push_down_and_exact_score_effect():
    r = a.analyze_attribution(snapshot_three(), [1, 2, 3, 4, 5, 6])
    # Wrong-support signals must contain negative pairwise support for missed correct numbers when misses exist.
    if r['missed_actual_numbers']:
        pushed_b = r['per_signal']['b']['pushed_correct_numbers_down_vs_selected_wrong']
        assert pushed_b
        assert pushed_b[0]['against'][0]['weighted_support_correct_minus_wrong'] < 0
    assert set(r['per_signal']['a']['exact_score_contribution_actual']) == {str(i) for i in range(1, 7)}


def test_snapshot_validation_guards_and_private_helpers():
    snap = snapshot_three()
    with pytest.raises(ValueError, match='six unique'):
        a.analyze_attribution(snap, [1, 2, 3])
    with pytest.raises(ValueError, match='six unique'):
        a.analyze_attribution(snap, [1, 2, 3, 4, 5, 61])
    with pytest.raises(ValueError, match='>= 1'):
        a.analyze_attribution(snap, [1, 2, 3, 4, 5, 6], max_coalition_removal=0)
    with pytest.raises(ValueError, match='requires'):
        a._snapshot_arrays({})
    bad = json.loads(json.dumps(snap)); bad['weights'].pop('c')
    with pytest.raises(ValueError, match='identical'):
        a._snapshot_arrays(bad)
    bad = json.loads(json.dumps(snap)); bad['raw_signals']['a']['values'].pop('60')
    with pytest.raises(ValueError, match='exactly 60'):
        a._snapshot_arrays(bad)
    bad = json.loads(json.dumps(snap)); bad['raw_signals']['a']['values']['60'] = float('nan')
    with pytest.raises(ValueError, match='non-finite'):
        a._snapshot_arrays(bad)
    bad = json.loads(json.dumps(snap)); bad['weights']['a'] = -1
    with pytest.raises(ValueError, match='invalid weight'):
        a._snapshot_arrays(bad)
    bad = json.loads(json.dumps(snap)); bad['weights'] = {k: 0.0 for k in bad['weights']}
    with pytest.raises(ValueError, match='positive total'):
        a._snapshot_arrays(bad)
    arrays, weights = a._snapshot_arrays(snap)
    with pytest.raises(ValueError, match='remove all'):
        a._aggregate(arrays, weights, tuple(arrays))
    zero = dict(weights); zero['a'] = 1.0; zero['b'] = 0.0; zero['c'] = 0.0
    with pytest.raises(ValueError, match='zero weight mass'):
        a._aggregate(arrays, zero, ('a',))


def test_redundancy_handles_constant_vectors_and_evaluate():
    arrays = {'x': np.ones(60), 'y': np.ones(60), 'z': np.arange(60, dtype=float)}
    red = a._redundancy(arrays)
    assert red['x']['max_abs_correlation'] == 0.0
    ev = a._evaluate(np.zeros(60), {1, 2, 60})
    assert ev['top6'] == [1, 2, 3, 4, 5, 6]
    assert ev['hits'] == 2


def test_sha256_json_canonical_order():
    assert a.sha256_json({'a': 1, 'b': 2}) == a.sha256_json({'b': 2, 'a': 1})
