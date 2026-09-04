from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from smart_portfolio_optimizer import PortfolioConfig, optimize_from_freeze

PIPELINE_SCHEMA = "SMART_PORTFOLIO_PIPELINE_V1"
CANONICAL_PORTFOLIO_CONFIG = PortfolioConfig(
    game_count=4,
    candidate_pool_size=12,
    numbers_per_game=6,
    max_pairwise_overlap=2,
    coverage_bonus=0.0,
    rank_bonus=0.02,
    time_limit_seconds=30.0,
    random_seed=42,
    require_full_candidate_coverage=True,
    min_number_exposure=2,
    max_number_exposure=2,
)


def sha256(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_portfolio_package(
    freeze_path: str | Path,
    out_path: str | Path | None = None,
    config: PortfolioConfig = CANONICAL_PORTFOLIO_CONFIG,
) -> dict[str, Any]:
    freeze_path = Path(freeze_path)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8-sig"))
    target = int(freeze.get("target_contest"))
    cutoff = int(freeze.get("cutoff_contest"))
    if freeze.get("frozen_before_result") is not True:
        raise ValueError("portfolio pipeline requires a pre-result frozen input")
    if target != cutoff + 1:
        raise ValueError("target contest must immediately follow cutoff contest")
    champion = freeze.get("champion")
    if not isinstance(champion, dict) or not isinstance(champion.get("top6"), list):
        raise ValueError("freeze champion head is missing")

    control = optimize_from_freeze(
        freeze_path,
        PortfolioConfig(
            game_count=1,
            candidate_pool_size=6,
            coverage_bonus=0.0,
            rank_bonus=0.02,
            time_limit_seconds=5.0,
            random_seed=config.random_seed,
        ),
        head="champion",
    )
    portfolio = optimize_from_freeze(freeze_path, config=config, head="champion")
    objective_gap = abs(float(portfolio["objective_value"]) - float(portfolio["best_objective_bound"]))
    checks = {
        "pre_result_freeze": True,
        "causal_cutoff": target == cutoff + 1,
        "single_game_preserved": sorted(control["games"][0]) == sorted(int(x) for x in champion["top6"]),
        "solver_optimal": portfolio["solver_status"] == "OPTIMAL",
        "objective_gap_zero": objective_gap <= 1e-6,
        "overlap_within_contract": portfolio["metrics"]["max_pairwise_overlap_observed"] <= config.max_pairwise_overlap,
        "portfolio_only": portfolio["contract"].get("portfolio_only") is True,
        "scores_unchanged": portfolio["contract"].get("predictive_scores_unchanged") is True,
    }
    if config == CANONICAL_PORTFOLIO_CONFIG:
        checks["canonical_full_candidate_coverage"] = portfolio["metrics"]["unique_number_count"] == config.candidate_pool_size
        checks["canonical_balanced_exposure"] = portfolio["metrics"]["min_number_exposure_observed"] == 2 and portfolio["metrics"]["max_number_exposure_observed"] == 2
        checks["canonical_minimum_overlap_bound"] = portfolio["metrics"]["max_pairwise_overlap_observed"] <= 2
    status = "PASS" if all(checks.values()) else "FAIL"
    artifact = {
        "schema": PIPELINE_SCHEMA,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "target_contest": target,
        "cutoff_contest": cutoff,
        "freeze_file": freeze_path.name,
        "freeze_sha256": sha256(freeze_path),
        "optimizer_file": "smart_portfolio_optimizer.py",
        "optimizer_sha256": sha256(Path(__file__).with_name("smart_portfolio_optimizer.py")),
        "pipeline_sha256": sha256(Path(__file__)),
        "config": asdict(config),
        "champion_top6": [int(x) for x in champion["top6"]],
        "single_game_control": control,
        "portfolio": portfolio,
        "checks": checks,
        "contract": {
            "post_scoring_component": True,
            "predictive_model_unchanged": True,
            "no_retroactive_result_use": True,
            "no_claim_of_predictability_gain": True,
        },
    }
    if status != "PASS":
        raise RuntimeError(f"portfolio package failed validation: {checks}")
    if out_path is not None:
        out = Path(out_path)
        out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        artifact["artifact_file"] = out.name
        artifact["artifact_sha256"] = sha256(out)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    artifact = build_portfolio_package(args.freeze, args.out)
    print(json.dumps({
        "status": artifact["status"],
        "target_contest": artifact["target_contest"],
        "games": artifact["portfolio"]["games"],
        "solver": artifact["portfolio"]["solver_status"],
        "unique_numbers": artifact["portfolio"]["metrics"]["unique_number_count"],
        "max_overlap": artifact["portfolio"]["metrics"]["max_pairwise_overlap_observed"],
        "artifact_sha256": artifact.get("artifact_sha256"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
