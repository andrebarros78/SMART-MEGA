from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import adjudicate_signal_challenger as adjudicator
import smart_3054_adjudication_preflight as preflight
import smart_official_result_ingest as official_ingest
import smart_sequential_prospective_proof as sequential
from smart_current_epoch_contract import resolve as resolve_current_epoch
from smart_learning_epoch_reset import verify_active_epoch, resolve_locked_prospective_registration
from smart_signal_agent import SmartSignalAgent
from smart_v2_engine import load_draws

SCHEMA = "SMART_3054_FULL_CYCLE_SANDBOX_V2"
TARGET = 3054
CUTOFF = 3053


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
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
        raise ValueError(f"active epoch path escapes project root: {value}") from exc
    return path


def _current_paths(root: Path) -> dict[str, Any]:
    current = resolve_current_epoch(root)
    if current["status"] != "FROZEN" or current["target_contest"] != TARGET or current["cutoff_contest"] != CUTOFF:
        raise ValueError("3054 full-cycle sandbox requires the current FROZEN 3054 epoch")
    active = verify_active_epoch(root / "SMART_ACTIVE_EPOCH.json")
    state_paths = active.get("state_paths", {})
    prospective = active.get("prospective_registration")
    if not isinstance(prospective, dict) and current.get("authority_mode") == "CARRY_FORWARD_UNRESOLVED_PROSPECTIVE":
        prospective = resolve_locked_prospective_registration(root, TARGET, CUTOFF, str(current["freeze_sha256"]))
    if not isinstance(prospective, dict):
        raise ValueError("active epoch prospective registration missing")
    required = {
        "ledger": state_paths.get("ledger"),
        "state": state_paths.get("state"),
        "probability": prospective.get("probability_ledger_file"),
    }
    if any(not isinstance(value, str) or not value for value in required.values()):
        raise ValueError("active epoch sandbox paths incomplete")
    full_process = None
    if current.get("current_engineering_generation_authority") is True:
        full_process = _resolve(root, str(Path(required["ledger"]).parent / "FULL_PROCESS_PROOF.json"))
    return {
        "current": current,
        "active": active,
        "ledger": _resolve(root, required["ledger"]),
        "state": _resolve(root, required["state"]),
        "probability": _resolve(root, required["probability"]),
        "freeze": _resolve(root, str(current["freeze_file"])),
        "data": _resolve(root, str(current["data_file"])),
        "full_process_proof": full_process,
        "schedule": prospective.get("schedule_authority"),
        "prospective": prospective,
    }


def _hashes(paths: dict[str, Path]) -> dict[str, str]:
    return {name: sha256_file(path) for name, path in paths.items()}


def _agent_from_prestate(prestate: dict[str, Any]) -> SmartSignalAgent:
    return SmartSignalAgent(
        start=int(prestate["start_index"]),
        eta=float(prestate["eta"]),
        redundancy_threshold=float(prestate["redundancy_consensus_threshold"]),
        meta_strength=float(prestate["meta_strength"]),
        calibration_strength=float(prestate["calibration_strength"]),
    )


def build_sandbox(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    current_guard = resolve_current_epoch(root)
    if current_guard.get("status") != "FROZEN" or int(current_guard.get("target_contest", -1)) != TARGET or int(current_guard.get("cutoff_contest", -1)) != CUTOFF:
        raise ValueError("3054 full-cycle sandbox requires the current FROZEN 3054/3053 active epoch")
    readiness = preflight.build_preflight(root)
    if readiness["readiness_status"] != "PASS":
        raise RuntimeError("3054 adjudication preflight is not PASS")

    paths = _current_paths(root)
    current = paths["current"]
    expected_freeze_sha256 = str(current["freeze_sha256"])
    schedule = paths["schedule"]
    if not isinstance(schedule, dict) or schedule.get("result_used") is not False:
        raise ValueError("active epoch schedule authority missing or non-causal")
    target_date = str(schedule.get("target_date", ""))
    if not target_date:
        raise ValueError("active epoch target date missing")

    protected = {
        "active_epoch": root / "SMART_ACTIVE_EPOCH.json",
        "epoch_ledger": paths["ledger"],
        "epoch_prestate": paths["state"],
        "epoch_probability_ledger": paths["probability"],
        "current_freeze": paths["freeze"],
        "immutable_epoch_data": paths["data"],
        "canonical_result_store": root / "Mega-Sena.xlsx",
    }
    if paths["full_process_proof"] is not None:
        protected["full_process_proof"] = paths["full_process_proof"]
    if any(not path.is_file() for path in protected.values()):
        missing = [name for name, path in protected.items() if not path.is_file()]
        raise FileNotFoundError(f"sandbox protected artifacts missing: {missing}")
    hashes_before = _hashes(protected)
    if hashes_before["current_freeze"] != expected_freeze_sha256:
        raise ValueError("active epoch freeze hash mismatch")

    prestate = _read_json(paths["state"])
    if int(prestate.get("last_contest", -1)) != CUTOFF:
        raise ValueError("current epoch prestate must end at cutoff 3053")
    if prestate.get("data_sha256") != sha256_file(paths["data"]):
        raise ValueError("current epoch prestate data hash mismatch")

    with tempfile.TemporaryDirectory(prefix="smart3054-full-cycle-") as raw_tmp:
        tmp = Path(raw_tmp)
        ledger = tmp / "SMART_SIGNAL_LEDGER.sandbox.json"
        through = tmp / "Mega-Sena_through_3054.synthetic.xlsx"
        learned = tmp / "SMART_SIGNAL_STATE_3054_LEARNED.synthetic.json"
        shutil.copy2(paths["ledger"], ledger)

        synthetic_payload = {
            "numero": TARGET,
            "dataApuracao": target_date,
            "listaDezenas": ["01", "02", "03", "04", "05", "06"],
            "acumulado": False,
        }
        official = official_ingest.validate_official_payload(synthetic_payload, TARGET)
        frame = official_ingest.build_extended_frame(paths["data"], TARGET, official)
        frame.to_excel(through, index=False)
        draws, contests = load_draws(through)
        if int(contests[-1]) != TARGET:
            raise RuntimeError("sandbox result dataset does not end at 3054")

        cwd_before = Path.cwd()
        try:
            os.chdir(root)
            adjudication = adjudicator.adjudicate(through, TARGET, ledger)
            agent = _agent_from_prestate(prestate)
            replay = agent.replay_history(draws, contests)
            learned_state = agent.state_document(data_sha256=sha256_file(through))
            learned_state.update({
                "sequential_learning_target": TARGET,
                "learning_after_adjudication": True,
                "sandbox_only": True,
                "synthetic_result_has_predictive_authority": False,
                "source_prestate_sha256": sha256_file(paths["state"]),
                "source_epoch_id": current["epoch_id"],
            })
            learned.write_text(json.dumps(learned_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            learning = sequential.append_learning_update(ledger, TARGET, learned, through)
            proof = sequential.append_sequence_proof(ledger, TARGET)
            final_ledger = _read_json(ledger)
            validation = sequential.validate_target_sequence(
                final_ledger,
                TARGET,
                require_learning=True,
                require_proof=True,
                verify_files=True,
                root=root,
            )

            duplicate_learning_rejected = False
            duplicate_learning_error = None
            try:
                sequential.append_learning_update(ledger, TARGET, learned, through)
            except ValueError as exc:
                duplicate_learning_rejected = True
                duplicate_learning_error = str(exc)

            duplicate_proof_rejected = False
            duplicate_proof_error = None
            try:
                sequential.append_sequence_proof(ledger, TARGET)
            except ValueError as exc:
                duplicate_proof_rejected = True
                duplicate_proof_error = str(exc)
        finally:
            os.chdir(cwd_before)

        if not validation.get("valid"):
            raise RuntimeError("full sandbox sequence validation failed")
        if not duplicate_learning_rejected or not duplicate_proof_rejected:
            raise RuntimeError("full sandbox duplicate guards failed")
        if int(learned_state.get("last_contest", -1)) != TARGET:
            raise RuntimeError("learned state does not end at 3054")

        target_types = [
            event.get("event_type")
            for event in final_ledger.get("events", [])
            if int(event.get("target_contest", -1)) == TARGET
        ]
        expected_tail = [sequential.LEARNING_EVENT, sequential.PROOF_EVENT]
        if target_types[-2:] != expected_tail:
            raise RuntimeError("full sandbox sequence does not end in learning then proof")

        hashes_after = _hashes(protected)
        if hashes_after != hashes_before:
            raise RuntimeError("full-cycle sandbox mutated current epoch or canonical protected artifacts")

        checks = {
            "preflight_pass": True,
            "active_epoch_frozen": current["status"] == "FROZEN",
            "current_freeze_hash_bound": hashes_before["current_freeze"] == expected_freeze_sha256,
            "official_schedule_date_used_for_synthetic_rehearsal": official["draw_date_text"] == target_date,
            "synthetic_official_payload_validated": True,
            "synthetic_dataset_ends_at_3054": True,
            "adjudication_completed": int(adjudication["target_contest"]) == TARGET,
            "learning_state_trained_through_3054": int(learned_state["last_contest"]) == TARGET,
            "learning_event_recorded": learning.get("status") == "LEARNING_RECORDED",
            "sequential_proof_recorded": proof.get("status") == "SEQUENCE_PROVEN",
            "full_sequence_valid": validation.get("valid") is True,
            "duplicate_learning_rejected": duplicate_learning_rejected,
            "duplicate_proof_rejected": duplicate_proof_rejected,
            "canonical_protected_artifacts_unchanged": hashes_after == hashes_before,
        }
        status = "PASS" if all(checks.values()) else "FAIL"
        return {
            "schema": SCHEMA,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "active_epoch_id": current["epoch_id"],
            "target_contest": TARGET,
            "cutoff_contest": CUTOFF,
            "target_date": target_date,
            "status": status,
            "active_freeze_sha256": expected_freeze_sha256,
            "synthetic_result": official["numbers"],
            "synthetic_result_authority": "NONE_SANDBOX_ONLY",
            "adjudication": {
                "champion_hits": int(adjudication["champion_hits"]),
                "challenger_hits": int(adjudication["challenger_hits"]),
                "e_value_after": float(adjudication["e_value_after"]),
            },
            "learning": {
                "agent_start_index": int(prestate["start_index"]),
                "last_contest": int(learned_state["last_contest"]),
                "data_sha256": learned_state["data_sha256"],
                "replay_rows": len(replay["rows"]),
                "learning_event_status": learning["status"],
            },
            "sequence": validation,
            "target_event_types": target_types,
            "duplicate_guards": {
                "learning_rejected": duplicate_learning_rejected,
                "learning_error": duplicate_learning_error,
                "proof_rejected": duplicate_proof_rejected,
                "proof_error": duplicate_proof_error,
            },
            "canonical_hashes_before": hashes_before,
            "canonical_hashes_after": hashes_after,
            "checks": checks,
            "official_result_ingested": False,
            "canonical_learning_executed": False,
            "terminal_6of6_proven": False,
        }


def write_sandbox(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    document = build_sandbox(root)
    (root / "SMART_3054_FULL_CYCLE_SANDBOX_PROOF.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return document


if __name__ == "__main__":
    import sys
    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    result = write_sandbox(project_root)
    print(json.dumps({
        "status": result["status"],
        "target": result["target_contest"],
        "target_date": result["target_date"],
        "learning_last_contest": result["learning"]["last_contest"],
        "sequence_valid": result["sequence"]["valid"],
        "duplicate_guards": result["duplicate_guards"],
        "canonical_unchanged": result["checks"]["canonical_protected_artifacts_unchanged"],
    }, ensure_ascii=False))
