from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import hypergeom

import smart_v2_engine as e
from smart_portfolio_optimizer import PortfolioConfig, optimize_portfolio

BACKTEST_SCHEMA = "SMART_PORTFOLIO_BACKTEST_V1"


@dataclass(frozen=True)
class BudgetPolicy:
    game_count: int
    candidate_pool_size: int
    max_pairwise_overlap: int
    coverage_bonus: float = 2.0
    rank_bonus: float = 0.02
    time_limit_seconds: float = 2.0
    require_full_candidate_coverage: bool = False
    min_number_exposure: int | None = None
    max_number_exposure: int | None = None

    def optimizer_config(self) -> PortfolioConfig:
        return PortfolioConfig(
            game_count=self.game_count,
            candidate_pool_size=self.candidate_pool_size,
            max_pairwise_overlap=self.max_pairwise_overlap,
            coverage_bonus=self.coverage_bonus,
            rank_bonus=self.rank_bonus,
            time_limit_seconds=self.time_limit_seconds,
            random_seed=42,
            require_full_candidate_coverage=self.require_full_candidate_coverage,
            min_number_exposure=self.min_number_exposure,
            max_number_exposure=self.max_number_exposure,
        )


DEFAULT_POLICIES = (
    BudgetPolicy(1, 6, 5, coverage_bonus=0.0, time_limit_seconds=0.5),
    BudgetPolicy(2, 10, 2, coverage_bonus=0.0, time_limit_seconds=0.05, require_full_candidate_coverage=True, min_number_exposure=1, max_number_exposure=2),
    BudgetPolicy(4, 12, 2, coverage_bonus=0.0, time_limit_seconds=0.05, require_full_candidate_coverage=True, min_number_exposure=2, max_number_exposure=2),
    BudgetPolicy(6, 12, 3, coverage_bonus=0.0, time_limit_seconds=0.05, require_full_candidate_coverage=True, min_number_exposure=3, max_number_exposure=3),
)


def _policy_scores(pre: dict[str, np.ndarray], t: int, elog: dict[str, float], flog: dict[str, float]):
    names = list(pre)
    fams = sorted(set(e.family_of(n) for n in names))
    sc = {n: pre[n][t] for n in names}
    pen, _ = e.redundancy_penalty(sc)
    fw = e.regularize(e.softmax(flog), prior_mix=e.PRIOR_MIX, cap=e.FAMILY_CAP)
    eff: dict[str, float] = {}
    fam_scores: dict[str, np.ndarray] = {}
    for fam in fams:
        fn = [n for n in names if e.family_of(n) == fam]
        ew = e.regularize(e.softmax({n: elog[n] for n in fn}), prior_mix=e.PRIOR_MIX, cap=e.EXPERT_CAP_WITHIN_FAMILY)
        adj = {n: ew[n] * pen[n] for n in fn}
        z = sum(adj.values())
        adj = {n: v / z for n, v in adj.items()}
        for n in fn:
            eff[n] = fw[fam] * adj[n]
        fam_scores[fam] = sum(adj[n] * sc[n] for n in fn)
    agg = sum(eff[n] * sc[n] for n in names)
    return sc, fam_scores, agg


def _update_hedge(sc, fam_scores, actual, elog, flog, eta):
    actual_set = set(int(x) for x in actual)
    for name in sc:
        top, _ = e.rank_top6(sc[name])
        elog[name] += eta * (len(set(top) & actual_set) - e.UNIFORM_EXPECTED_HITS)
    for fam in fam_scores:
        top, _ = e.rank_top6(fam_scores[fam])
        flog[fam] += eta * (len(set(top) & actual_set) - e.UNIFORM_EXPECTED_HITS)


def _game_metrics(games: list[list[int]], actual) -> dict[str, Any]:
    actual_set = set(int(x) for x in actual)
    hits = [len(set(game) & actual_set) for game in games]
    union = set().union(*(set(g) for g in games))
    return {
        "game_hits": hits,
        "sum_game_hits": int(sum(hits)),
        "best_game_hits": int(max(hits)),
        "union_hits": int(len(union & actual_set)),
        "any_3plus": int(any(h >= 3 for h in hits)),
        "any_4plus": int(any(h >= 4 for h in hits)),
        "any_5plus": int(any(h >= 5 for h in hits)),
        "any_6": int(any(h >= 6 for h in hits)),
    }


def _uniform_baseline(game_count: int, contests: int) -> dict[str, float]:
    rv = hypergeom(M=60, n=6, N=6)
    probs = {k: float(rv.pmf(k)) for k in range(7)}
    p3 = sum(probs[k] for k in range(3, 7))
    p4 = sum(probs[k] for k in range(4, 7))
    p5 = probs[5] + probs[6]
    p6 = probs[6]
    return {
        "expected_sum_game_hits": float(contests * game_count * 0.6),
        "expected_mean_hits_per_game": 0.6,
        "expected_contests_any_3plus_independent_games": float(contests * (1.0 - (1.0 - p3) ** game_count)),
        "expected_contests_any_4plus_independent_games": float(contests * (1.0 - (1.0 - p4) ** game_count)),
        "expected_contests_any_5plus_independent_games": float(contests * (1.0 - (1.0 - p5) ** game_count)),
        "expected_contests_any_6_independent_games": float(contests * (1.0 - (1.0 - p6) ** game_count)),
        "single_game_hit_probabilities": {str(k): probs[k] for k in range(7)},
    }


def run_backtest(
    data_path: str | Path,
    eval_from_contest: int = 2751,
    eval_through_contest: int | None = None,
    hedge_start_index: int = 1000,
    eta: float = math.log(2),
    policies: tuple[BudgetPolicy, ...] = DEFAULT_POLICIES,
) -> dict[str, Any]:
    data_path = Path(data_path)
    draws, contests = e.load_draws(data_path)
    pre = e.precompute_scores(e.onehot(draws))
    names = list(pre)
    fams = sorted(set(e.family_of(n) for n in names))
    elog = {n: 0.0 for n in names}
    flog = {f: 0.0 for f in fams}
    rows: dict[int, list[dict[str, Any]]] = {p.game_count: [] for p in policies}
    start_clock = time.time()

    for t in range(hedge_start_index, len(draws)):
        sc, fam_scores, agg = _policy_scores(pre, t, elog, flog)
        contest = int(contests[t])
        if contest >= eval_from_contest and (eval_through_contest is None or contest <= eval_through_contest):
            scores = {str(i + 1): float(agg[i]) for i in range(60)}
            for policy in policies:
                if policy.game_count == 1:
                    top, _ = e.rank_top6(agg)
                    portfolio = {
                        "solver_status": "TOP6_DIRECT",
                        "games": [sorted(int(x) for x in top)],
                        "metrics": {
                            "unique_number_count": 6,
                            "max_pairwise_overlap_observed": 0,
                        },
                    }
                else:
                    try:
                        portfolio = optimize_portfolio(scores, policy.optimizer_config())
                    except RuntimeError:
                        retry = PortfolioConfig(
                            game_count=policy.game_count,
                            candidate_pool_size=policy.candidate_pool_size,
                            max_pairwise_overlap=policy.max_pairwise_overlap,
                            coverage_bonus=policy.coverage_bonus,
                            rank_bonus=policy.rank_bonus,
                            time_limit_seconds=max(0.2, policy.time_limit_seconds * 4.0),
                            random_seed=42,
                            require_full_candidate_coverage=policy.require_full_candidate_coverage,
                            min_number_exposure=policy.min_number_exposure,
                            max_number_exposure=policy.max_number_exposure,
                        )
                        portfolio = optimize_portfolio(scores, retry)
                metrics = _game_metrics(portfolio["games"], draws[t])
                rows[policy.game_count].append({
                    "contest": contest,
                    "cutoff_contest": int(contests[t - 1]),
                    "games": portfolio["games"],
                    "solver_status": portfolio["solver_status"],
                    "unique_number_count": int(portfolio["metrics"]["unique_number_count"]),
                    "max_pairwise_overlap": int(portfolio["metrics"]["max_pairwise_overlap_observed"]),
                    **metrics,
                })
        _update_hedge(sc, fam_scores, draws[t], elog, flog, eta)

    summaries: dict[str, Any] = {}
    for policy in policies:
        key = str(policy.game_count)
        r = rows[policy.game_count]
        n = len(r)
        total_games = n * policy.game_count
        summary = {
            "policy": asdict(policy),
            "contests": n,
            "total_games": total_games,
            "sum_game_hits": int(sum(x["sum_game_hits"] for x in r)),
            "mean_hits_per_game": float(sum(x["sum_game_hits"] for x in r) / total_games) if total_games else 0.0,
            "mean_best_game_hits": float(sum(x["best_game_hits"] for x in r) / n) if n else 0.0,
            "mean_union_hits": float(sum(x["union_hits"] for x in r) / n) if n else 0.0,
            "contests_any_3plus": int(sum(x["any_3plus"] for x in r)),
            "contests_any_4plus": int(sum(x["any_4plus"] for x in r)),
            "contests_any_5plus": int(sum(x["any_5plus"] for x in r)),
            "contests_any_6": int(sum(x["any_6"] for x in r)),
            "mean_unique_numbers": float(sum(x["unique_number_count"] for x in r) / n) if n else 0.0,
            "max_overlap_observed": int(max((x["max_pairwise_overlap"] for x in r), default=0)),
            "solver_optimal": int(sum(x["solver_status"] == "OPTIMAL" for x in r)),
            "solver_feasible": int(sum(x["solver_status"] == "FEASIBLE" for x in r)),
            "uniform_baseline": _uniform_baseline(policy.game_count, n),
        }
        baseline = summary["uniform_baseline"]
        summary["excess_sum_hits_vs_uniform_expectation"] = float(summary["sum_game_hits"] - baseline["expected_sum_game_hits"])
        summary["excess_any_3plus_vs_uniform_independent_expectation"] = float(summary["contests_any_3plus"] - baseline["expected_contests_any_3plus_independent_games"])
        summary["excess_any_4plus_vs_uniform_independent_expectation"] = float(summary["contests_any_4plus"] - baseline["expected_contests_any_4plus_independent_games"])
        summaries[key] = summary

    return {
        "schema": BACKTEST_SCHEMA,
        "data_file": data_path.name,
        "eval_from_contest": int(eval_from_contest),
        "eval_through_contest": int(min(int(contests[-1]), eval_through_contest)) if eval_through_contest is not None else int(contests[-1]),
        "hedge_start_index": int(hedge_start_index),
        "eta": float(eta),
        "causal": True,
        "future_leakage": False,
        "policies": summaries,
        "rows": {str(k): v for k, v in rows.items()},
        "runtime_seconds": float(time.time() - start_clock),
        "interpretation_contract": {
            "portfolio_layer_only": True,
            "uniform_comparison_is_reference_not_proof_of_predictability": True,
            "historical_backtest_is_engineering_evidence_not_prospective_proof": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Explicit causal dataset path; no temporal default allowed")
    parser.add_argument("--eval-from", type=int, default=2751)
    parser.add_argument("--eval-through", type=int, default=None)
    parser.add_argument("--out", default="SMART_PORTFOLIO_BACKTEST_2751_3052.json")
    args = parser.parse_args()
    result = run_backtest(args.data, args.eval_from, args.eval_through)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"runtime_seconds": result["runtime_seconds"], "policies": result["policies"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

