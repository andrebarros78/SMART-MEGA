from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import numpy as np

SCHEMA = 'SMART_CONTEXTUAL_META_WEIGHTS_1'
DEFAULT_META_STRENGTH = 0.06
MAX_META_STRENGTH = 0.15

FEATURE_COEFFICIENTS = {
    'stability': 0.20,
    'recent_quality': 0.20,
    'dispersion': 0.10,
    'family_uniqueness': 0.15,
    'interaction': 0.20,
    'regime_alignment': 0.10,
    'drift_health': 0.05,
}


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _normalize_feature(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    arr = np.asarray([float(values[n]) for n in sorted(values)], dtype=float)
    if not np.all(np.isfinite(arr)):
        raise ValueError('meta feature contains non-finite values')
    center = float(np.median(arr))
    dev = np.abs(arr - center)
    scale = float(np.median(dev))
    if scale <= 1e-12:
        scale = float(np.std(arr))
    if scale <= 1e-12:
        return {n: 0.0 for n in values}
    return {n: float(np.clip((float(v) - center) / (2.5 * scale), -1.0, 1.0)) for n, v in values.items()}


def _score_arrays(scores: dict[str, Any]) -> dict[str, np.ndarray]:
    if not isinstance(scores, dict) or not scores:
        raise ValueError('scores cannot be empty')
    out = {}
    for name in sorted(scores):
        arr = np.asarray(scores[name], dtype=float)
        if arr.shape != (60,) or not np.all(np.isfinite(arr)):
            raise ValueError(f'{name}: expected 60 finite score values')
        out[name] = arr
    return out


def _family_features(arrays: dict[str, np.ndarray], families: dict[str, str]) -> tuple[dict[str, float], float]:
    if set(arrays) != set(families):
        raise ValueError('family ids must match score ids')
    fam_names = sorted(set(families.values()))
    fam_means = {}
    for fam in fam_names:
        members = [n for n in arrays if families[n] == fam]
        fam_means[fam] = np.mean([arrays[n] for n in members], axis=0)
    pair_distances = []
    for i, a in enumerate(fam_names):
        for b in fam_names[i + 1:]:
            pair_distances.append(float(np.mean(np.abs(fam_means[a] - fam_means[b]))))
    global_divergence = float(np.mean(pair_distances)) if pair_distances else 0.0
    uniqueness = {}
    for n, arr in arrays.items():
        own = families[n]
        own_distance = float(np.mean(np.abs(arr - fam_means[own])))
        other = [float(np.mean(np.abs(arr - fam_means[f]))) for f in fam_names if f != own]
        other_distance = float(np.mean(other)) if other else own_distance
        uniqueness[n] = other_distance - own_distance
    return uniqueness, global_divergence


def _interaction_feature(names: list[str], interaction_state: dict[str, Any] | None) -> dict[str, float]:
    out = {n: 0.0 for n in names}
    if not interaction_state:
        return out
    pairs = interaction_state.get('pairs', {})
    if not isinstance(pairs, dict):
        raise ValueError('interaction_state pairs must be a dict')
    counts = {n: 0 for n in names}
    for row in pairs.values():
        signals = row.get('signals', [])
        if not isinstance(signals, list) or len(signals) != 2:
            continue
        value = float(row.get('shrunk_interaction', 0.0))
        if not math.isfinite(value):
            raise ValueError('interaction feature must be finite')
        for n in signals:
            if n in out:
                out[n] += value
                counts[n] += 1
    return {n: (out[n] / counts[n] if counts[n] else 0.0) for n in names}


def contextual_meta_factors(scores: dict[str, Any], metrics: dict[str, dict[str, Any]],
                            families: dict[str, str], context_state: dict[str, Any],
                            interaction_state: dict[str, Any] | None = None,
                            strength: float = DEFAULT_META_STRENGTH) -> tuple[dict[str, float], dict[str, Any]]:
    strength = float(strength)
    if not math.isfinite(strength) or not 0.0 <= strength <= MAX_META_STRENGTH:
        raise ValueError(f'strength must be in [0,{MAX_META_STRENGTH}]')
    arrays = _score_arrays(scores)
    names = sorted(arrays)
    if set(metrics) != set(names) or set(families) != set(names):
        raise ValueError('scores, metrics and families must have identical ids')

    required = {'stability', 'recent_excess_vs_uniform', 'quality', 'drift_active', 'regime_context'}
    for n in names:
        missing = required - set(metrics[n])
        if missing:
            raise ValueError(f'{n}: missing meta metrics {sorted(missing)}')

    raw_stability = {n: float(metrics[n]['stability']) for n in names}
    raw_recent = {n: 0.65 * float(metrics[n]['recent_excess_vs_uniform']) + 0.35 * (float(metrics[n]['quality']) - 0.5) for n in names}
    raw_dispersion = {n: float(np.std(arrays[n])) for n in names}
    raw_uniqueness, family_divergence = _family_features(arrays, families)
    raw_interaction = _interaction_feature(names, interaction_state)

    f_stability = _normalize_feature(raw_stability)
    f_recent = _normalize_feature(raw_recent)
    f_dispersion = _normalize_feature(raw_dispersion)
    f_uniqueness = _normalize_feature(raw_uniqueness)
    f_interaction = _normalize_feature(raw_interaction)
    raw_regime = {n: float(metrics[n]['regime_context']) for n in names}
    f_regime = _normalize_feature(raw_regime)

    active = bool(context_state.get('active', False))
    score = float(context_state.get('l1_score', 0.0))
    threshold = float(context_state.get('l1_threshold', 1.0))
    if not math.isfinite(score) or not math.isfinite(threshold) or threshold <= 0:
        raise ValueError('invalid context state')
    regime_intensity = float(min(1.0, max(0.0, score / threshold))) if active else 0.0

    factors = {}
    rows = {}
    for n in names:
        drift_health = -1.0 if bool(metrics[n]['drift_active']) else 0.0
        parts = {
            'stability': f_stability[n],
            'recent_quality': f_recent[n],
            'dispersion': f_dispersion[n],
            'family_uniqueness': f_uniqueness[n],
            'interaction': f_interaction[n],
            'regime_alignment': f_regime[n] * regime_intensity,
            'drift_health': drift_health,
        }
        meta_score = sum(FEATURE_COEFFICIENTS[k] * parts[k] for k in FEATURE_COEFFICIENTS)
        meta_score = float(np.clip(meta_score, -1.0, 1.0))
        factor = float(math.exp(strength * meta_score))
        factors[n] = factor
        rows[n] = {
            'features': parts,
            'meta_score': meta_score,
            'factor': factor,
            'raw': {
                'stability': raw_stability[n],
                'recent_quality': raw_recent[n],
                'dispersion': raw_dispersion[n],
                'family_uniqueness': raw_uniqueness[n],
                'interaction': raw_interaction[n],
                'regime_context': raw_regime[n],
                'drift_active': bool(metrics[n]['drift_active']),
            },
        }

    audit = {
        'schema': SCHEMA,
        'strength': strength,
        'max_strength': MAX_META_STRENGTH,
        'coefficients': FEATURE_COEFFICIENTS,
        'regime_active': active,
        'regime_intensity': regime_intensity,
        'family_divergence': family_divergence,
        'signals': rows,
        'factor_min': float(min(factors.values())),
        'factor_max': float(max(factors.values())),
        'weight_effect_enabled': bool(strength > 0.0),
        'causal_semantics': 'uses only pre-result signal metrics/context and interaction state learned from prior adjudicated outcomes',
    }
    audit['sha256'] = sha256_json(audit)
    return factors, audit
