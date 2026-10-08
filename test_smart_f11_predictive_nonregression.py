from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from smart_f11_predictive_nonregression import (
    BASELINE_SOURCE_SHA256,
    HISTORICAL_REFERENCE_GIT_BLOB,
    evaluate,
)

ROOT = Path(__file__).resolve().parent


def _historical():
    return {
        "p10": json.loads((ROOT / "SMART_P10_HISTORICAL_NONREGRESSION.json").read_text(encoding="utf-8")),
        "p05": json.loads((ROOT / "SMART_P05_FINAL_HOLDOUT.json").read_text(encoding="utf-8")),
        "p06": json.loads((ROOT / "SMART_P06_FINAL_HOLDOUT.json").read_text(encoding="utf-8")),
        "fine_tuning": json.loads((ROOT / "SMART_AI_FINE_TUNING_CURRENT.json").read_text(encoding="utf-8")),
    }


def test_f11_real_baseline_vs_candidate_and_explicit_scientific_boundary():
    result = evaluate(ROOT)
    assert result["status"] == "PASS", result["errors"]
    assert all(result["checks"].values())
    assert result["comparison"]["p10"]["total_delta"] == 0
    assert result["comparison"]["p10"]["holdout_delta"] == 0
    assert result["comparison"]["p05"]["holdout_delta"] == 0
    assert result["comparison"]["p05"]["intermediate_validation_delta"] == -1
    assert result["comparison"]["p06"]["candidate_minus_uniform_holdout_brier"] > 0
    assert result["comparison"]["p06"]["approved_for_predictive_promotion"] is False
    assert result["comparison"]["fine_tuning"]["selection_validation_gain"] == -1
    assert result["comparison"]["fine_tuning"]["effective_candidate_id"] == "baseline"
    assert result["comparison"]["fine_tuning"]["promotion_authorized"] is False
    assert result["six_of_six_proven"] is False
    assert result["prospective_advantage_proven"] is False


def test_f11_certified_report_recomputes_bitwise():
    persisted = json.loads((ROOT / "SMART_F11_PREDICTIVE_NONREGRESSION.json").read_text(encoding="utf-8"))
    assert persisted == evaluate(ROOT)


def test_f11_tampered_material_scoring_hash_fails_closed():
    observed = dict(BASELINE_SOURCE_SHA256)
    observed["smart_signal_agent.py"] = "0" * 64
    result = evaluate(ROOT, source_hashes=observed)
    assert result["status"] == "FAIL"
    assert not result["checks"]["production_prediction_source_unchanged_from_F10"]


def test_f11_modified_historical_evidence_blob_fails_closed():
    blobs = dict(HISTORICAL_REFERENCE_GIT_BLOB)
    blobs["SMART_P06_FINAL_HOLDOUT.json"] = "0" * 40
    result = evaluate(ROOT, reference_blob_hashes=blobs)
    assert result["status"] == "FAIL"
    assert not result["checks"]["historical_artifacts_git_blob_identical_to_F10"]


def test_f11_holdout_loss_falsely_marked_nonregressive_fails():
    docs = deepcopy(_historical())
    assert docs["p06"]["final_holdout"]["mean_brier"] > docs["p06"]["final_holdout"]["uniform_brier"]
    docs["p06"]["guards"]["final_holdout_brier_nonregression_vs_uniform"] = True
    result = evaluate(ROOT, evidence=docs)
    assert result["status"] == "FAIL"
    assert not result["checks"]["p06_holdout_brier_loss_not_misrepresented"]


def test_f11_bad_fine_tuning_promotion_rejected():
    docs = deepcopy(_historical())
    assert docs["fine_tuning"]["adjudication"]["gains_vs_baseline"]["validation"] < 0
    docs["fine_tuning"]["adjudication"]["promotion_authorized"] = True
    docs["fine_tuning"]["adjudication"]["effective_candidate_id"] = "eta_050x"
    result = evaluate(ROOT, evidence=docs)
    assert result["status"] == "FAIL"
    assert not result["checks"]["fine_tuning_promotion_requires_causal_nonregression"]


def test_f11_future_result_leakage_and_holdout_selection_rejected():
    docs = deepcopy(_historical())
    docs["fine_tuning"]["guardrails"]["future_result_used"] = True
    docs["fine_tuning"]["selection"]["holdout_used_for_selection"] = True
    result = evaluate(ROOT, evidence=docs)
    assert result["status"] == "FAIL"
    assert not result["checks"]["no_holdout_selection_or_future_result_leakage"]


def test_f11_fabricated_prospective_advantage_rejected():
    docs = deepcopy(_historical())
    docs["p10"]["prospective_predictive_claim"] = True
    result = evaluate(ROOT, evidence=docs)
    assert result["status"] == "FAIL"
    assert not result["checks"]["no_unproven_prospective_superiority_claim"]


def test_f11_historical_worsening_candidate_loss_rejected():
    docs = deepcopy(_historical())
    docs["p10"]["holdout_2801_3050"]["blocks"][0]["p10"] -= 1
    docs["p05"]["final_holdout_2801_3050"]["p05_hits"] -= 1
    docs["p05"]["final_holdout_2801_3050"]["delta"] -= 1
    result = evaluate(ROOT, evidence=docs)
    assert result["status"] == "FAIL"
    assert not result["checks"]["p10_baseline_vs_candidate_nonregression"]
    assert not result["checks"]["p05_historical_holdout_nonregression"]
