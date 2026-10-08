from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "SMART_F11_PREDICTIVE_NON_REGRESSION_V1"
BASELINE_HEAD = "d3c411cbc6e22f0b332fb37be11ead0e2a7d9d77"
BASELINE_SOURCE_SHA256 = {
    "smart_signal_agent.py": "04f1abc512178ffff767964021438fc9d8bcf52ec67ce88c2823542264a3f02f",
    "smart_ai_fine_tuning.py": "f54d6575d891df6711c6798c9d0116b0c73d38c3308077e5b807061455407e4d",
    "smart_fine_tuning_lifecycle.py": "c0a205b40e53be54176e2c8d1764cee08819c1b64048d9f96477db722b47cc9a",
    "smart_champion_challenger.py": "8b643a2677b914263f0ecbd9cb650bc6f58dc83b5de056a924e4a5bafd4269df",
    "smart_full_process_pipeline.py": "f154252a116604941e6ce05adac0e5b52acba62e4ccb516a642f8be921e3c9cc",
    "smart_portfolio_pipeline.py": "b3812152dc59e314932168dc2b4c4ccbee4eef39bc1822868490584c6cb97e7c",
    "smart_primary_card_selector.py": "97c6642203419924f61b257d15bcd352bb758f1745cb41eaea606f9afab249ba",
    "smart_v2_engine.py": "edf434aabe1a140a6b3fdb16aaa332cbc46077545abebd1612b109a6839a074a",
    "smart_rank_score_calibration.py": "0a35f4462105a373b202c1c37c34b334e628ad0916061ff86f2c0df2e02a2333",
    "smart_bounded_online_learning.py": "72b73f296015de8f4f71c75a15e16594b81a4ec59b17b6df80526c3b4ec28d07",
    "smart_portfolio_optimizer.py": "10c634183327bf1d4e0387f37dd6c9f73097514f6131cb479dce29662f1b57c8",
    "smart_prospective_cycle.py": "df9d69c0942d27fe0082037763b55e52aff64d022f5c0702546acf1c72b53761",
    "smart_prospective_authority.py": "69a69477b4f87cf55f79b726691c8ad4ff1e747dedc223c42b9b21697d7d2f4c",
    "smart_learning_epoch_reset.py": "d4e899585fe91b3752f239f74e47fb4d90e359b43e2505bbe7efd83ca4178e61"
}
HISTORICAL_REFERENCE_GIT_BLOB = {
    "SMART_P10_HISTORICAL_NONREGRESSION.json": "c31cf066cae6cb450af8abcadb837cf7bd8c029f",
    "SMART_P05_FINAL_HOLDOUT.json": "a587a710de3c998c31259ad95ad0a0eef55d7b48",
    "SMART_P06_FINAL_HOLDOUT.json": "91fc4a524cb256224ebddca57d41f12ce6e74dfa",
    "SMART_AI_FINE_TUNING_CURRENT.json": "a94d8029202322c16ba1425f7085c0783ae2ff37"
}
REFERENCE_FILES = {
    "p10": "SMART_P10_HISTORICAL_NONREGRESSION.json",
    "p05": "SMART_P05_FINAL_HOLDOUT.json",
    "p06": "SMART_P06_FINAL_HOLDOUT.json",
    "fine_tuning": "SMART_AI_FINE_TUNING_CURRENT.json",
}


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _tracked_blob_sha(root: Path, path: str) -> str | None:
    """Read-only Git clean-filter-aware hash of checked out evidence."""
    tracked = subprocess.run(
        ["git", "rev-parse", "HEAD:" + path],
        cwd=root, capture_output=True, text=True, check=False,
    )
    clean = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", path],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if tracked.returncode != 0 or clean.returncode != 0:
        return None
    return tracked.stdout.strip()


def evaluate(
    root: str | Path,
    *,
    evidence: dict[str, dict[str, Any]] | None = None,
    source_hashes: dict[str, str] | None = None,
    reference_blob_hashes: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    observed_sources = source_hashes if source_hashes is not None else {
        path: hashlib.sha256((root / path).read_bytes()).hexdigest()
        for path in BASELINE_SOURCE_SHA256
    }
    observed_blobs = reference_blob_hashes if reference_blob_hashes is not None else {
        path: _tracked_blob_sha(root, path) for path in HISTORICAL_REFERENCE_GIT_BLOB
    }
    datasets = evidence if evidence is not None else {
        kind: json.loads((root / path).read_text(encoding="utf-8-sig"))
        for kind, path in REFERENCE_FILES.items()
    }
    p10 = datasets["p10"]
    p05 = datasets["p05"]
    p06 = datasets["p06"]
    tune = datasets["fine_tuning"]
    final_p05 = p05["final_holdout_2801_3050"]
    final_p06 = p06["final_holdout"]
    tune_gain = tune["adjudication"]["gains_vs_baseline"]
    observed_delta = float(final_p06["mean_brier"]) - float(final_p06["uniform_brier"])
    holdout_delta = int(final_p05["p05_hits"]) - int(final_p05["baseline_hits"])
    check: dict[str, bool] = {}
    errors: list[str] = []

    def gate(name: str, ok: bool) -> None:
        check[name] = bool(ok)
        if not ok:
            errors.append(name)

    gate("production_prediction_source_unchanged_from_F10",
         observed_sources == BASELINE_SOURCE_SHA256)
    gate("historical_artifacts_git_blob_identical_to_F10",
         observed_blobs == HISTORICAL_REFERENCE_GIT_BLOB)
    gate("historical_evaluation_cutoffs_valid",
         p10.get("data_cutoff") == 3050
         and int(final_p05["n"]) == 250
         and final_p06["start"] == 2801 and final_p06["end"] == 3050
         and int(final_p06["n"]) == 250
         and int(tune["target_contest"]) - int(tune["cutoff_contest"]) == 1)
    gate("p10_baseline_vs_candidate_nonregression",
         p10["schema"] == "SMART_P10_HISTORICAL_NONREGRESSION_1"
         and int(p10["total_delta"]) >= 0
         and int(p10["p10_total_hits"]) >= int(p10["reference_total_hits"])
         and int(p10["holdout_2801_3050"]["delta"]) >= 0
         and all(int(b["p10"]) >= int(b["reference"]) for b in p10["holdout_2801_3050"]["blocks"])
         and p10["next_weights_equal"] is True)
    gate("p05_historical_holdout_nonregression",
         p05["schema"] == "SMART_P05_FINAL_HOLDOUT_1"
         and int(p05["p05_total_hits"]) >= int(p05["baseline_total_hits"])
         and holdout_delta >= 0
         and int(final_p05["delta"]) == holdout_delta
         and p05["guards"]["final_holdout_nonregression"] is True
         and p05["guards"]["total_nonregression"] is True)
    gate("p06_holdout_brier_loss_not_misrepresented",
         p06["schema"] == "SMART_P06_FINAL_HOLDOUT_1"
         and ((observed_delta <= 0) == (p06["guards"]["final_holdout_brier_nonregression_vs_uniform"] is True))
         and ((observed_delta <= 0) or p06["guards"]["prospective_predictive_claim"] is False)
         and p06["guards"]["ranking_not_reordered"] is True
         and p06["guards"]["weights_not_changed_by_p06"] is True)
    guard = tune["guardrails"]
    selection = tune["selection"]
    adjudication = tune["adjudication"]
    all_nonreg = all(float(v) >= 0 for v in tune_gain.values())
    has_gain_validation = float(tune_gain["validation"]) > 0
    can_promote = has_gain_validation and all_nonreg
    gate("fine_tuning_promotion_requires_causal_nonregression",
         tune["schema"] == "SMART_AI_FINE_TUNING_1"
         and tune["status"] == "PASS"
         and (
             can_promote or
             (adjudication["promotion_authorized"] is False
              and adjudication["effective_candidate_id"] == adjudication["baseline_candidate_id"])
         )
         and (not adjudication["promotion_authorized"] or can_promote)
         and (adjudication["non_regressive_all_partitions"] is all_nonreg))
    gate("no_holdout_selection_or_future_result_leakage",
         selection["holdout_used_for_selection"] is False
         and guard["holdout_used_for_selection"] is False
         and guard["future_result_used"] is False
         and guard["test_result_hyperparameter_selection_prohibited"] is True
         and p10["holdout_used_for_tuning"] is False
         and p05["guards"]["future_leakage"] is False
         and p06["guards"]["future_leakage"] is False)
    gate("no_unproven_prospective_superiority_claim",
         p10["prospective_predictive_claim"] is False
         and p05["guards"]["prospective_claim"] is False
         and p06["guards"]["prospective_predictive_claim"] is False)

    return_value = {
        "schema": SCHEMA,
        "status": "PASS" if all(check.values()) else "FAIL",
        "baseline_head": BASELINE_HEAD,
        "candidate_scope": "F10_TO_F11_UNCHANGED_PREDICTIVE_IMPLEMENTATION",
        "claim_scope": "Engineering non-regression and causal rejection of weaker candidates, not 6/6 or prospective predictive superiority.",
        "checks": check,
        "errors": errors,
        "comparison": {
            "p10": {
                "reference_total_hits": int(p10["reference_total_hits"]),
                "candidate_total_hits": int(p10["p10_total_hits"]),
                "total_delta": int(p10["total_delta"]),
                "holdout_reference_hits": int(p10["holdout_2801_3050"]["reference_hits"]),
                "holdout_candidate_hits": int(p10["holdout_2801_3050"]["p10_hits"]),
                "holdout_delta": int(p10["holdout_2801_3050"]["delta"]),
                "interpretation": "HISTORICAL_TIE_NOT_PROSPECTIVE_PROOF",
            },
            "p05": {
                "baseline_holdout_hits": int(final_p05["baseline_hits"]),
                "candidate_holdout_hits": int(final_p05["p05_hits"]),
                "holdout_delta": holdout_delta,
                "intermediate_validation_delta": int(p05["intermediate_validation_2201_2800"]["delta"]),
                "interpretation": "HISTORICAL_HOLDOUT_NONREGRESSION_NO_SUPERIORITY",
            },
            "p06": {
                "candidate_holdout_mean_brier": float(final_p06["mean_brier"]),
                "uniform_holdout_mean_brier": float(final_p06["uniform_brier"]),
                "candidate_minus_uniform_holdout_brier": observed_delta,
                "interpretation": "HISTORICAL_HOLDOUT_BRIER_REGRESSION"
                if observed_delta > 0 else "HISTORICAL_HOLDOUT_NOT_WORSE",
                "approved_for_predictive_promotion": False,
            },
            "fine_tuning": {
                "target_contest": int(tune["target_contest"]),
                "cutoff_contest": int(tune["cutoff_contest"]),
                "selection_validation_gain": float(tune_gain["validation"]),
                "non_regressive_all_partitions": all_nonreg,
                "promotion_authorized": adjudication["promotion_authorized"],
                "effective_candidate_id": adjudication["effective_candidate_id"],
                "interpretation": "BASELINE_RETAINED_NOT_PROVEN_SUPERIOR"
                if adjudication["promotion_authorized"] is False else "PROMOTION_REQUIRES_NEW_PROSPECTIVE_PROOF",
            },
        },
        "sources": {
            "baseline_source_sha256": BASELINE_SOURCE_SHA256,
            "observed_source_sha256": observed_sources,
            "historical_baseline_git_blobs": HISTORICAL_REFERENCE_GIT_BLOB,
            "observed_historical_git_blobs": observed_blobs,
        },
        "scientific_status": "UNPROVEN_PROSPECTIVE_6_OF_6",
        "prospective_advantage_proven": False,
        "six_of_six_proven": False,
    }
    return_value["sha256"] = _sha256_json(return_value)
    return return_value


def main() -> int:
    parser = argparse.ArgumentParser(description="F11 predictive non-regression evidence gate")
    parser.add_argument("--write", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    report = evaluate(root)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        path = args.write if args.write.is_absolute() else root / args.write
        path.write_text(text, encoding="utf-8")
    if args.check:
        path = args.check if args.check.is_absolute() else root / args.check
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            raise SystemExit("F11 non-regression report stale or missing")
    print(json.dumps({"status": report["status"], "checks": report["checks"],
                      "comparison": report["comparison"], "scientific_status": report["scientific_status"]},
                     ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
