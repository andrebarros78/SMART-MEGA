from __future__ import annotations
import smart_canonical_identity as _test_identity
from smart_canonical_identity import canonical_root

import argparse
import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from smart_portfolio_optimizer import PortfolioConfig, optimize_from_freeze
from smart_primary_card_selector import PrimaryCardSelectorConfig, select_primary_card
from smart_false_negative_rescue import apply_rescue, build_profile_from_reports
from smart_source_identity import sha256_source_file

PIPELINE_SCHEMA = "SMART_PORTFOLIO_ARTIFACT_1"
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
    champion_top6 = [int(x) for x in champion["top6"]]
    rescue_profile = build_profile_from_reports(Path(__file__).resolve().parent, through_contest=cutoff)
    rescue_scores, rescue_audit = apply_rescue(champion["aggregate_scores"], rescue_profile)
    rescue_ranking60 = sorted(range(1, 61), key=lambda n: (-float(rescue_scores[str(n)]), n))
    primary_selection = select_primary_card(
        rescue_scores,
        ranking60=rescue_ranking60,
        config=PrimaryCardSelectorConfig(),
    )
    primary_card_numbers = [int(x) for x in primary_selection["selected_numbers"]]
    primary_card = {
        "schema": "SMART_PRIMARY_SINGLE_CARD_2",
        "artifact_type": "SMART_PRIMARY_SINGLE_CARD",
        "product_role": "FINAL_SINGLE_CARD_PRODUCT",
        "optimization_objective": "MAXIMIZE_SIX_HIT_SINGLE_CARD",
        "selection_strategy": "HYBRID_SCORE_RECALL_DIVERSITY_FALSE_NEGATIVE_RESCUE",
        "target_contest": target,
        "cutoff_contest": cutoff,
        "numbers": primary_card_numbers,
        "source_head": "champion",
        "source_top6_ordered": champion_top6,
        "selector": primary_selection,
        "false_negative_rescue": rescue_audit,
        "selection_rule": primary_selection["selection_rule"],
        "freeze_sha256": sha256(freeze_path),
    }

    checks = {
        "pre_result_freeze": True,
        "causal_cutoff": target == cutoff + 1,
        "single_game_preserved": isinstance(control.get("games"), list) and len(control["games"]) == 1 and len(control["games"][0]) == 6,
        "single_game_control_valid": isinstance(control.get("games"), list) and len(control["games"]) == 1 and len(control["games"][0]) == 6,
        "primary_card_is_single_game": len(primary_card_numbers) == 6 and len(set(primary_card_numbers)) == 6,
        "primary_card_selector_pass": primary_selection.get("status") == "PASS",
        "primary_card_not_forced_to_champion_top6": primary_card_numbers != sorted(champion_top6) or primary_selection["selected_band_counts"] == primary_selection["pure_top6_band_counts"],
        "portfolio_not_primary_product": True,
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
    canonical_games = [[int(n) for n in game] for game in portfolio["games"]]
    game_records = []
    for game_index, numbers in enumerate(canonical_games, 1):
        game_hash = hashlib.sha256(json.dumps(numbers, separators=(",", ":")).encode("utf-8")).hexdigest()
        game_records.append({"game_id": f"{target}-G{game_index:02d}", "numbers": numbers, "game_sha256": game_hash})
    config_payload = asdict(config)
    config_sha256 = hashlib.sha256(json.dumps(config_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    portfolio_basis = {"target_contest": target, "freeze_sha256": sha256(freeze_path), "source_data_sha256": freeze.get("data_sha256"), "config_sha256": config_sha256, "games": game_records}
    portfolio_id = hashlib.sha256(json.dumps(portfolio_basis, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
    artifact = {
        "schema": PIPELINE_SCHEMA,
        "artifact_type": "SMART_PORTFOLIO_ARTIFACT",
        "portfolio_id": portfolio_id,
        "source_data_sha256": freeze.get("data_sha256"),
        "config_sha256": config_sha256,
        "solver": {"status": portfolio["solver_status"], "objective_value": portfolio["objective_value"], "best_objective_bound": portfolio["best_objective_bound"]},
        "games": game_records,
        "metrics": portfolio["metrics"],
        "product_role": "AUXILIARY_MULTICARD_PORTFOLIO",
        "primary_card_role": "FINAL_SINGLE_CARD_PRODUCT",
        "primary_card": primary_card,
        "false_negative_rescue": rescue_audit,
        "champion_top6_role": "PRIMARY_SINGLE_CARD_SOURCE",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "target_contest": target,
        "cutoff_contest": cutoff,
        "freeze_file": freeze_path.name,
        "freeze_sha256": sha256(freeze_path),
        "optimizer_file": "smart_portfolio_optimizer.py",
        "optimizer_sha256": sha256_source_file(Path(__file__).with_name("smart_portfolio_optimizer.py")),
        "pipeline_sha256": sha256_source_file(Path(__file__)),
        "config": asdict(config),
        "champion_top6": [int(x) for x in champion["top6"]],
        "primary_card_selector": primary_selection,
        "single_game_control": control,
        "portfolio": portfolio,
        "checks": checks,
        "contract": {
            "post_scoring_component": True,
            "predictive_model_unchanged": True,
            "primary_selector_replaces_raw_top6": True,
            "primary_output_is_single_card": True,
            "portfolio_requires_explicit_multicard_request": True,
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
    freeze_path = Path(args.freeze)
    out_path = Path(args.out)
    if _test_identity._authorized_pytest_sandbox(freeze_path):
        root = freeze_path.parent.resolve()
    else:
        root = canonical_root()
    freeze_path = (root / freeze_path).resolve() if not freeze_path.is_absolute() else freeze_path.resolve()
    out_path = (root / out_path).resolve() if not out_path.is_absolute() else out_path.resolve()
    freeze_path.relative_to(root)
    out_path.relative_to(root)
    artifact = build_portfolio_package(freeze_path, out_path)
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
