from __future__ import annotations

import hashlib
import itertools
import json
from typing import Any

import numpy as np

import smart_v2_engine as e

ATTRIBUTION_SCHEMA = 'SMART_SIGNAL_ATTRIBUTION_1'
MAX_COALITION_REMOVAL = 3


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _snapshot_arrays(snapshot: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    raw = snapshot.get('raw_signals')
    weights = snapshot.get('weights')
    if not isinstance(raw, dict) or not raw or not isinstance(weights, dict):
        raise ValueError('snapshot requires raw_signals and weights')
    if set(raw) != set(weights):
        raise ValueError('raw_signals and weights must contain identical signal ids')
    arrays: dict[str, np.ndarray] = {}
    parsed_weights: dict[str, float] = {}
    for name in sorted(raw):
        values = raw[name].get('values')
        if not isinstance(values, dict) or set(values) != {str(i) for i in range(1, 61)}:
            raise ValueError(f'signal {name} must contain exactly 60 values')
        arr = np.asarray([float(values[str(i)]) for i in range(1, 61)], dtype=float)
        if not np.all(np.isfinite(arr)):
            raise ValueError(f'signal {name} contains non-finite values')
        w = float(weights[name])
        if not np.isfinite(w) or w < 0:
            raise ValueError(f'invalid weight for {name}')
        arrays[name] = arr
        parsed_weights[name] = w
    total = sum(parsed_weights.values())
    if total <= 0:
        raise ValueError('weights must have positive total mass')
    parsed_weights = {n: w / total for n, w in parsed_weights.items()}
    return arrays, parsed_weights


def _aggregate(arrays: dict[str, np.ndarray], weights: dict[str, float], removed: tuple[str, ...] = ()) -> np.ndarray:
    removed_set = set(removed)
    kept = [n for n in arrays if n not in removed_set]
    if not kept:
        raise ValueError('cannot remove all signals')
    mass = sum(weights[n] for n in kept)
    if mass <= 0:
        raise ValueError('remaining signals have zero weight mass')
    out = np.zeros(60, dtype=float)
    for n in kept:
        out += (weights[n] / mass) * arrays[n]
    return out


def _evaluate(score: np.ndarray, actual_set: set[int]) -> dict[str, Any]:
    top6, order = e.rank_top6(score)
    ranking = e.NUMBERS[order].tolist()
    rank = {int(number): idx + 1 for idx, number in enumerate(ranking)}
    return {
        'top6': [int(x) for x in top6],
        'hits': len(set(top6) & actual_set),
        'ranking60': [int(x) for x in ranking],
        'rank_actual': {str(n): int(rank[n]) for n in sorted(actual_set)},
        'cutoff_score': float(score[top6[-1] - 1]),
    }


def _redundancy(arrays: dict[str, np.ndarray]) -> dict[str, dict[str, Any]]:
    names = sorted(arrays)
    out: dict[str, dict[str, Any]] = {}
    for name in names:
        peers = []
        a = arrays[name]
        for other in names:
            if other == name:
                continue
            b = arrays[other]
            if float(np.std(a)) <= 1e-15 or float(np.std(b)) <= 1e-15:
                corr = 0.0
            else:
                corr = float(np.corrcoef(a, b)[0, 1])
            peers.append((other, abs(corr), corr))
        peers.sort(key=lambda x: (-x[1], x[0]))
        mean_abs = float(np.mean([p[1] for p in peers])) if peers else 0.0
        out[name] = {
            'mean_abs_correlation': mean_abs,
            'novelty': float(max(0.0, 1.0 - mean_abs)),
            'most_redundant_peer': peers[0][0] if peers else None,
            'max_abs_correlation': float(peers[0][1]) if peers else 0.0,
            'signed_correlation_with_peer': float(peers[0][2]) if peers else 0.0,
        }
    return out


def analyze_attribution(snapshot: dict[str, Any], actual_numbers: list[int] | tuple[int, ...],
                        max_coalition_removal: int = MAX_COALITION_REMOVAL) -> dict[str, Any]:
    actual = sorted(int(x) for x in actual_numbers)
    if len(actual) != 6 or len(set(actual)) != 6 or actual[0] < 1 or actual[-1] > 60:
        raise ValueError('actual_numbers must contain six unique numbers in 1..60')
    if max_coalition_removal < 1:
        raise ValueError('max_coalition_removal must be >= 1')
    arrays, weights = _snapshot_arrays(snapshot)
    actual_set = set(actual)
    base_score = _aggregate(arrays, weights)
    base = _evaluate(base_score, actual_set)
    selected_wrong = sorted(set(base['top6']) - actual_set)
    missed_actual = sorted(actual_set - set(base['top6']))
    redundancy = _redundancy(arrays)

    per_signal: dict[str, dict[str, Any]] = {}
    for name in sorted(arrays):
        loo_score = _aggregate(arrays, weights, (name,))
        loo = _evaluate(loo_score, actual_set)
        exact_delta = base_score - loo_score
        top, _ = e.rank_top6(arrays[name])
        expert_hits = len(set(top) & actual_set)
        pushed_down = []
        for correct in missed_actual:
            blockers = []
            for wrong in selected_wrong:
                margin = float(weights[name] * (arrays[name][correct - 1] - arrays[name][wrong - 1]))
                if margin < 0:
                    blockers.append({'wrong_selected': int(wrong), 'weighted_support_correct_minus_wrong': margin})
            blockers.sort(key=lambda x: (x['weighted_support_correct_minus_wrong'], x['wrong_selected']))
            if blockers:
                pushed_down.append({'correct_number': int(correct), 'against': blockers})
        per_signal[name] = {
            'weight_before_result': float(weights[name]),
            'expert_top6': [int(x) for x in top],
            'expert_top6_hits': int(expert_hits),
            'leave_one_out_top6': loo['top6'],
            'leave_one_out_hits': int(loo['hits']),
            'marginal_hit_contribution': int(base['hits'] - loo['hits']),
            'actual_rank_change_if_removed': {
                str(n): int(loo['rank_actual'][str(n)] - base['rank_actual'][str(n)]) for n in actual
            },
            'exact_score_contribution_actual': {str(n): float(exact_delta[n - 1]) for n in actual},
            'pushed_correct_numbers_down_vs_selected_wrong': pushed_down,
            'redundancy': redundancy[name],
        }

    coalitions_tested = 0
    minimal_improving_size: int | None = None
    minimal_improving: list[dict[str, Any]] = []
    target_recovery: dict[str, dict[str, Any]] = {
        str(n): {'base_rank': int(base['rank_actual'][str(n)]), 'minimal_removed': None, 'examples': []}
        for n in missed_actual
    }
    names = sorted(arrays)
    max_remove = min(int(max_coalition_removal), len(names) - 1)
    for size in range(1, max_remove + 1):
        for removed in itertools.combinations(names, size):
            coalitions_tested += 1
            score = _aggregate(arrays, weights, removed)
            ev = _evaluate(score, actual_set)
            if ev['hits'] > base['hits']:
                if minimal_improving_size is None:
                    minimal_improving_size = size
                if size == minimal_improving_size and len(minimal_improving) < 20:
                    minimal_improving.append({
                        'removed_signals': list(removed), 'top6': ev['top6'], 'hits': int(ev['hits']),
                        'gain_vs_base': int(ev['hits'] - base['hits']), 'rank_actual': ev['rank_actual'],
                    })
            for n in missed_actual:
                key = str(n)
                if ev['rank_actual'][key] <= 6:
                    current = target_recovery[key]['minimal_removed']
                    if current is None:
                        target_recovery[key]['minimal_removed'] = size
                        current = size
                    if size == current and len(target_recovery[key]['examples']) < 10:
                        target_recovery[key]['examples'].append({
                            'removed_signals': list(removed), 'top6': ev['top6'], 'hits': int(ev['hits']),
                            'new_rank': int(ev['rank_actual'][key]),
                        })

    payload = {
        'schema': ATTRIBUTION_SCHEMA,
        'retroactive_optimization_prohibited': True,
        'purpose': 'post-result diagnostic attribution only; never rewrites the frozen prediction',
        'actual_numbers': actual,
        'base': {
            'top6': base['top6'], 'hits': int(base['hits']), 'rank_actual': base['rank_actual'],
            'cutoff_score': base['cutoff_score'],
        },
        'missed_actual_numbers': missed_actual,
        'selected_wrong_numbers': selected_wrong,
        'per_signal': per_signal,
        'coalition_analysis': {
            'max_removal_size': max_remove,
            'coalitions_tested': coalitions_tested,
            'minimal_improving_removal_size': minimal_improving_size,
            'minimal_improving_examples': minimal_improving,
            'missed_number_recovery': target_recovery,
        },
    }
    payload['attribution_sha256'] = sha256_json(payload)
    return payload

