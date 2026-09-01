from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

import smart_v2_engine as e

SCHEMA = 'SMART_SIGNAL_INTERACTIONS_1'
EWMA_ALPHA = 0.05
CONFIDENCE_HALF_LIFE = 100.0
MAX_GROUP_ORDER = 3


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _actual(actual_numbers) -> list[int]:
    actual = sorted(int(x) for x in actual_numbers)
    if len(actual) != 6 or len(set(actual)) != 6 or actual[0] < 1 or actual[-1] > 60:
        raise ValueError('actual_numbers must contain six unique numbers in 1..60')
    return actual


def _inputs(scores: dict[str, Any], weights: dict[str, float]):
    if not isinstance(scores, dict) or not scores or set(scores) != set(weights):
        raise ValueError('scores and weights must be non-empty with identical ids')
    arrays = {}
    parsed = {}
    for name in sorted(scores):
        arr = np.asarray(scores[name], dtype=float)
        if arr.shape != (60,) or not np.all(np.isfinite(arr)):
            raise ValueError(f'{name}: expected 60 finite values')
        w = float(weights[name])
        if not math.isfinite(w) or w < 0:
            raise ValueError(f'invalid weight for {name}')
        arrays[name] = arr
        parsed[name] = w
    z = sum(parsed.values())
    if z <= 0:
        raise ValueError('weights must have positive mass')
    return arrays, {n: w / z for n, w in parsed.items()}


def _aggregate(arrays, weights, removed=()):
    removed = set(removed)
    kept = [n for n in arrays if n not in removed]
    if not kept:
        raise ValueError('cannot remove all signals')
    mass = sum(weights[n] for n in kept)
    if mass <= 0:
        raise ValueError('remaining signals have zero weight mass')
    out = np.zeros(60, dtype=float)
    for n in kept:
        out += weights[n] / mass * arrays[n]
    return out


def _hits(score, actual):
    top, _ = e.rank_top6(score)
    return int(len(set(top) & set(actual))), [int(x) for x in top]


def analyze_interactions(scores: dict[str, Any], weights: dict[str, float], actual_numbers,
                         max_group_order: int = MAX_GROUP_ORDER) -> dict[str, Any]:
    actual = _actual(actual_numbers)
    arrays, weights = _inputs(scores, weights)
    names = sorted(arrays)
    if max_group_order < 2 or max_group_order > 3:
        raise ValueError('max_group_order must be 2 or 3')
    full_hits, full_top6 = _hits(_aggregate(arrays, weights), actual)
    single = {}
    for n in names:
        h, top = _hits(_aggregate(arrays, weights, (n,)), actual)
        single[n] = {'hits_without': h, 'delta_hits': full_hits - h, 'top6_without': top}
    pairs = {}
    for a, b in itertools.combinations(names, 2):
        key = f'{a}|{b}'
        if len(names) <= 2:
            pairs[key] = {'signals':[a,b], 'available':False,
                          'reason':'leave-two-out undefined when pair is the full ensemble'}
            continue
        h_ab, _ = _hits(_aggregate(arrays, weights, (a, b)), actual)
        joint = full_hits - h_ab
        interaction = joint - single[a]['delta_hits'] - single[b]['delta_hits']
        pairs[key] = {'signals': [a, b], 'available':True, 'hits_without_pair': h_ab,
                      'joint_delta_hits': int(joint), 'interaction_delta_hits': int(interaction)}
    triples = {}
    if max_group_order >= 3 and len(names) > 3:
        for group in itertools.combinations(names, 3):
            h_g, _ = _hits(_aggregate(arrays, weights, group), actual)
            joint = full_hits - h_g
            pair_sum = sum(pairs['|'.join(sorted(pair))]['interaction_delta_hits']
                           for pair in itertools.combinations(group, 2))
            single_sum = sum(single[n]['delta_hits'] for n in group)
            pure = joint - single_sum - pair_sum
            key = '|'.join(group)
            triples[key] = {'signals': list(group), 'hits_without_group': h_g,
                            'joint_delta_hits': int(joint), 'pure_interaction_delta_hits': int(pure)}
    payload = {'schema': SCHEMA, 'actual_numbers': actual, 'full_hits': full_hits, 'full_top6': full_top6,
               'single_effects': single, 'pair_interactions': pairs, 'triple_interactions': triples,
               'weight_effect_enabled': False,
               'causal_semantics': 'all scores/weights frozen before result; interactions learned only after result'}
    payload['interaction_sha256'] = sha256_json(payload)
    return payload


def analyze_snapshot(snapshot: dict[str, Any], actual_numbers, max_group_order: int = MAX_GROUP_ORDER):
    raw = snapshot.get('raw_signals'); weights = snapshot.get('weights')
    if not isinstance(raw, dict) or not isinstance(weights, dict):
        raise ValueError('snapshot requires raw_signals and weights')
    scores = {}
    for name, sig in raw.items():
        values = sig.get('values')
        if not isinstance(values, dict) or set(values) != {str(i) for i in range(1, 61)}:
            raise ValueError(f'{name}: expected exactly 60 values')
        scores[name] = [float(values[str(i)]) for i in range(1, 61)]
    return analyze_interactions(scores, weights, actual_numbers, max_group_order=max_group_order)


@dataclass
class PairInteractionState:
    a: str
    b: str
    observations: int = 0
    sum_interaction: float = 0.0
    mean_interaction: float = 0.0
    m2: float = 0.0
    ewma_interaction: float = 0.0
    positive: int = 0
    zero: int = 0
    negative: int = 0

    def update(self, value: float):
        x = float(value)
        if not math.isfinite(x):
            raise ValueError('interaction update must be finite')
        self.observations += 1
        self.sum_interaction += x
        d = x - self.mean_interaction
        self.mean_interaction += d / self.observations
        self.m2 += d * (x - self.mean_interaction)
        self.ewma_interaction = x if self.observations == 1 else (1-EWMA_ALPHA)*self.ewma_interaction + EWMA_ALPHA*x
        if x > 0: self.positive += 1
        elif x < 0: self.negative += 1
        else: self.zero += 1

    def metrics(self):
        var = self.m2/(self.observations-1) if self.observations > 1 else 0.0
        conf = self.observations/(self.observations+CONFIDENCE_HALF_LIFE) if self.observations else 0.0
        return {'schema': SCHEMA, 'signals': [self.a, self.b], 'observations': self.observations,
                'mean_interaction_delta_hits': self.mean_interaction,
                'cumulative_interaction_delta_hits': self.sum_interaction,
                'std_interaction_delta_hits': math.sqrt(max(0.0, var)),
                'ewma_interaction_delta_hits': self.ewma_interaction,
                'confidence': conf, 'shrunk_interaction': self.mean_interaction*conf,
                'positive_updates': self.positive, 'zero_updates': self.zero, 'negative_updates': self.negative,
                'weight_effect_enabled': False}


@dataclass
class InteractionTracker:
    signal_names: tuple[str, ...]
    pairs: dict[str, PairInteractionState] = field(init=False)

    def __post_init__(self):
        names = tuple(sorted(self.signal_names))
        if len(names) < 2 or len(set(names)) != len(names):
            raise ValueError('at least two unique signal names required')
        self.signal_names = names
        self.pairs = {f'{a}|{b}': PairInteractionState(a,b) for a,b in itertools.combinations(names,2)}

    def update(self, scores, weights, actual_numbers):
        analysis = analyze_interactions(scores, weights, actual_numbers, max_group_order=2)
        if set(analysis['pair_interactions']) != set(self.pairs):
            raise ValueError('interaction ids do not match tracker')
        for key, row in analysis['pair_interactions'].items():
            if row.get('available', True):
                self.pairs[key].update(row['interaction_delta_hits'])
        return analysis

    def metrics(self):
        rows = {k: v.metrics() for k,v in self.pairs.items()}
        ranked = sorted(rows, key=lambda k: (-rows[k]['shrunk_interaction'], k))
        return {'schema': SCHEMA, 'pair_count': len(rows), 'pairs': rows,
                'top_synergies': ranked[:10], 'top_antagonisms': list(reversed(ranked[-10:])),
                'weight_effect_enabled': False}
