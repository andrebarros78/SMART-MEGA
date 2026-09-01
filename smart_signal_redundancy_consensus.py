from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

SCHEMA = 'SMART_FALSE_CONSENSUS_REDUNDANCY_1'
DEFAULT_CORRELATION_THRESHOLD = 0.90
SOFT_FLOOR = 0.15


def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _arrays(scores: dict[str, Any]) -> dict[str, np.ndarray]:
    if not isinstance(scores, dict) or not scores:
        raise ValueError('scores cannot be empty')
    out = {}
    for name in sorted(scores):
        arr = np.asarray(scores[name], dtype=float)
        if arr.shape != (60,) or not np.all(np.isfinite(arr)):
            raise ValueError(f'{name}: expected 60 finite values')
        out[name] = arr
    return out


def _correlation_matrix(arrays: dict[str, np.ndarray]) -> dict[str, dict[str, float]]:
    names = sorted(arrays)
    corr = {n: {} for n in names}
    for i, a_name in enumerate(names):
        a = arrays[a_name]
        for j, b_name in enumerate(names):
            if j < i:
                corr[a_name][b_name] = corr[b_name][a_name]
                continue
            if a_name == b_name:
                c = 1.0
            else:
                b = arrays[b_name]
                if float(np.std(a)) <= 1e-15 or float(np.std(b)) <= 1e-15:
                    c = 0.0
                else:
                    c = float(np.corrcoef(a, b)[0, 1])
            corr[a_name][b_name] = c
    return corr


def _components(corr: dict[str, dict[str, float]], threshold: float) -> list[list[str]]:
    names = sorted(corr)
    unseen = set(names)
    groups = []
    while unseen:
        root = min(unseen)
        stack = [root]
        unseen.remove(root)
        group = []
        while stack:
            cur = stack.pop()
            group.append(cur)
            linked = [n for n in sorted(unseen) if abs(float(corr[cur][n])) >= threshold]
            for n in linked:
                unseen.remove(n)
                stack.append(n)
        groups.append(sorted(group))
    return sorted(groups, key=lambda g: (g[0], len(g)))


def consensus_penalties(scores: dict[str, Any], base_utility: dict[str, float] | None = None,
                        threshold: float = DEFAULT_CORRELATION_THRESHOLD) -> tuple[dict[str, float], dict[str, Any]]:
    if not 0.0 < float(threshold) < 1.0:
        raise ValueError('threshold must be in (0,1)')
    arrays = _arrays(scores)
    names = sorted(arrays)
    if base_utility is None:
        utility = {n: 1.0 / len(names) for n in names}
    else:
        if set(base_utility) != set(names):
            raise ValueError('base_utility ids must match scores')
        utility = {n: max(0.0, float(base_utility[n])) for n in names}
        z = sum(utility.values())
        if z <= 0:
            raise ValueError('base_utility must have positive mass')
        utility = {n: v / z for n, v in utility.items()}
    corr = _correlation_matrix(arrays)
    groups = _components(corr, float(threshold))
    penalties = {n: 1.0 for n in names}
    cluster_rows = []
    for idx, group in enumerate(groups, start=1):
        mass = sum(utility[n] for n in group)
        size = len(group)
        # Anti-multiplicity: a redundant cluster is downweighted so copies cannot scale influence linearly.
        cluster_factor = 1.0 / size
        for n in group:
            cluster_peers = [abs(float(corr[n][p])) for p in group if p != n]
            mean_cluster_peer = float(np.mean(cluster_peers)) if cluster_peers else 0.0
            soft = max(SOFT_FLOOR, 1.0 - mean_cluster_peer)
            anti_multiplicity = max(SOFT_FLOOR, min(1.0, cluster_factor + (1.0 - cluster_factor) * soft))
            all_peers = [abs(float(corr[n][p])) for p in names if p != n]
            mean_abs_all = float(np.mean(all_peers)) if all_peers else 0.0
            novelty = max(SOFT_FLOOR, min(1.0, 1.0 - mean_abs_all))
            penalties[n] = max(SOFT_FLOOR, min(1.0, float(np.sqrt(novelty * anti_multiplicity))))
        cluster_rows.append({'cluster_id': idx, 'members': group, 'size': size, 'base_utility_mass': float(mass),
                             'cluster_factor': float(cluster_factor)})
    weighted_duplicate_pressure = {}
    for n in names:
        weighted_duplicate_pressure[n] = float(sum(utility[p] * max(0.0, (abs(float(corr[n][p])) - threshold) / (1.0 - threshold))
                                                   for p in names if p != n))
    audit = {
        'schema': SCHEMA,
        'threshold': float(threshold),
        'clusters': cluster_rows,
        'correlations': corr,
        'weighted_duplicate_pressure': weighted_duplicate_pressure,
        'penalties': penalties,
        'false_consensus_policy': 'connected redundant cluster receives per-member anti-multiplicity penalty; influence growth must be sublinear',
    }
    audit['sha256'] = sha256_json(audit)
    return penalties, audit
