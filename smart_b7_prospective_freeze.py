from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

import smart_v2_engine as e
from freeze_next_research import current_policy
from smart_rank_score_calibration import RankScoreCalibrator
from smart_b7_predictive_edge import sha256_json
from smart_target_schedule import resolve_target_schedule, assert_pre_draw_window

SCHEMA = "SMART_B7_PROSPECTIVE_FREEZE_V1"


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_embedded_hash(document: dict[str, Any]) -> None:
    observed = document.get("sha256")
    canonical = dict(document)
    canonical.pop("sha256", None)
    if not isinstance(observed, str) or observed != sha256_json(canonical):
        raise ValueError("historical report embedded hash mismatch")


def _train_calibrator(strength: float, champion_rows: list[dict[str, Any]], draws: np.ndarray, contests: np.ndarray) -> RankScoreCalibrator:
    by_contest = {int(c): draws[i] for i, c in enumerate(contests)}
    calibrator = RankScoreCalibrator(strength=float(strength), prior_strength=20.0)
    for row in champion_rows:
        contest = int(row["contest"])
        ranking = [int(x) for x in row["ranking60"]]
        actual = [int(x) for x in by_contest[contest]]
        probabilities, _ = calibrator.predict(ranking, row.get("aggregate_scores"))
        calibrator.update(ranking, actual, predicted_probabilities=probabilities)
    return calibrator


def build(data_path: str | Path, historical_report_path: str | Path, target: int, target_date: str,
          frontier_freeze_path: str | Path | None = None, start_index: int = 1000) -> dict[str, Any]:
    data_path = Path(data_path)
    report_path = Path(historical_report_path)
    draws, contests = e.load_draws(data_path)
    target = int(target)
    if int(contests[-1]) >= target:
        raise ValueError("target already present in data; refusing retrospective freeze")
    if int(contests[-1]) != target - 1:
        raise ValueError("data must end immediately before target contest")
    root = Path(__file__).resolve().parent
    schedule = resolve_target_schedule(root, target)
    if str(schedule.get("target_date")) != str(target_date):
        raise ValueError("target_date does not match official schedule authority")
    temporal_guard = assert_pre_draw_window(schedule)

    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    verify_embedded_hash(report)
    selected_strength = float(report["selected_strength"])
    shadow_strength = float(report["shadow_challenger_strength"])
    if report.get("selection_partition") != "validation" or report.get("evaluation_partition") != "holdout":
        raise ValueError("historical report selection/evaluation partitions invalid")
    if report.get("future_leakage") is not False:
        raise ValueError("historical report does not prove future_leakage=false")

    champion = e.walk_forward(draws, contests, start=int(start_index))
    policy = current_policy(draws, start=int(start_index))
    selected_calibrator = _train_calibrator(selected_strength, champion.rows, draws, contests)
    shadow_calibrator = _train_calibrator(shadow_strength, champion.rows, draws, contests)
    selected_probabilities, selected_audit = selected_calibrator.predict(policy["ranking60"], policy["aggregate_scores"])
    shadow_probabilities, shadow_audit = shadow_calibrator.predict(policy["ranking60"], policy["aggregate_scores"])

    frontier_ref = None
    if frontier_freeze_path is not None:
        frontier_path = Path(frontier_freeze_path)
        if not frontier_path.is_file():
            raise ValueError("frontier freeze reference missing")
        frontier = json.loads(frontier_path.read_text(encoding="utf-8-sig"))
        if int(frontier.get("target_contest", -1)) != target or int(frontier.get("cutoff_contest", -1)) != target - 1:
            raise ValueError("frontier freeze target/cutoff mismatch")
        if frontier.get("result_used") is not False:
            raise ValueError("frontier freeze result_used must be false")
        frontier_ref = {
            "file": frontier_path.name,
            "sha256": sha256_file(frontier_path),
            "candidate_count": int(frontier.get("candidate_count", 0)),
            "status": frontier.get("status"),
        }

    freeze = {
        "schema": SCHEMA,
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "target_contest": target,
        "target_date": str(target_date),
        "cutoff_contest": target - 1,
        "frozen_before_result": True,
        "result_used": False,
        "schedule_authority": schedule,
        "temporal_guard": temporal_guard,
        "data_file": data_path.name,
        "data_sha256": sha256_file(data_path),
        "historical_report_file": report_path.name,
        "historical_report_sha256": sha256_file(report_path),
        "engine_file": "smart_v2_engine.py",
        "engine_sha256": sha256_file(Path("smart_v2_engine.py")),
        "calibrator_file": "smart_rank_score_calibration.py",
        "calibrator_sha256": sha256_file(Path("smart_rank_score_calibration.py")),
        "freezer_file": Path(__file__).name,
        "freezer_sha256": sha256_file(Path(__file__)),
        "start_index": int(start_index),
        "canonical": {
            "mode": report["canonical_probability_mode"],
            "selected_strength": selected_strength,
            "top6": [int(x) for x in policy["top6"]],
            "ranking60": [int(x) for x in policy["ranking60"]],
            "probabilities": selected_probabilities,
            "probability_sum": float(sum(selected_probabilities.values())),
            "calibration_audit": selected_audit,
            "predictive_edge_claim": False,
            "jackpot_probability_uplift_claim": False,
        },
        "shadow_challenger": {
            "strength": shadow_strength,
            "top6": [int(x) for x in policy["top6"]],
            "ranking60": [int(x) for x in policy["ranking60"]],
            "probabilities": shadow_probabilities,
            "probability_sum": float(sum(shadow_probabilities.values())),
            "calibration_audit": shadow_audit,
            "validation_gate": report["validation_gate"],
            "historical_holdout": report["shadow_challenger_holdout"],
            "status": "SHADOW_ONLY_UNTIL_FUTURE_OOS_PROOF",
        },
        "policy": {
            "expert_weights": policy["expert_weights"],
            "family_weights": policy["family_weights"],
            "dynamic_weighting": True,
            "redundancy_penalty": True,
        },
        "frontier_shadow_reference": frontier_ref,
        "production_authority": False,
        "vf63_unchanged": True,
        "b7_operational_role": "PARALLEL_PROSPECTIVE_EVIDENCE_COLLECTION",
        "promotion_rule": "no material predictive claim until frozen future outcomes establish proper-score advantage with required evidence",
    }
    freeze["sha256"] = sha256_json(freeze)
    return freeze


def write(data_path: str | Path, historical_report_path: str | Path, out_path: str | Path, target: int, target_date: str,
          frontier_freeze_path: str | Path | None = None, start_index: int = 1000) -> dict[str, Any]:
    out = Path(out_path)
    if out.exists():
        raise FileExistsError(f"refusing to overwrite prospective freeze: {out}")
    freeze = build(data_path, historical_report_path, target, target_date, frontier_freeze_path, start_index)
    out.write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8")
    return freeze


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--historical-report", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--target", required=True, type=int)
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--frontier-freeze")
    parser.add_argument("--start", type=int, default=1000)
    args = parser.parse_args()
    freeze = write(args.data, args.historical_report, args.out, args.target, args.target_date, args.frontier_freeze, args.start)
    print(json.dumps({
        "target": freeze["target_contest"],
        "canonical_mode": freeze["canonical"]["mode"],
        "top6": freeze["canonical"]["top6"],
        "shadow_strength": freeze["shadow_challenger"]["strength"],
        "freeze_sha256": freeze["sha256"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
