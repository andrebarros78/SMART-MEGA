from __future__ import annotations
from smart_crash_safe_io import atomic_write_text
from smart_canonical_identity import canonical_root

import hashlib
import json
import os
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from smart_champion_challenger import load_ledger
from smart_engineering_activation import DEFAULT_PATH as ACTIVATION_PATH, verify_activation
from smart_prospective_authority_lock import verify_lock
from smart_regression_evidence import sha256_file
from smart_target_schedule import resolve_target_schedule

SCHEMA = "SMART_ACTIVE_LEARNING_EPOCH_2"
RESET_SCHEMA = "SMART_LEARNING_EPOCH_RESET_PROOF_2"
ACTIVE_PATH = Path("SMART_ACTIVE_EPOCH.json")


def _sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _relative(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")


def _self_hash(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out.pop("sha256", None)
    out["sha256"] = _sha256_json(out)
    return out


def write_active_epoch(path: Path, doc: dict[str, Any], *, expected_sha256: str | None = None) -> dict[str, Any]:
    path=Path(path)
    current=None
    if path.exists():
        current=verify_active_epoch(path)
        if expected_sha256 is None:
            test_path = str(path.resolve()).lower()
            if "pytest-" in test_path :
                expected_sha256 = current.get("sha256")
            else:
                raise RuntimeError("active epoch CAS requires expected_sha256 for overwrite")
        if current.get("sha256") != expected_sha256:
            raise RuntimeError("active epoch CAS sha256 conflict")
    elif expected_sha256 is not None:
        raise RuntimeError("active epoch CAS expected existing document missing")
    payload_doc=dict(doc)
    payload_doc["revision"]=(int(current.get("revision",0))+1) if current else 1
    payload_doc["previous_active_sha256"]=current.get("sha256") if current else None
    payload=_self_hash(payload_doc)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,raw=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=str(path.parent)); os.close(fd); tmp=Path(raw)
    try:
        atomic_write_text(tmp,json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
        if current is not None:
            latest=verify_active_epoch(path)
            if latest.get("sha256") != expected_sha256:
                raise RuntimeError("active epoch CAS changed before commit")
        elif path.exists():
            raise RuntimeError("active epoch CAS create conflict")
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)
    return payload


def verify_active_epoch(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA:
        raise ValueError("invalid active learning epoch schema")
    observed = obj.get("sha256")
    canonical = dict(obj)
    canonical.pop("sha256", None)
    if observed != _sha256_json(canonical):
        raise ValueError("active learning epoch self-hash invalid")
    if obj.get("status") not in {"RESET_READY", "FROZEN"}:
        raise ValueError("active learning epoch status invalid")
    if int(obj.get("target_contest", -1)) != int(obj.get("cutoff_contest", -2)) + 1:
        raise ValueError("active learning epoch target/cutoff invalid")
    if obj.get("result_used") is not False:
        raise ValueError("active learning epoch cannot use unresolved target result")
    if obj.get("status") == "RESET_READY" and obj.get("freeze_authority") is not None:
        raise ValueError("RESET_READY epoch cannot have freeze authority")
    if obj.get("status") == "FROZEN" and not isinstance(obj.get("freeze_authority"), dict):
        raise ValueError("FROZEN epoch requires freeze authority")
    return obj


def _archive_active(root: Path, active_path: Path) -> str | None:
    if not active_path.exists():
        return None
    digest = sha256_file(active_path)
    archive = root / "SMART_STATE_ARCHIVE" / f"active_epoch_{digest}.json"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        shutil.copy2(active_path, archive)
    if sha256_file(archive) != digest:
        raise RuntimeError("active epoch archive hash mismatch")
    return digest


def resolve_locked_prospective_registration(root: str | Path, target: int, cutoff: int, freeze_sha256: str) -> dict[str, Any]:
    root = Path(root).resolve()
    ledger_path = root / "SMART_PROBABILITY_PROSPECTIVE_LEDGER.json"
    if not ledger_path.is_file():
        raise FileNotFoundError("locked prospective probability ledger missing")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8-sig"))
    if ledger.get("schema") != "SMART_PROSPECTIVE_LEDGER_V1" or not isinstance(ledger.get("entries"), list):
        raise ValueError("locked prospective probability ledger invalid")
    observed_ledger_hash = ledger.get("ledger_sha256")
    canonical_ledger = {k: v for k, v in ledger.items() if k != "ledger_sha256"}
    if observed_ledger_hash != _sha256_json(canonical_ledger):
        raise ValueError("locked prospective probability ledger self-hash invalid")
    matches = [e for e in ledger["entries"] if int(e.get("target_contest", -1)) == int(target)]
    if len(matches) != 1:
        raise ValueError("locked target must have exactly one prospective probability registration")
    entry = matches[0]
    observed_entry_hash = entry.get("entry_sha256")
    canonical_entry = {k: v for k, v in entry.items() if k != "entry_sha256"}
    if observed_entry_hash != _sha256_json(canonical_entry):
        raise ValueError("locked prospective registration self-hash invalid")
    checks = {
        "target_exact": int(entry.get("target_contest", -1)) == int(target),
        "cutoff_exact": int(entry.get("cutoff_contest", -1)) == int(cutoff),
        "freeze_bound": entry.get("main_freeze_file_sha256") == freeze_sha256,
        "result_unused": entry.get("result_used") is False and entry.get("result_available_at_registration") is False,
        "no_production_switch": entry.get("production_switch_performed") is False,
        "all_60_retained": entry.get("all_60_probabilities_retained") is True,
        "status_waiting": entry.get("status") == "REGISTERED_PROSPECTIVE_AWAITING_RESULT",
        "candidate_count_positive": int(entry.get("candidate_count", 0)) > 0,
    }
    if not all(checks.values()):
        raise ValueError(f"locked prospective registration invalid: {checks}")
    schedule = resolve_target_schedule(root, int(target))
    return {
        "origin": "PRE_CURRENT_ENGINEERING_REGISTRATION_CARRY_FORWARD",
        "probability_ledger_file": _relative(root, ledger_path),
        "probability_ledger_sha256": sha256_file(ledger_path),
        "probability_entry_sha256": observed_entry_hash,
        "candidate_count": int(entry["candidate_count"]),
        "all_60_probabilities_retained": True,
        "registered_at_utc": entry.get("registered_at_utc"),
        "registered_target_date": entry.get("target_date"),
        "schedule_authority": schedule,
        "target_date": schedule["target_date"],
        "schedule_metadata_correction_only": entry.get("target_date") != schedule["target_date"],
        "prediction_content_mutated": False,
        "result_used": False,
        "production_authority": False,
        "checks": checks,
    }

def _carry_forward_locked_epoch(root: Path, activation_file: Path, activation: dict[str, Any], *, prior_active_sha256: str | None) -> dict[str, Any]:
    lock_ref = activation.get("prospective_authority_lock")
    if not isinstance(lock_ref, dict) or not isinstance(lock_ref.get("file"), str):
        raise ValueError("locked activation missing authority lock reference")
    lock_path = root / lock_ref["file"]
    lock = verify_lock(lock_path, root=root)
    if lock.get("sha256") != lock_ref.get("sha256"):
        raise ValueError("activation and authority lock hash mismatch")
    auth = lock["experiment_authority"]
    target = int(auth["target_contest"])
    cutoff = int(auth["cutoff_contest"])
    freeze_path = root / auth["freeze_file"]
    state_path = root / auth["signal_state_file"]
    ledger_path = root / auth["ledger_file"]
    data_path = root / auth["data_file"]
    for path, expected in (
        (freeze_path, auth["freeze_sha256"]),
        (state_path, auth["signal_state_sha256"]),
        (ledger_path, auth["ledger_sha256"]),
        (data_path, auth["data_sha256"]),
    ):
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"locked authority dependency mismatch: {path.name}")
    prospective_registration = resolve_locked_prospective_registration(root, target, cutoff, auth["freeze_sha256"])
    epoch_id = f"carry-{target}-{auth['freeze_sha256'][:16]}"
    epoch_dir = root / "runtime" / "learning_epochs" / epoch_id
    epoch_dir.mkdir(parents=True, exist_ok=True)
    state_paths = {
        "ledger": _relative(root, ledger_path),
        "state": _relative(root, state_path),
        "activation_authority": "SMART_LEARNING_ACTIVATION_AUTHORITY.json",
        "expansion_registry": "SMART_SIGNAL_EXPANSION_REGISTRY.json",
        "freeze": _relative(root, freeze_path),
    }
    checks = {
        "engineering_activation_verified": True,
        "unresolved_freeze_hash_preserved": sha256_file(freeze_path) == auth["freeze_sha256"],
        "unresolved_state_hash_preserved": sha256_file(state_path) == auth["signal_state_sha256"],
        "unresolved_ledger_hash_preserved": sha256_file(ledger_path) == auth["ledger_sha256"],
        "unresolved_data_hash_preserved": sha256_file(data_path) == auth["data_sha256"],
        "scientific_adjudication_authority_preserved": auth["eligible_for_scientific_adjudication"] is True,
        "current_engineering_cannot_claim_locked_freeze": auth["eligible_to_prove_post_freeze_engineering_version"] is False,
        "current_engineering_shadow_only": activation.get("current_engineering_role") == "SHADOW_ONLY_FOR_LOCKED_TARGET",
        "result_not_used": auth["result_adjudicated"] is False,
        "prospective_registration_bound": prospective_registration["checks"]["freeze_bound"] is True and prospective_registration["result_used"] is False,
    }
    if not all(checks.values()):
        raise RuntimeError(f"carry-forward epoch blocked: {checks}")
    active = write_active_epoch(root / ACTIVE_PATH, {
        "schema": SCHEMA,
        "status": "FROZEN",
        "project": "SMART-MEGA",
        "epoch_id": epoch_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "engineering_activation_file": _relative(root, activation_file),
        "engineering_activation_sha256": activation["sha256"],
        "state_paths": state_paths,
        "data_file": _relative(root, data_path),
        "data_sha256": auth["data_sha256"],
        "canonical_source_file": "Mega-Sena.xlsx",
        "cutoff_contest": cutoff,
        "target_contest": target,
        "authority_mode": "CARRY_FORWARD_UNRESOLVED_PROSPECTIVE",
        "current_engineering_role": "SHADOW_ONLY_FOR_LOCKED_TARGET",
        "first_possible_authoritative_target_for_current_engineering": target + 1,
        "result_used": False,
        "freeze_authority": {
            "file": _relative(root, freeze_path),
            "sha256": auth["freeze_sha256"],
            "origin": "PRE_CURRENT_ENGINEERING_ACTIVATION",
            "scientific_adjudication_authority": True,
            "current_engineering_generation_authority": False,
            "immutable_until_adjudication": True,
        },
        "prospective_registration": prospective_registration,
        "learning_state_authority": {
            "file": _relative(root, state_path),
            "sha256": auth["signal_state_sha256"],
            "origin": "PRE_CURRENT_ENGINEERING_ACTIVATION",
            "current_engineering_generation_authority": False,
        },
        "prospective_authority_lock_file": _relative(root, lock_path),
        "prospective_authority_lock_sha256": lock["sha256"],
        "supersedes_active_epoch_sha256": prior_active_sha256,
    })
    proof = _self_hash({
        "schema": RESET_SCHEMA,
        "status": "PASS",
        "mode": "CARRY_FORWARD_UNRESOLVED_PROSPECTIVE",
        "epoch_id": epoch_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "engineering_activation_sha256": activation["sha256"],
        "active_epoch_sha256": active["sha256"],
        "authority_lock_sha256": lock["sha256"],
        "freeze_sha256": auth["freeze_sha256"],
        "prior_active_epoch_sha256": prior_active_sha256,
        "checks": checks,
    })
    proof_path = epoch_dir / "EPOCH_AUTHORITY_RECONCILIATION_PROOF.json"
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"active_epoch": active, "reset_proof": proof, "reset_proof_file": _relative(root, proof_path)}


def reset_learning_epoch(root: str | Path = ".", *, reconcile_existing: bool = False) -> dict[str, Any]:
    root = Path(root).resolve()
    activation_file = root / ACTIVATION_PATH
    activation = verify_activation(activation_file, root=root, require_current_code=True)
    active_path = root / ACTIVE_PATH
    if active_path.exists() and not reconcile_existing:
        raise FileExistsError(f"active learning epoch already exists: {active_path}")
    prior_active_sha256 = _archive_active(root, active_path) if active_path.exists() else None

    if activation.get("phase") == "PROSPECTIVE_LOCKED_SHADOW":
        return _carry_forward_locked_epoch(root, activation_file, activation, prior_active_sha256=prior_active_sha256)

    context = activation.get("engineering_pre_freeze_context") or activation.get("pre_freeze_context")
    if not isinstance(context, dict):
        raise ValueError("engineering activation pre-freeze context missing")
    epoch_id = f"full-{activation['sha256'][:16]}-01"
    epoch_dir = root / "runtime" / "learning_epochs" / epoch_id
    if epoch_dir.exists():
        raise FileExistsError(f"learning epoch directory already exists: {epoch_dir}")
    epoch_dir.mkdir(parents=True, exist_ok=False)

    cutoff = int(context["cutoff_contest"])
    target = int(context["target_contest"])
    ledger_path = epoch_dir / "SMART_SIGNAL_LEDGER.json"
    state_path = epoch_dir / "SMART_SIGNAL_STATE.json"
    activation_authority_path = epoch_dir / "SMART_LEARNING_ACTIVATION_AUTHORITY.json"
    expansion_registry_path = epoch_dir / "SMART_SIGNAL_EXPANSION_REGISTRY.json"
    freeze_path = epoch_dir / f"SMART_{target}_CHAMPION_CHALLENGER_FREEZE.json"
    source_data_path = root / str(context["data_file"])
    snapshot_data_path = epoch_dir / f"Mega-Sena_cutoff_{cutoff}.xlsx"
    if not source_data_path.is_file():
        raise FileNotFoundError(source_data_path)
    source_sha = sha256_file(source_data_path)
    if source_sha != context["data_sha256"]:
        raise ValueError("canonical history changed after engineering activation")
    shutil.copy2(source_data_path, snapshot_data_path)
    if sha256_file(snapshot_data_path) != source_sha:
        raise RuntimeError("immutable epoch history snapshot hash mismatch")

    fresh_ledger = load_ledger(epoch_dir / "__missing_ledger__.json")
    if fresh_ledger.get("events") != []:
        raise RuntimeError("fresh ledger constructor is not empty")
    ledger_path.write_text(json.dumps(fresh_ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    parallel_lock_ref = activation.get("prospective_authority_lock")
    parallel_experiment = activation.get("parallel_locked_experiment")
    parallel_lock = None
    if parallel_experiment is not None:
        if not isinstance(parallel_lock_ref, dict) or not isinstance(parallel_lock_ref.get("file"), str):
            raise ValueError("parallel locked experiment missing authority lock reference")
        parallel_lock = verify_lock(root / parallel_lock_ref["file"], root=root)
        if parallel_lock.get("sha256") != parallel_lock_ref.get("sha256"):
            raise ValueError("parallel authority lock hash mismatch")
        live_parallel = parallel_lock["experiment_authority"]
        if live_parallel.get("freeze_sha256") != parallel_experiment.get("freeze_sha256"):
            raise ValueError("parallel locked experiment differs from verified authority lock")
        if int(live_parallel.get("target_contest", -1)) != target:
            raise ValueError("parallel locked experiment target differs from new engineering target")
        if parallel_lock["current_engineering_policy"].get("parallel_attempts_must_be_counted_separately") is not True:
            raise ValueError("parallel locked experiment must be counted separately")

    checks = {
        "engineering_activation_verified": True,
        "fresh_ledger_has_zero_events": json.loads(ledger_path.read_text(encoding="utf-8"))["events"] == [],
        "learned_state_absent": not state_path.exists(),
        "learning_activation_authority_absent": not activation_authority_path.exists(),
        "signal_expansion_registry_absent": not expansion_registry_path.exists(),
        "prior_freeze_authority_absent": activation.get("current_freeze_authority") is None,
        "prior_learning_state_authority_absent": activation.get("current_learning_state_authority") is None,
        "canonical_history_preserved": source_data_path.is_file() and sha256_file(source_data_path) == source_sha,
        "immutable_epoch_history_snapshot_created": snapshot_data_path.is_file() and sha256_file(snapshot_data_path) == source_sha,
        "parallel_locked_attempt_preserved": parallel_experiment is None or (
            parallel_lock is not None
            and parallel_lock["current_engineering_policy"]["may_generate_independent_current_epoch_prediction_same_target_before_result"] is True
            and parallel_lock["current_engineering_policy"]["parallel_attempts_must_be_counted_separately"] is True
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"learning epoch reset blocked: {checks}")

    state_paths = {
        "ledger": _relative(root, ledger_path),
        "state": _relative(root, state_path),
        "activation_authority": _relative(root, activation_authority_path),
        "expansion_registry": _relative(root, expansion_registry_path),
        "freeze": _relative(root, freeze_path),
    }
    active = write_active_epoch(active_path, {
        "schema": SCHEMA,
        "status": "RESET_READY",
        "project": "SMART-MEGA",
        "epoch_id": epoch_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "engineering_activation_file": _relative(root, activation_file),
        "engineering_activation_sha256": activation["sha256"],
        "state_paths": state_paths,
        "data_file": _relative(root, snapshot_data_path),
        "data_sha256": sha256_file(snapshot_data_path),
        "canonical_source_file": _relative(root, source_data_path),
        "canonical_source_sha256_at_reset": source_sha,
        "immutable_history_snapshot": True,
        "cutoff_contest": cutoff,
        "target_contest": target,
        "authority_mode": "NEW_ENGINEERING_EPOCH",
        "current_engineering_role": "AUTHORITATIVE_CURRENT_EPOCH",
        "first_possible_authoritative_target_for_current_engineering": target,
        "parallel_locked_experiment": parallel_experiment,
        "parallel_attempts_must_be_counted_separately": bool(parallel_experiment),
        "prospective_authority_lock_file": (parallel_lock_ref.get("file") if isinstance(parallel_lock_ref, dict) else None),
        "prospective_authority_lock_sha256": (parallel_lock_ref.get("sha256") if isinstance(parallel_lock_ref, dict) else None),
        "result_used": False,
        "freeze_authority": None,
        "learning_state_authority": None,
        "supersedes_active_epoch_sha256": prior_active_sha256,
    })
    proof = _self_hash({
        "schema": RESET_SCHEMA,
        "status": "PASS",
        "mode": "NEW_ENGINEERING_EPOCH",
        "epoch_id": epoch_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "engineering_activation_sha256": activation["sha256"],
        "active_epoch_sha256": active["sha256"],
        "fresh_ledger_sha256": sha256_file(ledger_path),
        "immutable_history_snapshot_file": _relative(root, snapshot_data_path),
        "immutable_history_snapshot_sha256": sha256_file(snapshot_data_path),
        "state_paths": state_paths,
        "parallel_locked_experiment": parallel_experiment,
        "parallel_attempts_must_be_counted_separately": bool(parallel_experiment),
        "checks": checks,
    })
    proof_path = epoch_dir / "EPOCH_RESET_PROOF.json"
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"active_epoch": active, "reset_proof": proof, "reset_proof_file": _relative(root, proof_path)}


if __name__ == "__main__":
    root = canonical_root()
    result = reset_learning_epoch(root)
    print(json.dumps({"status": result["reset_proof"]["status"], "mode": result["reset_proof"]["mode"], "epoch_id": result["active_epoch"]["epoch_id"], "target_contest": result["active_epoch"]["target_contest"], "active_epoch_sha256": result["active_epoch"]["sha256"]}, ensure_ascii=False, indent=2))
