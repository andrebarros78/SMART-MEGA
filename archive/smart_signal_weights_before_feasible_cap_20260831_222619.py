from __future__ import annotations

from collections import defaultdict

RECOVERY_PRIOR_MIX = 0.05
FAMILY_CAP = 0.70
FINAL_EXPERT_CAP = 0.42

REQUIRED_FACTORS = ('utility', 'quality', 'confidence', 'context', 'redundancy_penalty')


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    z = sum(weights.values())
    if z <= 0:
        raise ValueError('weight mass must be positive')
    return {k: v / z for k, v in weights.items()}


def _expert_cap(weights: dict[str, float], cap: float = FINAL_EXPERT_CAP) -> dict[str, float]:
    out = _normalize(dict(weights))
    while True:
        over = [k for k, v in out.items() if v > cap + 1e-15]
        if not over:
            break
        locked_mass = cap * len(over)
        free = [k for k in out if k not in over]
        free_mass = sum(out[k] for k in free)
        for k in over:
            out[k] = cap
        if not free or free_mass <= 0:
            break
        scale = (1.0 - locked_mass) / free_mass
        for k in free:
            out[k] *= scale
    return _normalize(out)


def _family_cap(weights: dict[str, float], families: dict[str, str], cap: float = FAMILY_CAP) -> dict[str, float]:
    out = _normalize(dict(weights))
    fam_totals = defaultdict(float)
    for n, w in out.items():
        fam_totals[families[n]] += w
    if len(fam_totals) <= 1:
        return out
    for fam, total in list(fam_totals.items()):
        if total <= cap + 1e-15:
            continue
        excess = total - cap
        members = [n for n in out if families[n] == fam]
        others = [n for n in out if families[n] != fam]
        scale = cap / total
        for n in members:
            out[n] *= scale
        other_total = sum(out[n] for n in others)
        if other_total > 0:
            for n in others:
                out[n] += excess * out[n] / other_total
        else:
            # Degenerate direct-helper input: preserve the family cap by
            # assigning the redistributed mass uniformly to the other family.
            share = excess / len(others)
            for n in others:
                out[n] += share
    return _normalize(out)


def dynamic_weights(metrics: dict[str, dict], families: dict[str, str]) -> tuple[dict[str, float], dict[str, dict]]:
    if not metrics:
        raise ValueError('metrics cannot be empty')
    raw = {}
    components = {}
    for name, m in metrics.items():
        missing = [k for k in REQUIRED_FACTORS if k not in m]
        if missing:
            raise ValueError(f'{name}: missing factors {missing}')
        factors = {k: max(0.0, float(m[k])) for k in REQUIRED_FACTORS}
        product = 1.0
        for value in factors.values():
            product *= value
        raw[name] = max(product, 1e-15)
        components[name] = {**factors, 'raw_product': raw[name]}

    normalized = _normalize(raw)
    n = len(raw)
    # Recovery prior prevents permanent death by inertia and allows a signal to recover.
    normalized = {k: (1.0 - RECOVERY_PRIOR_MIX) * v + RECOVERY_PRIOR_MIX / n for k, v in normalized.items()}
    normalized = _expert_cap(normalized)
    normalized = _family_cap(normalized, families)
    normalized = _expert_cap(normalized)
    for name in components:
        components[name]['final_weight'] = normalized[name]
    return normalized, components


