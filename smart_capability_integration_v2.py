from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import smart_v2_engine as engine
from smart_data_quality_gate import enforce_draw_quality, sha256_file
from smart_experiment_lab import ExperimentRegistry, ExperimentSpec, monte_carlo_null_hits, sha256_json
from smart_portfolio_optimizer import PortfolioConfig, optimize_from_freeze

INTEGRATION_SCHEMA = "SMART_CAPABILITY_INTEGRATION_V2"
EXPERIMENT_ID = "portfolio-optimizer-pre3053-v3"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _combined_code_hash(root: Path) -> str:
    files = [
        "smart_portfolio_optimizer.py",
        "smart_experiment_lab.py",
        "smart_data_quality_gate.py",
        "smart_validation_gate.py",
    ]
    digests = {name: sha256_file(root / name) for name in files}
    return sha256_json(digests)


def prepare_pre3053_integration(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    data_path = root / "Mega-Sena_through_3052.xlsx"
    freeze_path = root / "SMART_3053_CHAMPION_CHALLENGER_FREEZE.json"
    registry = ExperimentRegistry(root / "SMART_EXPERIMENT_REGISTRY", use_mlflow=True)

    quality = enforce_draw_quality(data_path, expected_max_contest=3052)
    freeze = json.loads(freeze_path.read_text(encoding="utf-8-sig"))
    champion_top6 = sorted(int(n) for n in freeze["champion"]["top6"])

    acceptance = {
        "data_quality_status": "PASS",
        "single_game_top6_preserved": True,
        "multi_game_solver_status": "OPTIMAL",
        "max_pairwise_overlap": 3,
        "minimum_unique_numbers": 12,
        "predictive_scores_unchanged": True,
        "canonical_tests_status": "PASS",
        "non_regression_status": "PASS",
    }

    spec = ExperimentSpec(
        experiment_id=EXPERIMENT_ID,
        hypothesis=(
            "A CP-SAT portfolio layer can optimize multi-game coverage under explicit overlap constraints "
            "while preserving the frozen SMART champion selection for a single game and without changing predictive scores."
        ),
        primary_metric="unique_number_count",
        direction="maximize",
        baseline="frozen champion ranking without portfolio optimization",
        cutoff_contest=3052,
        dataset_sha256=quality.file_sha256,
        code_sha256=_combined_code_hash(root),
        seed=42,
        minimum_effect=6.0,
        guardrails=(
            "single_game_top6_preserved",
            "overlap_constraint_respected",
            "predictive_scores_unchanged",
            "data_quality_pass",
            "canonical_tests_pass",
            "non_regression_pass",
        ),
        analysis_plan=(
            "Use only SMART_3053 frozen champion scores. First verify one-game equivalence. Then solve a 4-game, "
            "12-number candidate portfolio with CP-SAT and max pairwise overlap 3. Evaluate only operational "
            "portfolio metrics; do not claim improved draw predictability."
        ),
        tags={"target_contest": "3053", "capability": "portfolio_optimization"},
    )
    prereg = registry.preregister(spec)

    single = optimize_from_freeze(
        freeze_path,
        PortfolioConfig(game_count=1, candidate_pool_size=18, coverage_bonus=0.0, rank_bonus=0.02),
    )
    portfolio = optimize_from_freeze(
        freeze_path,
        PortfolioConfig(
            game_count=4,
            candidate_pool_size=12,
            max_pairwise_overlap=3,
            coverage_bonus=2.0,
            rank_bonus=0.02,
            time_limit_seconds=10.0,
            random_seed=42,
        ),
    )

    draws, contests = engine.load_draws(data_path)
    diagnostic = engine.walk_forward(draws, contests, start=2750)
    null = monte_carlo_null_hits([int(row["hits"]) for row in diagnostic.rows], replications=20_000, seed=42)
    null["scope"] = {
        "start_contest": int(diagnostic.rows[0]["contest"]),
        "end_contest": int(diagnostic.rows[-1]["contest"]),
        "engineering_diagnostic_only": True,
        "not_independent_prospective_proof": True,
    }

    single_preserved = single["games"][0] == champion_top6
    overlap_ok = portfolio["metrics"]["max_pairwise_overlap_observed"] <= 3
    unique_ok = portfolio["metrics"]["unique_number_count"] >= acceptance["minimum_unique_numbers"]
    solver_optimal = portfolio["solver_status"] == "OPTIMAL"

    integration = {
        "schema": INTEGRATION_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "target_contest": 3053,
        "cutoff_contest": 3052,
        "preregistration": prereg,
        "acceptance": acceptance,
        "pre_final_checks": {
            "data_quality_pass": quality.status == "PASS",
            "single_game_top6_preserved": single_preserved,
            "multi_game_solver_optimal": solver_optimal,
            "overlap_constraint_respected": overlap_ok,
            "minimum_unique_numbers_met": unique_ok,
            "predictive_scores_unchanged": bool(portfolio["contract"]["predictive_scores_unchanged"]),
        },
        "single_game_control": single,
        "portfolio": portfolio,
        "data_quality": quality.to_dict(),
        "null_monte_carlo": null,
        "source_hashes": {
            "freeze_sha256": sha256_file(freeze_path),
            "data_sha256": quality.file_sha256,
            "combined_code_sha256": spec.code_sha256,
        },
    }
    integration["pre_final_status"] = "PASS" if all(integration["pre_final_checks"].values()) else "FAIL"

    _write_json(root / "SMART_3053_PORTFOLIO_OPTIMIZATION.json", integration)
    _write_json(root / "SMART_DATA_QUALITY_3052.json", quality.to_dict())
    _write_json(root / "SMART_NULL_MONTE_CARLO_2751_3052.json", null)
    return integration


if __name__ == "__main__":
    import sys

    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    result = prepare_pre3053_integration(project_root)
    print(json.dumps({
        "status": result["pre_final_status"],
        "experiment_id": result["experiment_id"],
        "single_game": result["single_game_control"]["games"],
        "portfolio_games": result["portfolio"]["games"],
        "unique_numbers": result["portfolio"]["metrics"]["unique_number_count"],
        "max_overlap": result["portfolio"]["metrics"]["max_pairwise_overlap_observed"],
        "solver_status": result["portfolio"]["solver_status"],
    }, ensure_ascii=False, indent=2))
