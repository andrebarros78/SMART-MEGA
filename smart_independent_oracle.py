from __future__ import annotations

import math
from typing import Any

SCHEMA = 'SMART_INDEPENDENT_DECISION_ORACLE_1'
REQUIRED_FACTORS = ('utility', 'quality', 'confidence', 'context', 'redundancy_penalty')
RECOVERY_PRIOR_MIX = 0.05
FAMILY_CAP = 0.70
FINAL_EXPERT_CAP = 0.42
ABS_TOL = 1e-11
REL_TOL = 1e-10


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} must be numeric')
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f'{label} must be finite')
    return out


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    if not weights:
        raise ValueError('oracle weights cannot be empty')
    if any((not math.isfinite(v) or v < 0.0) for v in weights.values()):
        raise ValueError('oracle weights must be finite and non-negative')
    mass = float(sum(weights.values()))
    if mass <= 0.0:
        raise ValueError('oracle weight mass must be positive')
    return {k: float(v / mass) for k, v in weights.items()}


def _expert_cap(weights: dict[str, float], cap: float = FINAL_EXPERT_CAP) -> dict[str, float]:
    out = _normalize(dict(weights))
    cap = max(float(cap), 1.0 / len(out))
    base = dict(out)
    result = {k: 0.0 for k in base}
    free = list(base)
    remaining = 1.0
    while free:
        free_mass = sum(base[k] for k in free)
        if free_mass <= 0.0:
            share = remaining / len(free)
            for k in free:
                result[k] = share
            free = []
            continue
        proposed = {k: remaining * base[k] / free_mass for k in free}
        over = [k for k, value in proposed.items() if value > cap + 1e-15]
        if not over:
            for k, value in proposed.items():
                result[k] = value
            free = []
            continue
        for k in over:
            result[k] = cap
        remaining -= cap * len(over)
        locked = set(over)
        free = [k for k in free if k not in locked]
    return _normalize(result)


def _family_cap(weights: dict[str, float], families: dict[str, str], cap: float = FAMILY_CAP) -> dict[str, float]:
    if set(weights) != set(families):
        raise ValueError('oracle families must match weight ids')
    out = _normalize(dict(weights))
    family_names = sorted(set(families.values()))
    if len(family_names) <= 1:
        return out
    for family in family_names:
        total = sum(out[n] for n in out if families[n] == family)
        if total <= cap + 1e-15:
            continue
        excess = total - cap
        members = [n for n in out if families[n] == family]
        others = [n for n in out if families[n] != family]
        for n in members:
            out[n] *= cap / total
        other_total = sum(out[n] for n in others)
        if other_total > 0.0:
            for n in others:
                out[n] += excess * out[n] / other_total
        else:
            share = excess / len(others)
            for n in others:
                out[n] += share
    return _normalize(out)


def recompute_dynamic_weights(metrics: dict[str, dict[str, Any]], families: dict[str, str]) -> tuple[dict[str, float], dict[str, float]]:
    if not isinstance(metrics, dict) or not metrics or set(metrics) != set(families):
        raise ValueError('oracle metrics/families mismatch')
    raw: dict[str, float] = {}
    for name, row in metrics.items():
        if not isinstance(row, dict):
            raise ValueError(f'{name}: metric row must be object')
        product = 1.0
        for factor in REQUIRED_FACTORS:
            if factor not in row:
                raise ValueError(f'{name}: missing factor {factor}')
            product *= max(0.0, _finite(row[factor], f'{name}.{factor}'))
        raw[name] = max(product, 1e-15)
    weights = _normalize(raw)
    n = len(weights)
    weights = {k: (1.0 - RECOVERY_PRIOR_MIX) * v + RECOVERY_PRIOR_MIX / n for k, v in weights.items()}
    weights = _expert_cap(weights)
    weights = _family_cap(weights, families)
    weights = _expert_cap(weights)
    return weights, raw


def _signal_values(raw_signals: dict[str, Any]) -> tuple[dict[str, list[float]], dict[str, str]]:
    if not isinstance(raw_signals, dict) or not raw_signals:
        raise ValueError('oracle raw_signals missing')
    arrays: dict[str, list[float]] = {}
    families: dict[str, str] = {}
    expected_keys = {str(i) for i in range(1, 61)}
    for name, row in raw_signals.items():
        if not isinstance(row, dict) or not isinstance(row.get('values'), dict):
            raise ValueError(f'{name}: invalid raw signal')
        values = row['values']
        if set(values) != expected_keys:
            raise ValueError(f'{name}: raw signal must contain exactly 1..60')
        arrays[name] = [_finite(values[str(i)], f'{name}.values.{i}') for i in range(1, 61)]
        family = row.get('family')
        if not isinstance(family, str) or not family:
            raise ValueError(f'{name}: signal family missing')
        families[name] = family
    return arrays, families


def _compare_map(observed: dict[str, Any], expected: dict[str, float], label: str) -> None:
    if not isinstance(observed, dict) or set(observed) != set(expected):
        raise ValueError(f'{label} ids mismatch')
    for key, value in expected.items():
        got = _finite(observed[key], f'{label}.{key}')
        if not math.isclose(got, value, rel_tol=REL_TOL, abs_tol=ABS_TOL):
            raise ValueError(f'{label} mismatch at {key}')


def _contrastive_guard_independent(primary_top6: list[int], ranking60: list[int], champion_top6: list[int], minimum_novelty: int = 1) -> list[int]:
    primary = [int(x) for x in primary_top6]
    ranking = [int(x) for x in ranking60]
    champion = [int(x) for x in champion_top6]
    if len(primary) != 6 or len(set(primary)) != 6 or len(champion) != 6 or len(set(champion)) != 6:
        raise ValueError('oracle diversity guard top6 invalid')
    if len(ranking) != 60 or len(set(ranking)) != 60:
        raise ValueError('oracle diversity guard ranking invalid')
    champion_set = set(champion)
    if len(set(primary) - champion_set) >= int(minimum_novelty):
        return primary
    final = list(primary)
    # ranking is a 60-item permutation while Champion contains only six numbers,
    # therefore at least one contrastive replacement is mathematically guaranteed.
    replacement = next(n for n in ranking if n not in champion_set and n not in final[:-1])
    final[-1] = int(replacement)
    if len(set(final) - champion_set) < int(minimum_novelty):
        raise ValueError('oracle diversity guard minimum novelty failed')
    return final


def validate_prediction_snapshot(prediction: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(prediction, dict):
        raise ValueError('oracle prediction must be object')
    required = ('raw_signals', 'quality_metrics', 'weight_components', 'weights', 'aggregate_scores', 'ranking60', 'top6')
    missing = [k for k in required if k not in prediction]
    if missing:
        return {'schema': SCHEMA, 'status': 'LEGACY_NOT_APPLICABLE', 'verified': False, 'missing_fields': missing}

    arrays, families = _signal_values(prediction['raw_signals'])
    metrics = prediction['quality_metrics']
    if not isinstance(metrics, dict) or set(metrics) != set(arrays):
        raise ValueError('oracle quality_metrics ids mismatch')
    expected_weights, raw_products = recompute_dynamic_weights(metrics, families)
    observed_weights = prediction['weights']
    _compare_map(observed_weights, expected_weights, 'weights')

    components = prediction['weight_components']
    if not isinstance(components, dict) or set(components) != set(arrays):
        raise ValueError('oracle weight_components ids mismatch')
    for name in arrays:
        row = components[name]
        if not isinstance(row, dict):
            raise ValueError(f'{name}: weight component must be object')
        if not math.isclose(_finite(row.get('raw_product'), f'{name}.raw_product'), raw_products[name], rel_tol=REL_TOL, abs_tol=ABS_TOL):
            raise ValueError(f'{name}: raw product mismatch')
        if not math.isclose(_finite(row.get('final_weight'), f'{name}.final_weight'), expected_weights[name], rel_tol=REL_TOL, abs_tol=ABS_TOL):
            raise ValueError(f'{name}: final weight mismatch')

    aggregate = [0.0] * 60
    for name, values in arrays.items():
        w = expected_weights[name]
        for index, value in enumerate(values):
            aggregate[index] += w * value
    expected_scores = {str(i + 1): float(aggregate[i]) for i in range(60)}
    _compare_map(prediction['aggregate_scores'], expected_scores, 'aggregate_scores')

    ranking = sorted(range(1, 61), key=lambda number: (-aggregate[number - 1], number))
    stored_ranking = prediction['ranking60']
    if not isinstance(stored_ranking, list) or [int(x) for x in stored_ranking] != ranking:
        raise ValueError('oracle ranking60 mismatch')
    anchor_top6 = ranking[:6]

    governor = prediction.get('meta_governor')
    expected_final = anchor_top6
    decision_mode = 'quality_dynamic_anchor'
    if isinstance(governor, dict) and governor.get('alternate_authorized') is True:
        selected = governor.get('selected_top6')
        if not isinstance(selected, list) or len(selected) != 6:
            raise ValueError('oracle meta governor selected_top6 invalid')
        expected_final = [int(x) for x in selected]
        decision_mode = 'authorized_meta_governor'
    guard = prediction.get('challenger_diversity_guard')
    if isinstance(guard, dict) and guard.get('active') is True:
        if (
            guard.get('result_used') is not False
            or guard.get('promotion_authority') is not False
            or guard.get('shadow_only') is not True
            or guard.get('decision_effect') is not False
            or guard.get('applied') is not False
        ):
            raise ValueError('oracle diversity guard authority semantics invalid')
        champion = guard.get('champion_top6')
        minimum_novelty = guard.get('minimum_novelty', 1)
        if not isinstance(champion, list) or isinstance(minimum_novelty, bool):
            raise ValueError('oracle diversity guard payload invalid')
        shadow = _contrastive_guard_independent(expected_final, ranking, champion, int(minimum_novelty))
        if [int(x) for x in guard.get('primary_top6', [])] != expected_final:
            raise ValueError('oracle diversity guard primary mismatch')
        if [int(x) for x in guard.get('final_top6', [])] != expected_final:
            raise ValueError('oracle diversity guard final mismatch')
        if [int(x) for x in guard.get('shadow_top6', [])] != shadow:
            raise ValueError('oracle diversity guard shadow mismatch')
        generated = shadow != expected_final
        if guard.get('shadow_candidate_generated') is not generated:
            raise ValueError('oracle diversity guard generated flag mismatch')
    stored_top6 = prediction['top6']
    if not isinstance(stored_top6, list) or [int(x) for x in stored_top6] != expected_final:
        raise ValueError('oracle final top6 mismatch')

    multi = prediction.get('multi_challengers')
    if isinstance(multi, dict):
        policies = multi.get('policies')
        if isinstance(policies, dict) and isinstance(policies.get('quality_dynamic'), dict):
            qtop = policies['quality_dynamic'].get('top6')
            if not isinstance(qtop, list) or [int(x) for x in qtop] != anchor_top6:
                raise ValueError('oracle quality_dynamic anchor mismatch')

    calibration = prediction.get('rank_score_calibration')
    if isinstance(calibration, dict) and isinstance(calibration.get('probabilities_by_number'), dict):
        probs = calibration['probabilities_by_number']
        if set(probs) != {str(i) for i in range(1, 61)}:
            raise ValueError('oracle probability map ids mismatch')
        total = sum(_finite(probs[str(i)], f'probability.{i}') for i in range(1, 61))
        if not math.isclose(total, 6.0, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError('oracle probability mass must sum to six')

    return {
        'schema': SCHEMA,
        'status': 'PASS',
        'verified': True,
        'signal_count': len(arrays),
        'weight_sum': float(sum(expected_weights.values())),
        'anchor_top6': anchor_top6,
        'final_top6': expected_final,
        'decision_mode': decision_mode,
        'production_engine_imported': False,
        'recomputed_weights': True,
        'recomputed_aggregate_scores': True,
        'recomputed_ranking': True,
        'recomputed_final_top6': True,
    }


def validate_frozen_decision(frozen: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(frozen, dict):
        raise ValueError('oracle frozen artifact must be object')
    prediction = frozen.get('challenger')
    if not isinstance(prediction, dict):
        return {'schema': SCHEMA, 'status': 'LEGACY_NOT_APPLICABLE', 'verified': False, 'missing_fields': ['challenger']}
    result = validate_prediction_snapshot(prediction)
    if result.get('verified') is True and 'governed_challenger_top6' in frozen:
        governed = frozen['governed_challenger_top6']
        if not isinstance(governed, list) or [int(x) for x in governed] != result['final_top6']:
            raise ValueError('oracle frozen governed challenger top6 mismatch')
    return result


__all__ = ['SCHEMA', 'recompute_dynamic_weights', 'validate_prediction_snapshot', 'validate_frozen_decision']
