from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Any

import numpy as np

SCHEMA = 'SMART_MULTI_CHALLENGERS_1'
POLICY_IDS = (
    'quality_dynamic',
    'diversity_max',
    'low_redundancy',
    'regime_context',
    'conservative',
)
EXPERT_CAP = 0.42
FAMILY_CAP = 0.70
CONSERVATIVE_EXPERT_CAP = 0.25
CONSERVATIVE_FAMILY_CAP = 0.60
LOW_REDUNDANCY_POWER = 2.0
CONSERVATIVE_BLEND = 0.50


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    out = {str(k): float(v) for k, v in weights.items()}
    if not out or any((not math.isfinite(v) or v < 0.0) for v in out.values()):
        raise ValueError('weights must be finite and non-negative')
    z = sum(out.values())
    if z <= 0.0:
        raise ValueError('weight mass must be positive')
    return {k: v / z for k, v in out.items()}


def _cap_expert(weights: dict[str, float], cap: float) -> dict[str, float]:
    if not 0.0 < float(cap) < 1.0:
        raise ValueError('expert cap must be in (0,1)')
    out = _normalize(weights)
    if len(out) * cap < 1.0 - 1e-12:
        raise ValueError('expert cap infeasible for number of policies')
    for _ in range(len(out) + 2):
        over = [k for k, v in out.items() if v > cap + 1e-15]
        if not over:
            return _normalize(out)
        locked_mass = cap * len(over)
        free = [k for k in out if k not in over]
        free_mass = sum(out[k] for k in free)
        for k in over:
            out[k] = cap
        if not free or free_mass <= 0.0:
            return _normalize(out)
        scale = (1.0 - locked_mass) / free_mass
        for k in free:
            out[k] *= scale
    return _normalize(out)


def _cap_family(weights: dict[str, float], families: dict[str, str], cap: float) -> dict[str, float]:
    if set(weights) != set(families):
        raise ValueError('weights and families must have identical ids')
    out = _normalize(weights)
    fams = sorted(set(families.values()))
    if len(fams) <= 1:
        return out
    if len(fams) * cap < 1.0 - 1e-12:
        raise ValueError('family cap infeasible')
    while True:
        totals = defaultdict(float)
        for n, w in out.items():
            totals[families[n]] += w
        over = [f for f in fams if totals[f] > cap + 1e-15]
        if not over:
            return _normalize(out)
        for fam in over:
            total = totals[fam]
            excess = total - cap
            members = [n for n in out if families[n] == fam]
            others = [n for n in out if families[n] != fam]
            for n in members:
                out[n] *= cap / total
            other_total = sum(out[n] for n in others)
            if other_total <= 0.0:
                share = excess / len(others)
                for n in others:
                    out[n] += share
            else:
                for n in others:
                    out[n] += excess * out[n] / other_total


def _bounded(weights: dict[str, float], families: dict[str, str], expert_cap: float = EXPERT_CAP,
             family_cap: float = FAMILY_CAP) -> dict[str, float]:
    out = _cap_expert(weights, expert_cap)
    out = _cap_family(out, families, family_cap)
    return _cap_expert(out, expert_cap)


def _equal_family_weights(names: list[str], families: dict[str, str]) -> dict[str, float]:
    fams = sorted(set(families[n] for n in names))
    if not fams:
        raise ValueError('at least one family is required')
    out = {}
    for fam in fams:
        members = [n for n in names if families[n] == fam]
        for n in members:
            out[n] = 1.0 / len(fams) / len(members)
    return _normalize(out)


def _aggregate(scores: dict[str, np.ndarray], weights: dict[str, float]) -> tuple[list[int], list[int], dict[str, float]]:
    agg = np.zeros(60, dtype=float)
    for n, w in weights.items():
        agg += float(w) * scores[n]
    order = np.lexsort((np.arange(1, 61), -agg))
    ranking = (order + 1).tolist()
    return ranking[:6], ranking, {str(i + 1): float(agg[i]) for i in range(60)}


def _validate(scores: dict[str, Any], base_weights: dict[str, float], metrics: dict[str, dict[str, Any]],
              families: dict[str, str], redundancy_audit: dict[str, Any], context_state: dict[str, Any]):
    if not isinstance(scores, dict) or not scores:
        raise ValueError('scores cannot be empty')
    names = sorted(scores)
    if set(base_weights) != set(names) or set(metrics) != set(names) or set(families) != set(names):
        raise ValueError('scores, weights, metrics and families must have identical ids')
    arrays = {}
    for n in names:
        arr = np.asarray(scores[n], dtype=float)
        if arr.shape != (60,) or not np.all(np.isfinite(arr)):
            raise ValueError(f'{n}: expected 60 finite scores')
        arrays[n] = arr
        if 'regime_context' not in metrics[n]:
            raise ValueError(f'{n}: missing regime_context')
    base = _normalize(base_weights)
    penalties = redundancy_audit.get('penalties', {}) if isinstance(redundancy_audit, dict) else {}
    if set(penalties) != set(names):
        raise ValueError('redundancy penalties must match signal ids')
    for n in names:
        p = float(penalties[n])
        r = float(metrics[n]['regime_context'])
        if not math.isfinite(p) or p <= 0.0 or not math.isfinite(r) or r <= 0.0:
            raise ValueError('policy factors must be finite and positive')
    if not isinstance(context_state, dict) or 'active' not in context_state:
        raise ValueError('context_state must contain active')
    return names, arrays, base, {n: float(penalties[n]) for n in names}


def build_multi_challengers(scores: dict[str, Any], base_weights: dict[str, float],
                            metrics: dict[str, dict[str, Any]], families: dict[str, str],
                            redundancy_audit: dict[str, Any], context_state: dict[str, Any],
                            audit_detail: bool = True) -> dict[str, Any]:
    names, arrays, base, penalties = _validate(scores, base_weights, metrics, families, redundancy_audit, context_state)
    equal_family = _equal_family_weights(names, families)

    policies: dict[str, dict[str, Any]] = {}
    policy_weights: dict[str, dict[str, float]] = {}
    policy_weights['quality_dynamic'] = _bounded(base, families)
    policy_weights['diversity_max'] = _bounded(equal_family, families)
    low_red_raw = {n: base[n] * (penalties[n] ** LOW_REDUNDANCY_POWER) for n in names}
    policy_weights['low_redundancy'] = _bounded(low_red_raw, families)
    if bool(context_state.get('active', False)):
        context_raw = {n: base[n] * (float(metrics[n]['regime_context']) ** 2.0) for n in names}
    else:
        context_raw = dict(base)
    policy_weights['regime_context'] = _bounded(context_raw, families)
    conservative_raw = {n: (1.0 - CONSERVATIVE_BLEND) * base[n] + CONSERVATIVE_BLEND * equal_family[n] for n in names}
    policy_weights['conservative'] = _bounded(conservative_raw, families, CONSERVATIVE_EXPERT_CAP, CONSERVATIVE_FAMILY_CAP)

    for policy_id in POLICY_IDS:
        weights = policy_weights[policy_id]
        top6, ranking60, aggregate_scores = _aggregate(arrays, weights)
        fam_totals = {f: float(sum(w for n, w in weights.items() if families[n] == f)) for f in sorted(set(families.values()))}
        policies[policy_id] = {
            'policy_id': policy_id,
            'top6': top6,
            'ranking60': ranking60 if audit_detail else [],
            'aggregate_scores': aggregate_scores if audit_detail else {},
            'weights': weights,
            'max_weight': float(max(weights.values())),
            'family_totals': fam_totals,
            'context_active': bool(context_state.get('active', False)),
            'selection_authority': False,
            'audit_detail': bool(audit_detail),
        }
        policies[policy_id]['sha256'] = sha256_json(policies[policy_id])

    distinct_weight_pairs = 0
    total_pairs = 0
    ids = list(POLICY_IDS)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            total_pairs += 1
            if any(abs(policies[a]['weights'][n] - policies[b]['weights'][n]) > 1e-12 for n in names):
                distinct_weight_pairs += 1
    out = {
        'schema': SCHEMA,
        'policy_ids': list(POLICY_IDS),
        'policies': policies,
        'policy_count': len(POLICY_IDS),
        'distinct_weight_pairs': int(distinct_weight_pairs),
        'total_policy_pairs': int(total_pairs),
        'quality_dynamic_is_primary_challenger': True,
        'shadow_only': True,
        'selection_deferred_to_p08': True,
        'retroactive_selection_prohibited': True,
    }
    out['sha256'] = sha256_json(out)
    return out
