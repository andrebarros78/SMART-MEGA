from __future__ import annotations



import math

from collections import defaultdict



RECOVERY_PRIOR_MIX = 0.05

FAMILY_CAP = 0.70

FINAL_EXPERT_CAP = 0.42



REQUIRED_FACTORS = ('utility', 'quality', 'confidence', 'context', 'redundancy_penalty')





def _normalize(weights: dict[str, float]) -> dict[str, float]:

    if any(not math.isfinite(v) or v < 0.0 for v in weights.values()):
        raise ValueError('weights must be finite and non-negative')
    z = sum(weights.values())
    if not math.isfinite(z):
        raise ValueError('weight mass must be finite')

    if z <= 0:

        raise ValueError('weight mass must be positive')

    return {k: v / z for k, v in weights.items()}





def _expert_cap(weights: dict[str, float], cap: float = FINAL_EXPERT_CAP) -> dict[str, float]:
    out = _normalize(dict(weights))
    if not out:
        raise ValueError('weights cannot be empty')
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

        factors = {}
        for k in REQUIRED_FACTORS:
            value = m[k]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f'{name}.{k}: factor must be numeric')
            value = float(value)
            if not math.isfinite(value):
                raise ValueError(f'{name}.{k}: factor must be finite')
            factors[k] = max(0.0, value)

        product = 1.0

        for value in factors.values():

            product *= value

        if not math.isfinite(product):
            raise ValueError(f'{name}: factor product must be finite')
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
