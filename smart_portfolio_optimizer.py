from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from ortools.sat.python import cp_model

PORTFOLIO_SCHEMA = "SMART_PORTFOLIO_OPTIMIZER_V1"


@dataclass(frozen=True)
class PortfolioConfig:
    game_count: int = 1
    candidate_pool_size: int = 18
    numbers_per_game: int = 6
    max_pairwise_overlap: int = 4
    coverage_bonus: float = 0.35
    rank_bonus: float = 0.02
    time_limit_seconds: float = 5.0
    random_seed: int = 42

    def validate(self) -> None:
        if self.game_count < 1:
            raise ValueError("game_count must be >= 1")
        if self.numbers_per_game != 6:
            raise ValueError("SMART Mega games must contain exactly 6 numbers")
        if not 6 <= self.candidate_pool_size <= 60:
            raise ValueError("candidate_pool_size must be between 6 and 60")
        if not 0 <= self.max_pairwise_overlap < self.numbers_per_game:
            raise ValueError("max_pairwise_overlap must be between 0 and 5")
        if self.coverage_bonus < 0 or self.rank_bonus < 0:
            raise ValueError("objective bonuses must be non-negative")
        if self.time_limit_seconds <= 0:
            raise ValueError("time_limit_seconds must be positive")


def _coerce_scores(scores: Mapping[int | str, float]) -> dict[int, float]:
    out: dict[int, float] = {}
    for raw_n, raw_score in scores.items():
        n = int(raw_n)
        score = float(raw_score)
        if not 1 <= n <= 60:
            raise ValueError(f"number out of range: {n}")
        if not math.isfinite(score):
            raise ValueError(f"non-finite score for number {n}")
        out[n] = score
    if len(out) < 6:
        raise ValueError("at least 6 scored numbers are required")
    return out


def _normalized_scores(scores: Mapping[int, float]) -> dict[int, float]:
    lo = min(scores.values())
    hi = max(scores.values())
    if math.isclose(lo, hi):
        return {n: 1.0 for n in scores}
    return {n: (v - lo) / (hi - lo) for n, v in scores.items()}


def _pairwise_overlap(a: list[int], b: list[int]) -> int:
    return len(set(a).intersection(b))


def optimize_portfolio(
    aggregate_scores: Mapping[int | str, float],
    config: PortfolioConfig | None = None,
) -> dict[str, Any]:
    """Optimize a portfolio of Mega-Sena games without changing predictive scores.

    The optimizer consumes the already-frozen SMART ranking/scores. It optimizes only
    portfolio construction: weighted score, unique-number coverage and pairwise overlap.
    It does not claim to change draw probabilities.
    """
    cfg = config or PortfolioConfig()
    cfg.validate()
    scores = _coerce_scores(aggregate_scores)
    ranked = sorted(scores, key=lambda n: (-scores[n], n))
    candidates = ranked[: min(cfg.candidate_pool_size, len(ranked))]
    if len(candidates) < cfg.numbers_per_game:
        raise ValueError("candidate pool is smaller than a game")

    norm = _normalized_scores({n: scores[n] for n in candidates})
    score_scale = 1_000_000
    utility = {n: int(round(norm[n] * score_scale)) for n in candidates}
    rank_utility = {
        n: int(round((len(candidates) - rank) / len(candidates) * score_scale))
        for rank, n in enumerate(candidates)
    }

    model = cp_model.CpModel()
    x: dict[tuple[int, int], cp_model.IntVar] = {}
    for g in range(cfg.game_count):
        for n in candidates:
            x[g, n] = model.new_bool_var(f"x_g{g}_n{n}")
        model.add(sum(x[g, n] for n in candidates) == cfg.numbers_per_game)

    # Games are interchangeable. Enforce a deterministic binary signature order to
    # remove game-permutation symmetry and make optimality proofs substantially faster.
    if cfg.game_count > 1:
        signatures = [
            sum((1 << idx) * x[g, n] for idx, n in enumerate(candidates))
            for g in range(cfg.game_count)
        ]
        for g in range(cfg.game_count - 1):
            model.add(signatures[g] < signatures[g + 1])

    covered = {n: model.new_bool_var(f"covered_n{n}") for n in candidates}
    for n in candidates:
        for g in range(cfg.game_count):
            model.add(covered[n] >= x[g, n])
        model.add(covered[n] <= sum(x[g, n] for g in range(cfg.game_count)))

    if cfg.game_count > 1:
        for g1 in range(cfg.game_count):
            for g2 in range(g1 + 1, cfg.game_count):
                same_vars = []
                for n in candidates:
                    z = model.new_bool_var(f"same_g{g1}_g{g2}_n{n}")
                    model.add(z <= x[g1, n])
                    model.add(z <= x[g2, n])
                    model.add(z >= x[g1, n] + x[g2, n] - 1)
                    same_vars.append(z)
                model.add(sum(same_vars) <= cfg.max_pairwise_overlap)

    coverage_factor = int(round(cfg.coverage_bonus * 1000))
    rank_factor = int(round(cfg.rank_bonus * 1000))
    selection_term = sum(utility[n] * x[g, n] for g in range(cfg.game_count) for n in candidates)
    coverage_term = sum(utility[n] * covered[n] for n in candidates)
    rank_term = sum(rank_utility[n] * x[g, n] for g in range(cfg.game_count) for n in candidates)
    model.maximize(1000 * selection_term + coverage_factor * coverage_term + rank_factor * rank_term)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = cfg.time_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = cfg.random_seed
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"portfolio optimization failed with CP-SAT status={solver.status_name(status)}")

    games: list[list[int]] = []
    for g in range(cfg.game_count):
        game = sorted(n for n in candidates if solver.value(x[g, n]))
        games.append(game)
    games.sort()

    overlaps = [
        _pairwise_overlap(games[i], games[j])
        for i in range(len(games))
        for j in range(i + 1, len(games))
    ]
    selected = [n for game in games for n in game]
    unique = sorted(set(selected))
    raw_selection_score = sum(scores[n] for n in selected)
    raw_unique_score = sum(scores[n] for n in unique)

    return {
        "schema": PORTFOLIO_SCHEMA,
        "solver": "OR-Tools CP-SAT",
        "solver_status": solver.status_name(status),
        "objective_value": solver.objective_value,
        "best_objective_bound": solver.best_objective_bound,
        "config": asdict(cfg),
        "candidate_pool": candidates,
        "games": games,
        "metrics": {
            "unique_numbers": unique,
            "unique_number_count": len(unique),
            "average_pairwise_overlap": (sum(overlaps) / len(overlaps)) if overlaps else 0.0,
            "max_pairwise_overlap_observed": max(overlaps) if overlaps else 0,
            "raw_selection_score": raw_selection_score,
            "raw_unique_score": raw_unique_score,
        },
        "contract": {
            "predictive_scores_unchanged": True,
            "portfolio_only": True,
            "no_claim_of_draw_predictability_gain": True,
        },
    }


def optimize_from_freeze(
    freeze_path: str | Path,
    config: PortfolioConfig | None = None,
    head: str = "champion",
) -> dict[str, Any]:
    path = Path(freeze_path)
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if head not in payload:
        raise KeyError(f"head not found in freeze: {head}")
    head_payload = payload[head]
    scores = head_payload.get("aggregate_scores")
    if not isinstance(scores, dict):
        raise ValueError(f"freeze head {head!r} has no aggregate_scores")
    result = optimize_portfolio(scores, config=config)
    result["source"] = {
        "freeze_file": path.name,
        "target_contest": payload.get("target_contest"),
        "cutoff_contest": payload.get("cutoff_contest"),
        "head": head,
    }
    return result


__all__ = ["PORTFOLIO_SCHEMA", "PortfolioConfig", "optimize_portfolio", "optimize_from_freeze"]
