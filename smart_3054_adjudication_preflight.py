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
from smart_current_epoch_contract import resolve as resolve_current_epoch
from smart_learning_epoch_reset import verify_active_epoch, resolve_locked_prospective_registration
from smart_prospective_authority_lock import adjudicated_lock_evidence
from smart_v2_engine import load_draws

SCHEMA = "SMART_3054_ADJUDICATION_PREFLIGHT_V2"
TARGET = 3054
CUTOFF = 3053
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


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON object required: {path}")
    return obj


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (root / path).resolve()
    else:
        path = path.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"current epoch path escapes project root: {value}") from exc
    return path


def _current_paths(root: Path) -> dict[str, Any]:
    root = root.resolve()
    current = resolve_current_epoch(root)
    if current["target_contest"] != TARGET or current["cutoff_contest"] != CUTOFF:
        raise ValueError("active epoch is not the 3054/3053 prospective target")
    if current["result_used"] is not False:
        raise ValueError("active epoch authority is not pre-result")
    active = verify_active_epoch(root / "SMART_ACTIVE_EPOCH.json")

    if current["status"] == "FROZEN" and current["freeze_authority_present"] is True:
        state_paths = active.get("state_paths", {})
        prospective = active.get("prospective_registration")
        if not isinstance(prospective, dict) and current.get("authority_mode") == "CARRY_FORWARD_UNRESOLVED_PROSPECTIVE":
            prospective = resolve_locked_prospective_registration(root, TARGET, CUTOFF, str(current["freeze_sha256"]))
        if not isinstance(prospective, dict):
            raise ValueError("active epoch lacks prospective probability registration")
        required = ("ledger", "state")
        if any(not isinstance(state_paths.get(key), str) for key in required):
            raise ValueError("active epoch state paths incomplete")
        if not isinstance(prospective.get("probability_ledger_file"), str):
            raise ValueError("active epoch probability ledger path missing")
        ledger_path = _resolve(root, state_paths["ledger"])
        state_path = _resolve(root, state_paths["state"])
        freeze_path = _resolve(root, str(current["freeze_file"]))
        data_path = _resolve(root, str(current["data_file"]))
        probability_path = _resolve(root, prospective["probability_ledger_file"])
        current_generated = current.get("current_engineering_generation_authority") is True
        proof_path = ledger_path.parent / "FULL_PROCESS_PROOF.json" if current_generated else None
        generation_proof_mode = "CURRENT_ENGINEERING_FULL_PROCESS" if current_generated else "CARRY_FORWARD_AUTHORITY_LOCK"
        return {
            "current": current,
            "active": active,
            "ledger": ledger_path,
            "state": state_path,
            "freeze": freeze_path,
            "data": data_path,
            "probability": probability_path,
            "full_process_proof": proof_path,
            "prospective": prospective,
            "generation_proof_mode": generation_proof_mode,
            "adjudication_authority_mode": "ACTIVE_EPOCH_FROZEN",
            "authority_freeze_sha256": str(current["freeze_sha256"]),
            "scientific_adjudication_authority": current.get("scientific_adjudication_authority") is True,
            "current_engineering_generation_authority": current_generated,
        }

    # A temporal recovery may revoke only the current-engineering freeze while an
    # older, causally valid attempt remains immutably locked for adjudication.
    if current["status"] == "RESET_READY":
        locked = current.get("parallel_locked_experiment")
        if not isinstance(locked, dict):
            raise ValueError("3054 preflight requires a FROZEN active epoch or a preserved locked prospective authority")
        if int(locked.get("target_contest", -1)) != TARGET or int(locked.get("cutoff_contest", -1)) != CUTOFF:
            raise ValueError("preserved prospective authority target/cutoff mismatch")
        if locked.get("eligible_for_scientific_adjudication") is not True:
            raise ValueError("preserved prospective authority is not eligible for scientific adjudication")
        if locked.get("eligible_to_prove_post_freeze_engineering_version") is not False:
            raise ValueError("preserved prospective authority could falsely credit current engineering")
        freeze_sha = str(locked.get("freeze_sha256", ""))
        if len(freeze_sha) != 64:
            raise ValueError("preserved prospective authority freeze hash missing")
        prospective = resolve_locked_prospective_registration(root, TARGET, CUTOFF, freeze_sha)
        ledger_path = _resolve(root, str(locked["ledger_file"]))
        state_path = _resolve(root, str(locked["signal_state_file"]))
        freeze_path = _resolve(root, str(locked["freeze_file"]))
        data_path = _resolve(root, str(locked["data_file"]))
        probability_path = _resolve(root, prospective["probability_ledger_file"])
        immutable_hashes = {
            freeze_path: freeze_sha,
            data_path: str(locked["data_sha256"]),
            state_path: str(locked["signal_state_sha256"]),
        }
        for path, expected in immutable_hashes.items():
            if not path.is_file() or sha256_file(path) != expected:
                raise ValueError(f"preserved prospective authority immutable dependency mismatch: {path.name}")

        already_adjudicated = bool(current.get("parallel_experiment_adjudicated"))
        adjudication_evidence = None
        if already_adjudicated:
            lock_file = active.get("prospective_authority_lock_file")
            lock_sha = active.get("prospective_authority_lock_sha256")
            if not isinstance(lock_file, str) or not isinstance(lock_sha, str):
                raise ValueError("adjudicated preserved authority lock reference missing")
            adjudication_evidence = adjudicated_lock_evidence(root / lock_file, root=root)
            if adjudication_evidence["lock_sha256"] != lock_sha:
                raise ValueError("adjudicated preserved authority lock hash mismatch")
            if adjudication_evidence["freeze_sha256"] != freeze_sha:
                raise ValueError("adjudicated preserved authority freeze mismatch")
            if int(adjudication_evidence["target_contest"]) != TARGET:
                raise ValueError("adjudicated preserved authority target mismatch")
            if not ledger_path.is_file():
                raise ValueError("adjudicated append-only signal ledger missing")
        else:
            if not ledger_path.is_file() or sha256_file(ledger_path) != str(locked["ledger_sha256"]):
                raise ValueError("preserved prospective authority dependency mismatch: SMART_SIGNAL_LEDGER.json")
        return {
            "current": current,
            "active": active,
            "ledger": ledger_path,
            "state": state_path,
            "freeze": freeze_path,
            "data": data_path,
            "probability": probability_path,
            "full_process_proof": None,
            "prospective": prospective,
            "generation_proof_mode": "CARRY_FORWARD_AUTHORITY_LOCK",
            "adjudication_authority_mode": ("PARALLEL_LOCKED_PROSPECTIVE_ADJUDICATED" if already_adjudicated else "PARALLEL_LOCKED_PROSPECTIVE"),
            "authority_freeze_sha256": freeze_sha,
            "scientific_adjudication_authority": True,
            "current_engineering_generation_authority": False,
            "adjudication_already_executed": already_adjudicated,
            "adjudication_evidence": adjudication_evidence,
        }

    raise ValueError("3054 preflight requires a FROZEN active epoch or a preserved locked prospective authority")

def _validate_probability_ledger(path: Path, expected_freeze_sha256: str) -> dict[str, Any]:
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
    if entry.get("main_freeze_file_sha256") != expected_freeze_sha256:
        raise ValueError("probability ledger is not bound to the active epoch freeze")
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


def _validate_full_process_proof(path: Path, current: dict[str, Any]) -> dict[str, Any]:
    proof = read_json(path)
    if proof.get("schema") != "SMART_FULL_PROCESS_PROOF_2" or proof.get("status") != "PASS":
        raise ValueError("current full-process proof missing or invalid")
    observed = proof.get("sha256")
    canonical = dict(proof)
    canonical.pop("sha256", None)
    if observed != sha256_json(canonical):
        raise ValueError("full-process proof self-hash invalid")
    if proof.get("freeze_sha256") != current["freeze_sha256"]:
        raise ValueError("full-process proof is not bound to current freeze")
    if int(proof.get("target_contest", -1)) != TARGET or int(proof.get("cutoff_contest", -1)) != CUTOFF:
        raise ValueError("full-process proof target/cutoff mismatch")
    if proof.get("result_used") is not False or not all(proof.get("trace_checks", {}).values()):
        raise ValueError("full-process proof is not a complete pre-result causal proof")
    return proof


def _sandbox_adjudication(root: Path, ledger_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="smart3054-preflight-") as raw_tmp:
        temp_root = Path(raw_tmp)
        temp_ledger = temp_root / "SMART_SIGNAL_LEDGER.sandbox.json"
        temp_result = temp_root / "synthetic_result_3054.xlsx"
        shutil.copy2(ledger_path, temp_ledger)
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
        target_events = [event for event in sandbox_ledger.get("events", []) if int(event.get("target_contest", -1)) == TARGET]
        adjudications = [event for event in target_events if event.get("event_type") == "ADJUDICATION"]
        if len(adjudications) != 1:
            raise RuntimeError("sandbox does not contain exactly one adjudication")
        derived_types = {event.get("event_type") for event in target_events if event.get("event_type") in EXPECTED_DERIVED_TYPES}
        missing_derived = sorted(EXPECTED_DERIVED_TYPES - derived_types)
        if missing_derived:
            raise RuntimeError(f"sandbox adjudication missing derived events: {missing_derived}")
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
    root = Path(root).resolve()
    paths = _current_paths(root)
    current = paths["current"]
    expected_freeze_sha256 = paths["authority_freeze_sha256"]
    freeze_path = paths["freeze"]
    ledger_path = paths["ledger"]
    probability_path = paths["probability"]
    full_process_path = paths["full_process_proof"]
    active_path = root / "SMART_ACTIVE_EPOCH.json"
    canonical_result_path = root / "Mega-Sena.xlsx"

    protected = {
        "active_epoch": active_path,
        "signal_ledger": ledger_path,
        "current_freeze": freeze_path,
        "probability_ledger": probability_path,
        "canonical_result_store": canonical_result_path,
    }
    if full_process_path is not None:
        protected["full_process_proof"] = full_process_path
    missing = [name for name, path in protected.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"preflight protected artifacts missing: {missing}")
    canonical_hashes_before = {name: sha256_file(path) for name, path in protected.items()}
    if canonical_hashes_before["current_freeze"] != expected_freeze_sha256:
        raise ValueError("active epoch freeze file hash differs from current authority")

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
    if sequence_before.get("active_freeze_sha256") != expected_freeze_sha256:
        raise ValueError("signal ledger active freeze differs from current epoch authority")
    if int(sequence_before.get("derived_event_count", -1)) != 0:
        raise ValueError("post-result derived events already exist before 3054 adjudication")

    probability = _validate_probability_ledger(probability_path, expected_freeze_sha256)
    if paths["generation_proof_mode"] == "CURRENT_ENGINEERING_FULL_PROCESS":
        full_process = _validate_full_process_proof(full_process_path, current)
        generation_authority = {
            "mode": paths["generation_proof_mode"],
            "valid": True,
            "proof_file": str(full_process_path.relative_to(root)).replace("\\", "/"),
            "proof_sha256": sha256_file(full_process_path),
            "current_engineering_generated_locked_freeze": True,
        }
    else:
        full_process = None
        generation_authority = {
            "mode": paths["generation_proof_mode"],
            "valid": (
                paths["scientific_adjudication_authority"] is True
                and paths["current_engineering_generation_authority"] is False
                and paths["prospective"].get("prediction_content_mutated") is False
                and paths["adjudication_authority_mode"] in {"ACTIVE_EPOCH_FROZEN", "PARALLEL_LOCKED_PROSPECTIVE"}
            ),
            "proof_file": str(paths["freeze"].relative_to(root)).replace("\\", "/"),
            "proof_sha256": expected_freeze_sha256,
            "current_engineering_generated_locked_freeze": False,
        }
    if generation_authority["valid"] is not True:
        raise ValueError("current freeze generation/adjudication authority is invalid")

    result_store = _canonical_result_store_status(canonical_result_path)
    sandbox = _sandbox_adjudication(root, ledger_path)

    canonical_hashes_after = {name: sha256_file(path) for name, path in protected.items()}
    canonical_unchanged = canonical_hashes_before == canonical_hashes_after
    if not canonical_unchanged:
        raise RuntimeError("sandbox preflight mutated canonical prospective artifacts")

    checks = {
        "prospective_adjudication_authority_resolved": paths["scientific_adjudication_authority"] is True,
        "active_freeze_exact": sequence_before["active_freeze_sha256"] == expected_freeze_sha256,
        "pre_result_sequence_valid": bool(sequence_before["valid"]),
        "not_yet_adjudicated": sequence_before["adjudicated"] is False,
        "no_post_result_events_before_result": int(sequence_before["derived_event_count"]) == 0,
        "probability_ledger_complete": probability["all_candidates_have_60_probabilities"],
        "probability_mass_valid": probability["all_probability_sums_equal_six"],
        "probability_ledger_bound_to_active_freeze": probability["main_freeze_file_sha256"] == expected_freeze_sha256,
        "generation_authority_valid": generation_authority["valid"] is True,
        "no_retroactive_generation_claim": generation_authority["current_engineering_generated_locked_freeze"] is paths["current_engineering_generation_authority"],
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
        "active_epoch_id": current["epoch_id"],
        "active_freeze_sha256": expected_freeze_sha256,
        "adjudication_authority_mode": paths["adjudication_authority_mode"],
        "target_schedule": paths["prospective"].get("schedule_authority"),
        "sequence_before_result": sequence_before,
        "probability_ledger": probability,
        "generation_authority": generation_authority,
        "full_process_proof_sha256": generation_authority.get("proof_sha256") if full_process is not None else None,
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
        "active_freeze_sha256": result["active_freeze_sha256"],
    }, ensure_ascii=False))
