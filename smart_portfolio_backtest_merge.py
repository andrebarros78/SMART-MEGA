from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from smart_portfolio_backtest import BACKTEST_SCHEMA, _uniform_baseline

MERGED_SCHEMA = "SMART_PORTFOLIO_BACKTEST_MERGED_V1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _summary(policy: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    game_count = int(policy["game_count"])
    n = len(rows)
    total_games = n * game_count
    baseline = _uniform_baseline(game_count, n)
    summary = {
        "policy": policy,
        "contests": n,
        "total_games": total_games,
        "sum_game_hits": int(sum(x["sum_game_hits"] for x in rows)),
        "mean_hits_per_game": float(sum(x["sum_game_hits"] for x in rows) / total_games) if total_games else 0.0,
        "mean_best_game_hits": float(sum(x["best_game_hits"] for x in rows) / n) if n else 0.0,
        "mean_union_hits": float(sum(x["union_hits"] for x in rows) / n) if n else 0.0,
        "contests_any_3plus": int(sum(x["any_3plus"] for x in rows)),
        "contests_any_4plus": int(sum(x["any_4plus"] for x in rows)),
        "contests_any_5plus": int(sum(x["any_5plus"] for x in rows)),
        "contests_any_6": int(sum(x["any_6"] for x in rows)),
        "mean_unique_numbers": float(sum(x["unique_number_count"] for x in rows) / n) if n else 0.0,
        "max_overlap_observed": int(max((x["max_pairwise_overlap"] for x in rows), default=0)),
        "solver_optimal": int(sum(x["solver_status"] == "OPTIMAL" for x in rows)),
        "solver_feasible": int(sum(x["solver_status"] == "FEASIBLE" for x in rows)),
        "uniform_baseline": baseline,
    }
    summary["excess_sum_hits_vs_uniform_expectation"] = float(summary["sum_game_hits"] - baseline["expected_sum_game_hits"])
    summary["excess_any_3plus_vs_uniform_independent_expectation"] = float(summary["contests_any_3plus"] - baseline["expected_contests_any_3plus_independent_games"])
    summary["excess_any_4plus_vs_uniform_independent_expectation"] = float(summary["contests_any_4plus"] - baseline["expected_contests_any_4plus_independent_games"])
    return summary


def merge(paths: list[Path]) -> dict[str, Any]:
    docs = [json.loads(p.read_text(encoding="utf-8-sig")) for p in paths]
    if not docs:
        raise ValueError("no chunks")
    for d in docs:
        if d.get("schema") != BACKTEST_SCHEMA or d.get("causal") is not True or d.get("future_leakage") is not False:
            raise ValueError("invalid chunk contract")
    keys = sorted(docs[0]["rows"], key=int)
    merged_rows: dict[str, list[dict[str, Any]]] = {k: [] for k in keys}
    reference_policies = {k: docs[0]["policies"][k]["policy"] for k in keys}
    for d in docs:
        if sorted(d["rows"], key=int) != keys:
            raise ValueError("budget keys mismatch")
        for k in keys:
            if d["policies"][k]["policy"] != reference_policies[k]:
                raise ValueError(f"policy mismatch across chunks for budget {k}")
            merged_rows[k].extend(d["rows"][k])
    expected_contests = list(range(min(r["contest"] for r in merged_rows[keys[0]]), max(r["contest"] for r in merged_rows[keys[0]]) + 1))
    for k in keys:
        contests = [int(r["contest"]) for r in merged_rows[k]]
        if len(contests) != len(set(contests)):
            raise ValueError(f"duplicate contest in budget {k}")
        if contests != expected_contests:
            raise ValueError(f"non-contiguous or misaligned contests in budget {k}")
    summaries = {}
    for k in keys:
        summaries[k] = _summary(dict(docs[0]["policies"][k]["policy"]), merged_rows[k])
    return {
        "schema": MERGED_SCHEMA,
        "source_schema": BACKTEST_SCHEMA,
        "causal": True,
        "future_leakage": False,
        "eval_from_contest": expected_contests[0],
        "eval_through_contest": expected_contests[-1],
        "contest_count": len(expected_contests),
        "chunk_files": [{"file": p.name, "sha256": sha256(p)} for p in paths],
        "runtime_seconds_sum": float(sum(float(d["runtime_seconds"]) for d in docs)),
        "policies": summaries,
        "rows": merged_rows,
        "integrity": {
            "contiguous_contests": True,
            "no_duplicate_contests": True,
            "same_contests_all_budgets": True,
            "chunk_count": len(paths),
        },
        "interpretation_contract": {
            "historical_backtest_is_engineering_evidence_not_prospective_proof": True,
            "portfolio_optimizer_does_not_change_predictive_scores": True,
            "uniform_baseline_is_reference_not_predictability_claim": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("chunks", nargs="+")
    args = parser.parse_args()
    paths = [Path(x) for x in args.chunks]
    result = merge(paths)
    out = Path(args.out)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "contest_count": result["contest_count"],
        "from": result["eval_from_contest"],
        "through": result["eval_through_contest"],
        "policies": result["policies"],
        "sha256": sha256(out),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
