"""Exact, bounded research-only solver for Mega-Sena primary card candidates.

No production import or call path is changed. Never reads actual draw outcomes.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import asdict
from typing import Any, Mapping

from smart_primary_card_selector import (
    PrimaryCardSelectorConfig,
    _band,
    _coerce_scores,
    _counts,
    _normalized,
    _number,
    sha256_json,
)

SCHEMA = "SMART_PRIMARY_CARD_SELECTOR_EXACT_RESEARCH_1"


def _better(new: tuple[float, tuple[int, ...]], old: tuple[float, tuple[int, ...]] | None) -> bool:
    """Stable exact-score ordering; lexicographic tie-break is deterministic."""
    return old is None or new[0] > old[0] or (new[0] == old[0] and new[1] < old[1])


def _group_best(
    candidates: list[int], weights: dict[int, float], mandatory_top3: frozenset[int],
    limit: int,
) -> tuple[dict[tuple[int, bool], tuple[float, tuple[int, ...]]], int]:
    # (count, contains_champion_top3) -> optimal weighted subset.
    dp: dict[tuple[int, bool], tuple[float, tuple[int, ...]]] = {(0, False): (0.0, ())}
    visited = 0
    for number in candidates:
        prior = list(dp.items())
        for (count, has_top3), (score, subset) in prior:
            if count >= limit:
                continue
            visited += 1
            key = (count + 1, has_top3 or number in mandatory_top3)
            proposal = (score + weights[number], tuple(sorted((*subset, number))))
            if _better(proposal, dp.get(key)):
                dp[key] = proposal
    return dp, visited


def _select_exact_pool(
    scores: dict[int, float], ranking: list[int],
    cfg: PrimaryCardSelectorConfig, pool_size: int,
) -> tuple[tuple[float, tuple[int, ...]] | None, dict[str, Any]]:
    cands = ranking[:pool_size]
    norm = _normalized(scores, cands)
    position = {n: i for i, n in enumerate(cands)}
    weight = {
        n: cfg.score_weight * norm[n] +
           cfg.rank_weight * ((len(cands) - position[n]) / len(cands))
        for n in cands
    }
    if not all(math.isfinite(w) for w in weight.values()):
        raise ValueError("research selector objective weights must be finite")
    top3 = frozenset(ranking[:3])
    states = {}
    visited = 0
    for band in ("low", "mid", "high"):
        grouped = [n for n in cands if _band(n) == band]
        states[band], count = _group_best(grouped, weight, top3, cfg.numbers_per_card)
        visited += count

    best = None
    considered = feasible = 0
    for l in range(cfg.min_low_band, cfg.max_low_band + 1):
        for m in range(cfg.min_mid_band, cfg.max_mid_band + 1):
            hi = 6 - l - m
            if not cfg.min_high_band <= hi <= cfg.max_high_band:
                continue
            # Enumerate at most two presence flags per band, NOT 60 choose 6 subsets.
            for a, b, c in itertools.product((False, True), repeat=3):
                if cfg.require_top3_presence and not (a or b or c):
                    continue
                st_l = states["low"].get((l, a))
                st_m = states["mid"].get((m, b))
                st_h = states["high"].get((hi, c))
                if st_l is None or st_m is None or st_h is None:
                    continue
                considered += 1
                selected = tuple(sorted((*st_l[1], *st_m[1], *st_h[1])))
                assert len(selected) == len(set(selected)) == 6
                counts = {"low": l, "mid": m, "high": hi}
                bal = 1 - (abs(l - 2.5) + abs(m - 2.5) + abs(hi - 1)) / 6
                concentration = max(counts.values()) - min(counts.values())
                objective = (cfg.score_weight * sum(norm[n] for n in selected)
                           + cfg.rank_weight * sum((len(cands) - position[n]) / len(cands) for n in selected)
                           + cfg.band_balance_weight * bal
                           - cfg.concentration_penalty * max(0, concentration - 3))
                if not math.isfinite(objective):
                    raise ValueError("research selector objective must be finite")
                feasible += 1
                trial = (float(objective), selected)
                if best is None or trial[0] > best[0] or (math.isclose(trial[0], best[0]) and trial[1] < best[1]):
                    best = trial

    return best, {
        "candidate_pool": cands,
        "candidate_pool_size": len(cands),
        "evaluated_combinations": visited + considered,
        "candidate_state_evaluations": visited,
        "final_state_evaluations": considered,
        "feasible_state_count": feasible,
        "theoretical_combinations": math.comb(pool_size, 6),
    }


def select_primary_card_research(
    aggregate_scores: Mapping[int | str, float],
    ranking60: list[int] | tuple[int, ...] | None = None,
    config: PrimaryCardSelectorConfig | None = None,
) -> dict[str, Any]:
    """Exact dynamic-programming selector for frozen score vectors, research only.

    Important: no result argument is accepted, and production defaults are unchanged.
    Scientific gains must be demonstrated prospectively before any adoption.
    """
    cfg = config if config is not None else PrimaryCardSelectorConfig()
    cfg.validate()
    scores = _coerce_scores(aggregate_scores)
    ranking = ([_number(n) for n in ranking60] if ranking60 is not None
               else sorted(scores, key=lambda n: (-scores[n], n)))
    if len(ranking) != 60 or set(ranking) != set(range(1, 61)):
        raise ValueError("ranking60 must contain exactly 1..60 without duplicates")

    pools = list(range(cfg.candidate_pool_size, cfg.max_candidate_pool_size + 1, 2))
    if pools[-1] != cfg.max_candidate_pool_size:
        pools.append(cfg.max_candidate_pool_size)
    attempts = []
    best = meta = None
    for pool in pools:
        best, meta = _select_exact_pool(scores, ranking, cfg, pool)
        attempts.append({
            "candidate_pool_size": pool,
            "solved": best is not None,
            "states_visited": meta["evaluated_combinations"],
        })
        if best is not None:
            break
    if best is None:
        raise ValueError("no feasible research card under the candidate limits")

    chosen = list(best[1])
    report = {
        "schema": SCHEMA,
        "status": "RESEARCH_ONLY",
        "solver_status": "EXACT_OPTIMAL",
        "solver": "BAND_CARDINALITY_TOP3_STATE_DYNAMIC_PROGRAMMING",
        "model_promotion_authorized": False,
        "result_used": False,
        "scientific_superiority_proven": False,
        "numbers_per_card": 6,
        "pure_champion_top6_sorted": sorted(ranking[:6]),
        "selected_numbers": chosen,
        "selected_band_counts": _counts(chosen),
        "objective_value": best[0],
        "config": asdict(cfg),
        "adaptive_attempts": attempts,
        **meta,
    }
    report["sha256"] = sha256_json(report)
    return report