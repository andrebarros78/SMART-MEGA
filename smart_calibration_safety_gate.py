"""Production calibration gate: preserve rejected P06 and allow only verified neutralization.

A Brier tie with the uniform reference is a safe rollback, NOT proof of
predictive advantage. Historical P06 results and frozen cards remain immutable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "SMART_CALIBRATION_SAFETY_GATE_1"
POLICY = "P06_NEUTRALIZED_AFTER_FINAL_HOLDOUT_20260830"
UNIFORM_PROBABILITY = 0.1
UNIFORM_BRIER = 0.09


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _read_signed(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict):
        raise ValueError(f"invalid evidence document: {path.name}")
    body = dict(doc)
    observed = body.pop("sha256", None)
    if not isinstance(observed, str) or _digest(body) != observed:
        raise ValueError(f"invalid evidence self-hash: {path.name}")
    return doc


def historical_baseline(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    rejected = _read_signed(root / "SMART_P06_FINAL_HOLDOUT.json")
    adopted = _read_signed(root / "SMART_P06_NEUTRALIZED_VALIDATION.json")
    decision = json.loads((root / "SMART_P06_DECISION.json").read_text(encoding="utf-8-sig"))
    holdout = rejected.get("final_holdout", {})
    neutral = adopted.get("final_holdout", {})
    if (rejected.get("schema") != "SMART_P06_FINAL_HOLDOUT_1"
            or rejected.get("selected_strength") != 0.5
            or holdout.get("start") != 2801 or holdout.get("end") != 3050
            or holdout.get("n") != 250
            or not math.isclose(float(holdout["mean_brier"]), 0.09001357670052432, abs_tol=1e-14)
            or float(holdout["mean_brier"]) <= float(holdout["uniform_brier"])
            or rejected["guards"].get("final_holdout_brier_nonregression_vs_uniform") is not False):
        raise ValueError("historical losing P06 candidate has been altered or misrepresented")
    if (adopted.get("schema") != "SMART_P06_NEUTRALIZED_VALIDATION_1"
            or adopted.get("adopted_strength") != 0.0
            or adopted.get("guards", {}).get("published_probabilities_uniform") is not True
            or neutral.get("start") != 2801 or neutral.get("end") != 3050
            or neutral.get("n") != 250
            or not math.isclose(float(neutral["mean_brier"]), float(neutral["uniform_brier"]), abs_tol=1e-12)
            or decision.get("decision") != "ADOPT_NEUTRALIZED_PROBABILITY_LAYER"
            or decision.get("candidate_rejected") is not True
            or decision.get("adopted_strength") != 0.0):
        raise ValueError("neutralized production P06 authority is invalid")
    return {
        "rejected_candidate_strength": 0.5,
        "rejected_final_holdout_n": 250,
        "rejected_final_holdout_brier": float(holdout["mean_brier"]),
        "uniform_final_holdout_brier": float(holdout["uniform_brier"]),
        "rejected_delta_vs_uniform": float(holdout["mean_brier"]) - float(holdout["uniform_brier"]),
        "adopted_strength": 0.0,
        "adopted_final_holdout_brier": float(neutral["mean_brier"]),
        "adopted_delta_vs_uniform": float(neutral["mean_brier"]) - float(neutral["uniform_brier"]),
    }


def verify_freeze_calibration(root: str | Path, proof: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on any non-neutralized production probability publication."""
    root = Path(root).resolve()
    if not isinstance(proof, dict) or proof.get("status") != "PASS" or proof.get("result_used") is not False:
        raise ValueError("production freeze requires PASS proof and no future results")
    target = proof.get("target_contest")
    cutoff = proof.get("cutoff_contest")
    if type(target) is not int or type(cutoff) is not int or target != cutoff + 1:
        raise ValueError("freeze target/cutoff mismatch")
    source = proof.get("freeze_file")
    expected_sha = proof.get("freeze_sha256")
    if not isinstance(source, str) or not source or not isinstance(expected_sha, str):
        raise ValueError("freeze calibration requires a hash-bound source")
    path = (root / source).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
        raise ValueError("freeze calibration path escapes trusted root")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
        raise ValueError("freeze calibration source SHA-256 mismatch")
    freeze = json.loads(path.read_text(encoding="utf-8-sig"))
    if freeze.get("target_contest") != target or freeze.get("cutoff_contest") != cutoff:
        raise ValueError("freeze calibration contest lineage mismatch")
    challenger = freeze.get("challenger") or {}
    cal = challenger.get("rank_score_calibration") or {}
    if (cal.get("schema") != "SMART_RANK_SCORE_CALIBRATION_1"
            or cal.get("policy_id") != POLICY
            or cal.get("calibration_mode") != "NEUTRALIZED"
            or cal.get("neutralized") is not True
            or cal.get("strength") != 0.0
            or freeze.get("promotion_lineage", {}).get("calibration_strength") != 0.0):
        raise ValueError("unproved nonzero predictive calibration is forbidden in production")
    raw = dict(cal)
    raw_sha = raw.pop("sha256", None)
    raw.pop("probabilities_by_number", None)  # appended after signed calibration audit
    if not isinstance(raw_sha, str) or _digest(raw) != raw_sha:
        raise ValueError("calibration audit hash mismatch")
    probabilities = cal.get("probabilities_by_number")
    if not isinstance(probabilities, dict) or set(probabilities) != {str(i) for i in range(1, 61)}:
        raise ValueError("calibration lacks all 60 probability values")
    if any(type(p) not in (float, int) or not math.isfinite(float(p)) or abs(p - 0.1) > 1e-12
           for p in probabilities.values()):
        raise ValueError("production probabilities must remain uniform until new prospective proof")
    if abs(float(cal.get("probability_sum", 0)) - 6.0) > 1e-10:
        raise ValueError("calibration probability mass invalid")
    return {
        "target_contest": target,
        "cutoff_contest": cutoff,
        "production_policy": POLICY,
        "production_calibration_strength": 0.0,
        "production_brier_reference": UNIFORM_BRIER,
        "all_60_probabilities_uniform": True,
        "future_result_used": False,
        "freeze_sha256": expected_sha,
    }


def evaluate(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    baseline = historical_baseline(root)
    active = _read_signed(root / "SMART_ACTIVE_EPOCH.json")
    if active.get("status") != "FROZEN":
        raise ValueError("audit needs an existing immutable frozen epoch")
    proof_path = root / "runtime" / "learning_epochs" / str(active.get("epoch_id")) / "FULL_PROCESS_PROOF.json"
    proof = _read_signed(proof_path)
    verified = verify_freeze_calibration(root, proof)
    if verified["target_contest"] != active.get("target_contest"):
        raise ValueError("frozen epoch and calibration target differ")
    result = {
        "schema": SCHEMA,
        "status": "PASS",
        "purpose": "REJECT_P06_HOLDOUT_REGRESSION_AND_ENFORCE_PRODUCTION_NEUTRALIZATION",
        "historical_evidence": baseline,
        "production_evidence": verified,
        "historical_candidate_still_rejected": True,
        "historical_holdout_not_reoptimized": True,
        "ranking_and_card_unmodified": True,
        "prospective_superiority_proven": False,
        "six_of_six_proven": False,
        "next_policy": "POSITIVE_CALIBRATION_REQUIRES_NEW_INDEPENDENT_PROSPECTIVE_PROOF",
    }
    result["sha256"] = _digest(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", default="")
    args = parser.parse_args()
    report = evaluate(Path(__file__).resolve().parent)
    if args.write:
        destination = Path(args.write).resolve()
        if destination.parent != Path(__file__).resolve().parent:
            raise ValueError("report output must be in canonical project root")
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "historical": report["historical_evidence"],
                      "production": report["production_evidence"], "predictive_superiority": False},
                     ensure_ascii=False, sort_keys=True))
