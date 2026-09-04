from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import adjudicate_signal_challenger as adjudicator
import smart_sequential_prospective_proof as sequential
from smart_v2_engine import load_draws

SCHEMA = "SMART_3054_ADJUDICATION_PREFLIGHT_V1"
TARGET = 3054
CUTOFF = 3053
EXPECTED_FREEZE_SHA256 = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"
EXPECTED_DERIVED_TYPES = {
    "ATTRIBUTION",
    "MARGINAL_UTILITY",
    "INTERACTIONS",
    "MULTI_CHALLENGERS",
    "META_GOVERNOR",
    "RANK_SCORE_CALIBRATION",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _validate_probability_ledger(path: Path) -> dict[str, Any]:
    document = read_json(path)
    if document.get("schema") != "SMART_PROSPECTIVE_LEDGER_V1":
        raise ValueError("probability ledger schema mismatch")
    contract = document.get("contract", {})
    required_contract = {
        "append_only": True,
        "one_registration_per_target": True,
        "retain_all_60_probabilities": True,
        "adjudicate_only_from_official_result": True,
        "no_retroactive_reselection": True,
    }
    for key, expected in required_contract.items():
        if contract.get(key) is not expected:
            raise ValueError(f"probability ledger contract failed: {key}")

    entries = document.get("entries")
    if not isinstance(entries, list):
        raise ValueError("probability ledger entries missing")
    matches = [entry for entry in entries if int(entry.get("target_contest", -1)) == TARGET]
    if len(matches) != 1:
        raise ValueError("probability ledger must contain exactly one registration for target 3054")
    entry = matches[0]
    if int(entry.get("cutoff_contest", -1)) != CUTOFF:
        raise ValueError("probability ledger cutoff mismatch")
    if entry.get("result_used") is not False or entry.get("result_available_at_registration") is not False:
        raise ValueError("probability ledger registration used or had result information")
    if entry.get("production_switch_performed") is not False or entry.get("predictive_weight_authorized") is not False:
        raise ValueError("probability ledger has invalid pre-result authority flags")
    if entry.get("terminal_6of6_proven") is not False:
        raise ValueError("probability ledger falsely declares terminal proof")
    if entry.get("status") != "REGISTERED_PROSPECTIVE_AWAITING_RESULT":
        raise ValueError("probability ledger target is not awaiting result")
    if entry.get("main_freeze_file_sha256") != EXPECTED_FREEZE_SHA256:
        raise ValueError("probability ledger is not bound to the active freeze")
    if entry.get("source_cutoff_before_target") is not True or entry.get("all_60_probabilities_retained") is not True:
        raise ValueError("probability ledger registration causal flags invalid")

    candidates = entry.get("candidate_predictions")
    if not isinstance(candidates, dict) or not candidates:
        raise ValueError("probability ledger candidate predictions missing")
    if int(entry.get("candidate_count", -1)) != len(candidates):
        raise ValueError("probability ledger candidate count mismatch")

    expected_keys = {str(i) for i in range(1, 61)}
    summaries: list[dict[str, Any]] = []
    for candidate_id, candidate in sorted(candidates.items()):
        if not isinstance(candidate, dict):
            raise ValueError("candidate prediction must be an object")
        probabilities = candidate.get("probabilities")
        if not isinstance(probabilities, dict) or set(probabilities) != expected_keys:
            raise ValueError("candidate does not preserve exactly 60 probabilities")
        values = [float(probabilities[str(i)]) for i in range(1, 61)]
        if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in values):
            raise ValueError("candidate probability outside [0,1]")
        probability_sum = math.fsum(values)
        if not math.isclose(probability_sum, 6.0, rel_tol=0.0, abs_tol=1e-8):
            raise ValueError(f"candidate inclusion probabilities do not sum to six: {probability_sum}")
        declared_sum = float(candidate.get("probability_sum", float("nan")))
        if not math.isfinite(declared_sum) or not math.isclose(declared_sum, probability_sum, rel_tol=0.0, abs_tol=1e-10):
            raise ValueError("candidate declared probability sum differs from retained probabilities")
        if candidate.get("production_authority") is not False or candidate.get("result_used") is not False:
            raise ValueError("candidate prediction has invalid authority/result flags")
        top6 = [int(value) for value in candidate.get("top6", [])]
        if len(top6) != 6 or len(set(top6)) != 6 or min(top6) < 1 or max(top6) > 60:
            raise ValueError("candidate frozen top6 invalid")
        summaries.append({
            "candidate_id": candidate_id,
            "family": candidate.get("family"),
            "probability_count": 60,
            "probability_sum": probability_sum,
            "top6": top6,
        })

    return {
        "ledger_schema": document["schema"],
        "registration_schema": entry.get("schema"),
        "entry_sha256": entry.get("entry_sha256"),
        "candidate_count": len(candidates),
        "all_candidates_have_60_probabilities": True,
        "all_probability_sums_equal_six": True,
        "main_freeze_file_sha256": entry.get("main_freeze_file_sha256"),
        "registration_status": entry.get("status"),
        "summaries": summaries,
    }


def _canonical_result_store_status(path: Path) -> dict[str, Any]:
    _, contests = load_draws(path)
    values = [int(value) for value in contests]
    if values[-1] != CUTOFF:
        raise ValueError("canonical result store does not end at pre-3054 cutoff")
    if TARGET in values:
        raise ValueError("canonical result store already contains target 3054")
    if values != list(range(values[0], CUTOFF + 1)):
        raise ValueError("canonical result store is not contiguous through cutoff")
    return {
        "rows": len(values),
        "contest_min": values[0],
        "contest_max": values[-1],
        "target_absent": True,
        "contiguous_through_cutoff": True,
        "sha256": sha256_file(path),
    }


def _sandbox_adjudication(root: Path, ledger: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="smart3054-preflight-") as raw_tmp:
        temp_root = Path(raw_tmp)
        temp_ledger = temp_root / "SMART_SIGNAL_LEDGER.sandbox.json"
        temp_result = temp_root / "synthetic_result_3054.xlsx"
        shutil.copy2(root / "SMART_SIGNAL_LEDGER.json", temp_ledger)
        pd.DataFrame([{
            "Concurso": TARGET,
            "Bola1": 1,
            "Bola2": 2,
            "Bola3": 3,
            "Bola4": 4,
            "Bola5": 5,
            "Bola6": 6,
        }]).to_excel(temp_result, index=False)

        cwd_before = Path.cwd()
        try:
            os.chdir(root)
            result = adjudicator.adjudicate(temp_result, TARGET, temp_ledger)
            sandbox_ledger = read_json(temp_ledger)
            sequence = sequential.validate_target_sequence(
                sandbox_ledger,
                TARGET,
                require_learning=False,
                require_proof=False,
                verify_files=True,
                root=root,
            )
            duplicate_rejected = False
            duplicate_error = None
            try:
                adjudicator.adjudicate(temp_result, TARGET, temp_ledger)
            except ValueError as exc:
                duplicate_rejected = True
                duplicate_error = str(exc)
        finally:
            os.chdir(cwd_before)

        if not duplicate_rejected:
            raise RuntimeError("sandbox accepted duplicate adjudication")
        target_events = [
            event for event in sandbox_ledger.get("events", [])
            if int(event.get("target_contest", -1)) == TARGET
        ]
        adjudications = [event for event in target_events if event.get("event_type") == "ADJUDICATION"]
        if len(adjudications) != 1:
            raise RuntimeError("sandbox does not contain exactly one adjudication")
        derived_types = {
            event.get("event_type") for event in target_events
            if event.get("event_type") in EXPECTED_DERIVED_TYPES
        }
        missing_derived = sorted(EXPECTED_DERIVED_TYPES - derived_types)
        if missing_derived:
            raise RuntimeError(f"sandbox adjudication missing derived events: {missing_derived}")
        if result.get("target_contest") != TARGET:
            raise RuntimeError("sandbox adjudication target mismatch")
        return {
            "synthetic_result": [1, 2, 3, 4, 5, 6],
            "adjudication_created": True,
            "sequence_valid": bool(sequence.get("valid")),
            "sequence": sequence,
            "derived_event_types": sorted(derived_types),
            "missing_derived_event_types": missing_derived,
            "duplicate_adjudication_rejected": duplicate_rejected,
            "duplicate_error": duplicate_error,
            "champion_hits": int(result["champion_hits"]),
            "challenger_hits": int(result["challenger_hits"]),
            "canonical_ledger_used": False,
            "synthetic_result_has_predictive_authority": False,
        }


def build_preflight(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    ledger_path = root / "SMART_SIGNAL_LEDGER.json"
    freeze_path = root / "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json"
    probability_path = root / "SMART_PROBABILITY_PROSPECTIVE_LEDGER.json"
    authority_path = root / "SMART_PROSPECTIVE_EVIDENCE_AUTHORITY.json"
    canonical_result_path = root / "Mega-Sena.xlsx"

    canonical_hashes_before = {
        "signal_ledger": sha256_file(ledger_path),
        "freeze_3054": sha256_file(freeze_path),
        "probability_ledger": sha256_file(probability_path),
        "prospective_authority": sha256_file(authority_path),
        "canonical_result_store": sha256_file(canonical_result_path),
    }
    if canonical_hashes_before["freeze_3054"] != EXPECTED_FREEZE_SHA256:
        raise ValueError("active 3054 freeze hash differs from immutable authority")

    ledger = read_json(ledger_path)
    sequence_before = sequential.validate_target_sequence(
        ledger,
        TARGET,
        require_learning=False,
        require_proof=False,
        verify_files=True,
        root=root,
    )
    if sequence_before.get("adjudicated"):
        raise ValueError("3054 is already adjudicated; pre-result preflight is no longer applicable")
    if sequence_before.get("active_freeze_sha256") != EXPECTED_FREEZE_SHA256:
        raise ValueError("signal ledger active freeze differs from immutable 3054 authority")
    if int(sequence_before.get("derived_event_count", -1)) != 0:
        raise ValueError("post-result derived events already exist before 3054 adjudication")

    probability = _validate_probability_ledger(probability_path)
    authority = read_json(authority_path)
    target_authority = authority.get("targets", {}).get(str(TARGET), authority.get("targets", {}).get(TARGET))
    if not isinstance(target_authority, dict):
        raise ValueError("prospective authority lacks target 3054")
    if target_authority.get("active_or_latest_freeze_hash") != EXPECTED_FREEZE_SHA256:
        raise ValueError("prospective authority freeze hash mismatch")
    if target_authority.get("adjudicated") is not False or target_authority.get("sequential_proof") is not False:
        raise ValueError("prospective authority incorrectly marks 3054 as already completed")

    result_store = _canonical_result_store_status(canonical_result_path)
    sandbox = _sandbox_adjudication(root, ledger)

    canonical_hashes_after = {
        "signal_ledger": sha256_file(ledger_path),
        "freeze_3054": sha256_file(freeze_path),
        "probability_ledger": sha256_file(probability_path),
        "prospective_authority": sha256_file(authority_path),
        "canonical_result_store": sha256_file(canonical_result_path),
    }
    canonical_unchanged = canonical_hashes_before == canonical_hashes_after
    if not canonical_unchanged:
        raise RuntimeError("sandbox preflight mutated canonical prospective artifacts")

    checks = {
        "active_freeze_exact": sequence_before["active_freeze_sha256"] == EXPECTED_FREEZE_SHA256,
        "pre_result_sequence_valid": bool(sequence_before["valid"]),
        "not_yet_adjudicated": sequence_before["adjudicated"] is False,
        "no_post_result_events_before_result": int(sequence_before["derived_event_count"]) == 0,
        "probability_ledger_complete": probability["all_candidates_have_60_probabilities"],
        "probability_mass_valid": probability["all_probability_sums_equal_six"],
        "prospective_authority_unadjudicated": target_authority["adjudicated"] is False,
        "canonical_result_store_through_3053": result_store["contest_max"] == CUTOFF,
        "canonical_result_store_target_absent": result_store["target_absent"],
        "sandbox_adjudication_valid": sandbox["sequence_valid"],
        "sandbox_derived_events_complete": not sandbox["missing_derived_event_types"],
        "duplicate_adjudication_rejected": sandbox["duplicate_adjudication_rejected"],
        "canonical_artifacts_unchanged_by_sandbox": canonical_unchanged,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_contest": TARGET,
        "cutoff_contest": CUTOFF,
        "readiness_status": status,
        "active_freeze_sha256": EXPECTED_FREEZE_SHA256,
        "sequence_before_result": sequence_before,
        "probability_ledger": probability,
        "canonical_result_store": result_store,
        "sandbox_rehearsal": sandbox,
        "canonical_hashes_before": canonical_hashes_before,
        "canonical_hashes_after": canonical_hashes_after,
        "checks": checks,
        "official_result_ingested": False,
        "canonical_adjudication_executed": False,
        "predictive_weight_authorized": False,
        "terminal_6of6_proven": False,
        "next_external_hinge": "official contest 3054 result from accepted official sources",
    }


def write_preflight(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    document = build_preflight(root)
    (root / "SMART_3054_ADJUDICATION_PREFLIGHT.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return document


if __name__ == "__main__":
    import sys

    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    result = write_preflight(project_root)
    print(json.dumps({
        "readiness_status": result["readiness_status"],
        "target": result["target_contest"],
        "candidate_count": result["probability_ledger"]["candidate_count"],
        "sandbox_sequence_valid": result["sandbox_rehearsal"]["sequence_valid"],
        "duplicate_rejected": result["sandbox_rehearsal"]["duplicate_adjudication_rejected"],
        "canonical_unchanged": result["checks"]["canonical_artifacts_unchanged_by_sandbox"],
    }, ensure_ascii=False))
