from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

import smart_v2_engine as e
from smart_b7_predictive_edge import (
    UNIFORM_BRIER,
    UNIFORM_PROBABILITY,
    binary_log_loss,
    brier_score,
    expected_calibration_error,
    sha256_json,
)
from smart_rank_score_calibration import RankScoreCalibrator
from smart_probability_audit import moving_block_mean_ci

SCHEMA = "SMART_B7_CHAMPION_PROBABILITY_WALK_V1"
DEFAULT_STRENGTHS = (0.0, 0.10, 0.25, 0.50, 0.75, 1.0)
DEFAULT_PRIOR_STRENGTH = 20.0


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def split_name(contest: int) -> str:
    c = int(contest)
    if c <= 2200:
        return "calibration"
    if c <= 2700:
        return "validation"
    return "holdout"


def actual_vector(numbers: list[int] | np.ndarray) -> np.ndarray:
    out = np.zeros(60, dtype=float)
    vals = [int(x) for x in numbers]
    if len(vals) != 6 or len(set(vals)) != 6 or min(vals) < 1 or max(vals) > 60:
        raise ValueError("actual draw must contain six unique values in [1,60]")
    out[np.asarray(vals, dtype=int) - 1] = 1.0
    return out


def _row_score(probabilities: dict[str, float], actual_numbers: list[int] | np.ndarray) -> dict[str, float]:
    p = np.asarray([float(probabilities[str(i)]) for i in range(1, 61)], dtype=float)
    y = actual_vector(actual_numbers)
    return {
        "brier": brier_score(p, y),
        "log_loss": binary_log_loss(p, y),
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    b = np.asarray([float(r["brier"]) for r in rows])
    l = np.asarray([float(r["log_loss"]) for r in rows])
    h = np.asarray([int(r["hits"]) for r in rows], dtype=float)
    ub = np.asarray([float(r["uniform_brier"]) for r in rows])
    ul = np.asarray([float(r["uniform_log_loss"]) for r in rows])
    return {
        "n": int(len(rows)),
        "mean_brier": float(b.mean()),
        "uniform_mean_brier": float(ub.mean()),
        "brier_edge_pct": float(100.0 * (ub.mean() - b.mean()) / ub.mean()),
        "mean_log_loss": float(l.mean()),
        "uniform_mean_log_loss": float(ul.mean()),
        "log_loss_edge_pct": float(100.0 * (ul.mean() - l.mean()) / ul.mean()),
        "mean_hits": float(h.mean()),
        "uniform_mean_hits": 0.6,
        "hit_edge_pct": float(100.0 * (h.mean() - 0.6) / 0.6),
    }


def run(data_path: str | Path, start_index: int = 1000, strengths: tuple[float, ...] = DEFAULT_STRENGTHS,
        prior_strength: float = DEFAULT_PRIOR_STRENGTH, bootstrap_replications: int = 3000,
        seed: int = 20260907) -> dict[str, Any]:
    data_path = Path(data_path)
    draws, contests = e.load_draws(data_path)
    champion = e.walk_forward(draws, contests, start=int(start_index))
    if not champion.rows:
        raise ValueError("champion walk-forward produced no rows")
    by_contest = {int(c): draws[i] for i, c in enumerate(contests)}
    uniform_p = np.full(60, UNIFORM_PROBABILITY, dtype=float)
    uniform_log_loss = binary_log_loss(uniform_p, actual_vector([1, 2, 3, 4, 5, 6]))

    calibrators = {float(s): RankScoreCalibrator(strength=float(s), prior_strength=float(prior_strength)) for s in strengths}
    rows_by_strength: dict[str, list[dict[str, Any]]] = {str(float(s)): [] for s in strengths}

    for row in champion.rows:
        contest = int(row["contest"])
        ranking = [int(x) for x in row["ranking60"]]
        actual = [int(x) for x in by_contest[contest]]
        for strength, calibrator in calibrators.items():
            probabilities, audit = calibrator.predict(ranking, row.get("aggregate_scores"))
            score = _row_score(probabilities, actual)
            rec = {
                "contest": contest,
                "cutoff_contest": contest - 1,
                "split": split_name(contest),
                "strength": float(strength),
                "top6": [int(x) for x in row["top6"]],
                "hits": int(row["hits"]),
                "brier": float(score["brier"]),
                "uniform_brier": float(UNIFORM_BRIER),
                "log_loss": float(score["log_loss"]),
                "uniform_log_loss": float(uniform_log_loss),
                "probabilities": probabilities,
                "probability_sum": float(sum(probabilities.values())),
                "calibrator_observations_before_result": int(audit["observations"]),
                "result_used_for_prediction": False,
            }
            rows_by_strength[str(float(strength))].append(rec)
            calibrator.update(ranking, actual, predicted_probabilities=probabilities)

    summaries: dict[str, Any] = {}
    for strength in strengths:
        key = str(float(strength))
        rows = rows_by_strength[key]
        summaries[key] = {
            part: _summarize([r for r in rows if r["split"] == part])
            for part in ("calibration", "validation", "holdout")
        }
        summaries[key]["overall"] = _summarize(rows)

    # Selection is validation-only. Holdout never chooses the calibration strength.
    def validation_key(s: float) -> tuple[float, float, float]:
        v = summaries[str(float(s))]["validation"]
        conservative = min(float(v["brier_edge_pct"]), float(v["log_loss_edge_pct"]))
        return (conservative, float(v["brier_edge_pct"]), -float(s))

    shadow_challenger_strength = max(strengths, key=validation_key)
    shadow_key = str(float(shadow_challenger_strength))
    validation_rows = [r for r in rows_by_strength[shadow_key] if r["split"] == "validation"]
    if not validation_rows:
        raise ValueError("shadow challenger has no validation rows")
    validation_brier_gain = np.asarray([r["uniform_brier"] - r["brier"] for r in validation_rows], dtype=float)
    validation_log_gain = np.asarray([r["uniform_log_loss"] - r["log_loss"] for r in validation_rows], dtype=float)
    validation_brier_ci = moving_block_mean_ci(validation_brier_gain, bootstrap_replications, seed - 2, block_size=25)
    validation_log_ci = moving_block_mean_ci(validation_log_gain, bootstrap_replications, seed - 1, block_size=25)
    validation_gate_pass = bool(validation_brier_ci["lower"] > 0.0 and validation_log_ci["lower"] > 0.0)

    # No-regression rule: absent positive CI on both proper scores, canonical probabilities are neutralized.
    selected_strength = float(shadow_challenger_strength) if validation_gate_pass else 0.0
    selected_key = str(float(selected_strength))
    holdout_rows = [r for r in rows_by_strength[selected_key] if r["split"] == "holdout"]
    shadow_holdout_rows = [r for r in rows_by_strength[shadow_key] if r["split"] == "holdout"]
    if not holdout_rows or not shadow_holdout_rows:
        raise ValueError("selected model has no holdout rows")

    def enrich_holdout(rows: list[dict[str, Any]], ci_seed: int) -> dict[str, Any]:
        key = str(float(rows[0]["strength"]))
        brier_gain = np.asarray([r["uniform_brier"] - r["brier"] for r in rows], dtype=float)
        log_gain = np.asarray([r["uniform_log_loss"] - r["log_loss"] for r in rows], dtype=float)
        brier_ci = moving_block_mean_ci(brier_gain, bootstrap_replications, ci_seed, block_size=25)
        log_ci = moving_block_mean_ci(log_gain, bootstrap_replications, ci_seed + 1, block_size=25)
        p_all = np.asarray([[float(r["probabilities"][str(i)]) for i in range(1, 61)] for r in rows])
        y_all = np.asarray([actual_vector(by_contest[int(r["contest"])]) for r in rows])
        summary = dict(summaries[key]["holdout"])
        summary["ece_10"] = expected_calibration_error(p_all, y_all, bins=10)
        summary["brier_gain_ci95"] = brier_ci
        summary["log_loss_gain_ci95"] = log_ci
        summary["proper_score_positive_ci"] = bool(brier_ci["lower"] > 0.0 and log_ci["lower"] > 0.0)
        summary["prospective_edge_pct"] = float(min(summary["brier_edge_pct"], summary["log_loss_edge_pct"]))
        return summary

    holdout_summary = enrich_holdout(holdout_rows, seed)
    shadow_holdout_summary = enrich_holdout(shadow_holdout_rows, seed + 100)

    result = {
        "schema": SCHEMA,
        "data_file": data_path.name,
        "data_sha256": sha256_file(data_path),
        "engine_file": "smart_v2_engine.py",
        "engine_sha256": sha256_file(Path("smart_v2_engine.py")),
        "calibrator_file": "smart_rank_score_calibration.py",
        "calibrator_sha256": sha256_file(Path("smart_rank_score_calibration.py")),
        "start_index": int(start_index),
        "strength_grid": [float(x) for x in strengths],
        "selection_partition": "validation",
        "evaluation_partition": "holdout",
        "shadow_challenger_strength": float(shadow_challenger_strength),
        "validation_gate": {
            "requires_brier_gain_ci95_lower_gt_zero": True,
            "requires_log_loss_gain_ci95_lower_gt_zero": True,
            "brier_gain_ci95": validation_brier_ci,
            "log_loss_gain_ci95": validation_log_ci,
            "pass": validation_gate_pass,
        },
        "selected_strength": float(selected_strength),
        "canonical_probability_mode": "CALIBRATED_CHALLENGER" if validation_gate_pass else "UNIFORM_BASELINE_NO_REGRESSION",
        "selection_rule": "choose best validation challenger by conservative proper-score edge; activate only if both moving-block 95% gain CIs are strictly positive; otherwise neutralize to uniform",
        "future_leakage": False,
        "result_used_before_prediction": False,
        "summaries": summaries,
        "selected_holdout": holdout_summary,
        "shadow_challenger_holdout": shadow_holdout_summary,
        "selected_rows": rows_by_strength[selected_key],
        "shadow_challenger_rows": rows_by_strength[shadow_key],
        "historical_diagnostic_only": True,
        "production_authority": False,
        "prospective_proof": False,
        "guardrail": "historical validation/holdout evidence may select B7 architecture but cannot establish future predictive proof",
    }
    result["sha256"] = sha256_json(result)
    return result


def write(data_path: str | Path, out_path: str | Path, **kwargs: Any) -> dict[str, Any]:
    result = run(data_path, **kwargs)
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
