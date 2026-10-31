"""Versioned causal next-policy adapter. Does not mutate hash-pinned V2 source.

The frozen V2 walk-forward rows describe PRE-result policies. This adapter
returns an additional, up-to-date policy snapshot incorporating the LAST
observed result, while preserving all historical predictions byte-for-byte.
It does not establish predictive advantage or authorize a production switch.
"""
from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
from typing import Any

import smart_v2_engine as legacy


def walk_forward_next(
    draws: Any,
    contests: Any,
    start: int = 1000,
    eta: float = math.log(2),
    pre: dict | None = None,
    allowed: list[str] | None = None,
) -> legacy.WalkResult:
    """Replay exactly once, then evaluate weights for the NEXT draw.

    No result after the last contest is read. Historical rows are unchanged.
    """
    if not math.isfinite(eta) or eta <= 0:
        raise ValueError("eta must be finite and positive")
    precomputed = pre if pre is not None else legacy.precompute_scores(legacy.onehot(draws))
    names = list(precomputed) if allowed is None else list(allowed)
    if not names or len(set(names)) != len(names) or not set(names).issubset(precomputed):
        raise ValueError("allowed expert names must be distinct and exist in the causal signal set")
    old = legacy.walk_forward(draws, contests, start=start, eta=eta, pre=precomputed, allowed=names)
    if not old.rows:
        return old

    families = sorted({legacy.family_of(name) for name in names})
    expert_log = {name: 0.0 for name in names}
    family_log = {family: 0.0 for family in families}
    for row in old.rows:
        for name in names:
            expert_log[name] += eta * (row["expert_hits"][name] - legacy.UNIFORM_EXPECTED_HITS)
        for family in families:
            family_log[family] += eta * (row["family_hits"][family] - legacy.UNIFORM_EXPECTED_HITS)

    current = {name: precomputed[name][len(draws)] for name in names}
    penalty, _ = legacy.redundancy_penalty(current)
    family_weights = legacy.regularize(
        legacy.softmax(family_log), prior_mix=legacy.PRIOR_MIX, cap=legacy.FAMILY_CAP
    )
    next_weights = {}
    for family in families:
        family_names = [name for name in names if legacy.family_of(name) == family]
        within = legacy.regularize(
            legacy.softmax({name: expert_log[name] for name in family_names}),
            prior_mix=legacy.PRIOR_MIX,
            cap=legacy.EXPERT_CAP_WITHIN_FAMILY,
        )
        adjusted = {name: within[name] * penalty[name] for name in family_names}
        denominator = sum(adjusted.values())
        if not math.isfinite(denominator) or denominator <= 0:
            raise RuntimeError("causal policy produced invalid expert normalization")
        for name, numerator in adjusted.items():
            next_weights[name] = family_weights[family] * numerator / denominator
    if not math.isclose(sum(next_weights.values()), 1, abs_tol=1e-10):
        raise RuntimeError("next policy weights must sum to one")
    return replace(old, final_weights=next_weights, family_weights=family_weights)


def next_policy_snapshot(draws: Any, contests: Any, *, start: int = 1000) -> dict:
    """Expose a next-target policy without giving it production authority."""
    result = walk_forward_next(draws, contests, start=start)
    if not result.rows:
        raise ValueError("at least one scored pre-result draw required")
    return {
        "schema": "SMART_V2_NEXT_POLICY_1",
        "status": "CAUSAL_NEXT_WEIGHTS_REPLAYED",
        "cutoff_contest": int(contests[-1]),
        "next_contest": int(contests[-1]) + 1,
        "next_expert_weights": result.final_weights,
        "next_family_weights": result.family_weights,
        "last_forecast_weights": result.rows[-1]["weights"],
        "historical_rows": len(result.rows),
        "historical_total_hits": result.total_hits,
        "target_result_used": False,
        "predictive_superiority_proven": False,
        "production_switch_authorized": False,
    }
