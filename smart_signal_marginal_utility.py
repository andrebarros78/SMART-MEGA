from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

import numpy as np

import smart_v2_engine as e

MARGINAL_UTILITY_SCHEMA = 'SMART_SIGNAL_MARGINAL_UTILITY_1'
EWMA_ALPHA = 0.05
CONFIDENCE_HALF_LIFE = 100.0


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _validate_actual(actual_numbers) -> list[int]:
    actual = sorted(int(x) for x in actual_numbers)
    if len(actual) != 6 or len(set(actual)) != 6 or actual[0] < 1 or actual[-1] > 60:
        raise ValueError('actual_numbers must contain six unique numbers in 1..60')
    return actual


def _normalize_inputs(scores: dict[str, Any], weights: dict[str, float]) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    if not isinstance(scores, dict) or not scores or not isinstance(weights, dict):
        raise ValueError('scores and weights are required')
    if set(scores) != set(weights):
        raise ValueError('scores and weights must contain identical signal ids')
    arrays: dict[str, np.ndarray] = {}
    parsed: dict[str, float] = {}
    for name in sorted(scores):
        arr = np.asarray(scores[name], dtype=float)
        if arr.shape != (60,) or not np.all(np.isfinite(arr)):
            raise ValueError(f'signal {name} must contain 60 finite values')
        w = float(weights[name])
        if not math.isfinite(w) or w < 0:
            raise ValueError(f'invalid weight for {name}')
        arrays[name] = arr
        parsed[name] = w
    total = float(sum(parsed.values()))
    if total <= 0:
        raise ValueError('weights must have positive total mass')
    return arrays, {name: w / total for name, w in parsed.items()}


def _aggregate(arrays: dict[str, np.ndarray], weights: dict[str, float], removed: str | None = None) -> np.ndarray:
    kept = [name for name in arrays if name != removed]
    if not kept:
        raise ValueError('leave-one-out requires at least one remaining signal')
    mass = float(sum(weights[name] for name in kept))
    if mass <= 0:
        raise ValueError('remaining signals have zero weight mass')
    out = np.zeros(60, dtype=float)
    for name in kept:
        out += (weights[name] / mass) * arrays[name]
    return out


def _evaluate(score: np.ndarray, actual: list[int]) -> dict[str, Any]:
    top6, order = e.rank_top6(score)
    ranking = e.NUMBERS[order].tolist()
    ranks = {int(number): idx + 1 for idx, number in enumerate(ranking)}
    aset = set(actual)
    return {'top6': [int(x) for x in top6], 'hits': int(len(set(top6) & aset)),
            'ranks_actual': {str(n): int(ranks[n]) for n in actual}}


def evaluate_incremental_utility(scores: dict[str, Any], weights: dict[str, float], actual_numbers) -> dict[str, Any]:
    actual = _validate_actual(actual_numbers)
    arrays, norm_weights = _normalize_inputs(scores, weights)
    full_score = _aggregate(arrays, norm_weights)
    full = _evaluate(full_score, actual)
    full_top = set(full['top6'])
    actual_set = set(actual)
    per_signal: dict[str, dict[str, Any]] = {}
    for name in sorted(arrays):
        if len(arrays) == 1:
            per_signal[name] = {
                'available': False,
                'reason': 'leave-one-out undefined for a single-signal ensemble',
                'weight_before_result': float(norm_weights[name]),
            }
            continue
        loo_score = _aggregate(arrays, norm_weights, removed=name)
        loo = _evaluate(loo_score, actual)
        loo_top = set(loo['top6'])
        rank_lifts = [int(loo['ranks_actual'][str(n)]) - int(full['ranks_actual'][str(n)]) for n in actual]
        per_signal[name] = {
            'available': True,
            'weight_before_result': float(norm_weights[name]),
            'full_hits': int(full['hits']),
            'leave_one_out_hits': int(loo['hits']),
            'delta_hits': int(full['hits'] - loo['hits']),
            'mean_actual_rank_lift': float(np.mean(rank_lifts) / 59.0),
            'actual_rank_lift': {str(n): int(loo['ranks_actual'][str(n)] - full['ranks_actual'][str(n)]) for n in actual},
            'helped_actual_into_top6': sorted(int(n) for n in actual_set if n in full_top and n not in loo_top),
            'harmed_actual_out_of_top6': sorted(int(n) for n in actual_set if n not in full_top and n in loo_top),
            'leave_one_out_top6': loo['top6'],
        }
    payload = {
        'schema': MARGINAL_UTILITY_SCHEMA,
        'causal_semantics': 'weights/scores are frozen before result; outcome updates utility only after result',
        'actual_numbers': actual,
        'full_ensemble': full,
        'per_signal': per_signal,
    }
    payload['marginal_utility_sha256'] = sha256_json(payload)
    return payload


def analyze_marginal_utility_snapshot(snapshot: dict[str, Any], actual_numbers) -> dict[str, Any]:
    raw = snapshot.get('raw_signals')
    weights = snapshot.get('weights')
    if not isinstance(raw, dict) or not isinstance(weights, dict):
        raise ValueError('snapshot requires raw_signals and weights')
    scores = {}
    for name, sig in raw.items():
        values = sig.get('values')
        if not isinstance(values, dict) or set(values) != {str(i) for i in range(1, 61)}:
            raise ValueError(f'signal {name} must contain exactly 60 values')
        scores[name] = np.asarray([float(values[str(i)]) for i in range(1, 61)], dtype=float)
    return evaluate_incremental_utility(scores, weights, actual_numbers)


@dataclass
class MarginalUtilityState:
    name: str
    observations: int = 0
    sum_delta_hits: float = 0.0
    mean_delta_hits: float = 0.0
    m2_delta_hits: float = 0.0
    ewma_delta_hits: float = 0.0
    mean_rank_lift: float = 0.0
    m2_rank_lift: float = 0.0
    ewma_rank_lift: float = 0.0
    positive_updates: int = 0
    zero_updates: int = 0
    negative_updates: int = 0
    last_delta_hits: float = 0.0
    last_rank_lift: float = 0.0

    def update(self, delta_hits: float, rank_lift: float) -> None:
        d = float(delta_hits)
        r = float(rank_lift)
        if not math.isfinite(d) or not math.isfinite(r):
            raise ValueError('marginal utility update must be finite')
        self.observations += 1
        self.sum_delta_hits += d
        dd = d - self.mean_delta_hits
        self.mean_delta_hits += dd / self.observations
        self.m2_delta_hits += dd * (d - self.mean_delta_hits)
        dr = r - self.mean_rank_lift
        self.mean_rank_lift += dr / self.observations
        self.m2_rank_lift += dr * (r - self.mean_rank_lift)
        if self.observations == 1:
            self.ewma_delta_hits = d
            self.ewma_rank_lift = r
        else:
            self.ewma_delta_hits = (1.0 - EWMA_ALPHA) * self.ewma_delta_hits + EWMA_ALPHA * d
            self.ewma_rank_lift = (1.0 - EWMA_ALPHA) * self.ewma_rank_lift + EWMA_ALPHA * r
        if d > 0:
            self.positive_updates += 1
        elif d < 0:
            self.negative_updates += 1
        else:
            self.zero_updates += 1
        self.last_delta_hits = d
        self.last_rank_lift = r

    def metrics(self) -> dict[str, Any]:
        variance = self.m2_delta_hits / (self.observations - 1) if self.observations > 1 else 0.0
        rank_variance = self.m2_rank_lift / (self.observations - 1) if self.observations > 1 else 0.0
        confidence = self.observations / (self.observations + CONFIDENCE_HALF_LIFE) if self.observations else 0.0
        shrunk = self.mean_delta_hits * confidence
        return {
            'schema': MARGINAL_UTILITY_SCHEMA,
            'signal_id': self.name,
            'observations': int(self.observations),
            'mean_delta_hits': float(self.mean_delta_hits),
            'cumulative_delta_hits': float(self.sum_delta_hits),
            'std_delta_hits': float(math.sqrt(max(0.0, variance))),
            'ewma_delta_hits': float(self.ewma_delta_hits),
            'mean_actual_rank_lift': float(self.mean_rank_lift),
            'std_actual_rank_lift': float(math.sqrt(max(0.0, rank_variance))),
            'ewma_actual_rank_lift': float(self.ewma_rank_lift),
            'confidence': float(confidence),
            'shrunk_mean_delta_hits': float(shrunk),
            'positive_updates': int(self.positive_updates),
            'zero_updates': int(self.zero_updates),
            'negative_updates': int(self.negative_updates),
            'last_delta_hits': float(self.last_delta_hits),
            'last_rank_lift': float(self.last_rank_lift),
            'weight_effect_enabled': False,
            'interpretation': 'expected incremental ensemble hits attributable to this signal under causal leave-one-out',
        }


def update_marginal_states(states: dict[str, MarginalUtilityState], scores: dict[str, Any], weights: dict[str, float], actual_numbers) -> dict[str, Any]:
    analysis = evaluate_incremental_utility(scores, weights, actual_numbers)
    if set(states) != set(analysis['per_signal']):
        raise ValueError('states must match signal ids')
    for name, item in analysis['per_signal'].items():
        if item['available']:
            states[name].update(item['delta_hits'], item['mean_actual_rank_lift'])
    return analysis
