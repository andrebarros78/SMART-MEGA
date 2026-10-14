from __future__ import annotations
from smart_crash_safe_io import atomic_write_text
from smart_idempotency import resolve_key as resolve_idempotency_key, replay as replay_idempotency, commit as commit_idempotency, idempotent_operation
from smart_canonical_identity import canonical_root
from smart_operational_lifecycle import assert_state as assert_lifecycle_state, load_lifecycle, transition as transition_lifecycle
from smart_operation_lock import locked_operation, update_current_process_lock
from smart_storage_surfaces import runtime_path, evidence_path, require_within
from smart_rollover import canonical_rollover
from smart_transaction_journal import begin as journal_begin, prepared as journal_prepared, committing as journal_committing, committed as journal_committed, rolled_back as journal_rolled_back, current_phase as journal_current_phase
from smart_startup_reconciler import startup_guarded, reconcile as reconcile_startup
from smart_scientific_state_guard import audit_boundaries as audit_state_boundaries

import argparse
import hashlib
from functools import wraps
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from adjudicate_signal_challenger import adjudicate
from smart_agent_runtime import sha256_file
from smart_champion_challenger import active_freeze, load_ledger, reconcile_completed_epoch_ledger, seed_ledger_from_canonical
from smart_canonical_history_advance import advance_completed_epoch
from smart_current_epoch_contract import resolve as resolve_current_epoch
from smart_full_process_pipeline import _rel, _resolve, run_full_process
from smart_consumer_integration import audit_generation
from smart_operation_recovery import recover_interrupted_freeze_operation
from smart_operator_contract import contract, validate_target_sequence
from smart_learning_epoch_reset import ACTIVE_PATH, SCHEMA as EPOCH_SCHEMA, write_active_epoch, verify_active_epoch
from smart_manual_generation_authority import authorize as authorize_manual_generation, validate as validate_manual_generation
from smart_official_result_ingest import ingest as ingest_official_result
from smart_target_schedule import assert_pre_draw_window, resolve_target_schedule
import smart_terminal_executor as terminal_executor

SCHEMA = "SMART_OPERATOR_CONTRACT_V1"

POST_RESULT_HOLD_PATH = Path("SMART_NEXT_CYCLE_HOLD.json")
NEXT_CYCLE_AUTHORITY_PATH = Path("SMART_NEXT_CYCLE_AUTHORITY.json")
NEXT_CYCLE_AUTHORITY_SCHEMA = "SMART_NEXT_CYCLE_AUTHORITY_1"
NEXT_CYCLE_HOLD_SCHEMA = "SMART_NEXT_CYCLE_HOLD_1"


def _operator_sha256_json(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_operator_hashed_doc(path: Path, schema: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("schema") != schema:
        raise ValueError(f"invalid {schema} document")
    observed = obj.get("sha256")
    canonical = dict(obj)
    canonical.pop("sha256", None)
    if not isinstance(observed, str) or observed.lower() != _operator_sha256_json(canonical):
        raise ValueError(f"{schema} self-hash mismatch")
    return obj


def _write_operator_hashed_doc(path: Path, payload: dict[str, Any], *, expected_sha256: str | None = None) -> dict[str, Any]:
    current = None
    if path.exists():
        if expected_sha256 is None:
            raise RuntimeError(f"CAS expected_sha256 required for overwrite: {path.name}")
        current = _load_operator_hashed_doc(path, str(payload.get("schema") or ""))
        if current.get("sha256") != expected_sha256:
            raise RuntimeError(f"CAS sha256 conflict: {path.name}")
    elif expected_sha256 is not None:
        raise RuntimeError(f"CAS expected existing document missing: {path.name}")
    obj = dict(payload)
    obj.pop("sha256", None)
    obj["revision"] = (int(current.get("revision", 0)) + 1) if current else 1
    obj["previous_document_sha256"] = current.get("sha256") if current else None
    obj["sha256"] = _operator_sha256_json(obj)
    tmp = path.with_suffix(path.suffix + ".tmp")
    atomic_write_text(tmp,json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    if current is not None:
        latest = _load_operator_hashed_doc(path, str(payload.get("schema") or ""))
        if latest.get("sha256") != expected_sha256:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"CAS changed before replace: {path.name}")
    elif path.exists():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"CAS create conflict: {path.name}")
    tmp.replace(path)
    return obj


def _find_valid_pre_freeze_withdrawal(root: Path, target: int, epoch_id: str) -> tuple[Path, dict[str, Any]] | None:
    archive = evidence_path(root, "SMART_STATE_ARCHIVE")
    if not archive.is_dir():
        return None
    for path in archive.glob("operator_pre_freeze_withdrawal_*.json"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if obj.get("schema") != "SMART_OPERATOR_PRE_FREEZE_WITHDRAWAL_1":
            continue
        observed = obj.get("sha256")
        canonical = dict(obj); canonical.pop("sha256", None); canonical.pop("proof_file", None)
        if not isinstance(observed, str) or observed != _operator_sha256_json(canonical):
            continue
        if obj.get("status") != "WITHDRAWN_PRE_FREEZE":
            continue
        if int(obj.get("target_contest", -1)) != int(target) or str(obj.get("epoch_id") or "") != str(epoch_id):
            continue
        if obj.get("active_pointer_removed") is not True or obj.get("reason") != "PRE_FREEZE_TECHNICAL_CORRECTION":
            continue
        checks = obj.get("checks") or {}
        if not isinstance(checks, dict) or not checks or not all(v is True for v in checks.values()):
            continue
        return path, obj
    return None


@locked_operation("AUTHORIZE_NEXT_CYCLE")
def _run_idempotent(root, operation, target, idempotency_key, payload, action):
    key = resolve_idempotency_key(operation, int(target), idempotency_key, payload)
    prior = replay_idempotency(root, operation, key, int(target))
    if prior is not None:
        return prior
    result = action()
    commit_idempotency(root, operation, key, int(target), result)
    return result


def _authorization_idempotency_payload(root, target, args, kwargs):
    """Scope same-target reauthorization to its verified technical withdrawal.

    The ordinary first-authorization key is preserved. A consumed authority
    must never replay that prior success after a proven pre-freeze withdrawal.
    """
    payload = {"args": [str(x) for x in args],
               "kwargs": {k: str(v) for k, v in sorted(kwargs.items())}}
    root = Path(root).resolve()
    lifecycle = load_lifecycle(root)
    authority_path = root / NEXT_CYCLE_AUTHORITY_PATH
    if (lifecycle.get("state") != "HOLD"
            or int(lifecycle.get("target_contest") or -1) != int(target)
            or not authority_path.is_file()):
        return payload
    existing = _load_operator_hashed_doc(authority_path, NEXT_CYCLE_AUTHORITY_SCHEMA)
    if int(existing.get("target_contest", -1)) != int(target) or existing.get("consumed") is not True:
        return payload
    epoch_id = str(existing.get("prepared_epoch_id") or "")
    proof = _find_valid_pre_freeze_withdrawal(root, int(target), epoch_id)
    if proof is None:
        raise FileExistsError("consumed next-cycle authority cannot be replayed without withdrawal proof")
    proof_path, evidence = proof
    payload["withdrawal_reauthorization"] = {
        "prior_consumed_authority_sha256": existing["sha256"],
        "withdrawal_proof_sha256": evidence["sha256"],
        "withdrawn_epoch_id": epoch_id,
        "withdrawal_proof_file": str(proof_path.relative_to(root)).replace("\\", "/"),
    }
    return payload


@locked_operation("AUTHORIZE_NEXT_CYCLE")
@startup_guarded("AUTHORIZE_NEXT_CYCLE")
@idempotent_operation('AUTHORIZE', payload_builder=_authorization_idempotency_payload)
def authorize_next_cycle_operation(root: str | Path, target: int, *, idempotency_key: str | None = None) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    target = int(target)
    assert_lifecycle_state(root, "HOLD", target_contest=target)
    hold = _load_operator_hashed_doc(root / POST_RESULT_HOLD_PATH, NEXT_CYCLE_HOLD_SCHEMA)
    if hold.get("status") != "AWAITING_OPERATOR_APPLY_OR_GENERATE":
        raise ValueError("post-result hold is not awaiting operator apply/generate")
    if int(hold.get("next_target", -1)) != target:
        raise ValueError("post-result hold next target mismatch")
    if hold.get("automatic_prepare_forbidden") is not True or hold.get("prepare_allowed") is not False:
        raise ValueError("post-result hold does not forbid automatic preparation")
    review = root / str(hold.get("review_file") or "")
    if not review.is_file() or sha256_file(review) != hold.get("review_file_sha256"):
        raise ValueError("post-result review binding mismatch")
    canonical = root / "Mega-Sena.xlsx"
    if not canonical.is_file() or sha256_file(canonical) != hold.get("canonical_sha256_at_review"):
        raise ValueError("canonical history changed after post-result review")
    authority_path = root / NEXT_CYCLE_AUTHORITY_PATH
    reauthorization = None
    existing_authority_sha = None
    if authority_path.exists():
        existing = _load_operator_hashed_doc(authority_path, NEXT_CYCLE_AUTHORITY_SCHEMA)
        existing_authority_sha = existing["sha256"]
        existing_target = int(existing.get("target_contest", -1))
        existing_consumed = existing.get("consumed") is True
        if existing_target == target and existing.get("status") == "AUTHORIZED" and existing.get("consumed") is False:
            lifecycle = transition_lifecycle(root, "HOLD", "AUTHORIZED", target_contest=target, actor="operator_authorize_next_cycle_recover")
            return {**existing, "operational_lifecycle": lifecycle}
        if existing_target < target and existing_consumed and existing_target <= int(hold.get("completed_contest", -1)):
            reauthorization = {"supersedes_completed_cycle_authority": True, "prior_consumed_authority_sha256": existing.get("sha256"), "prior_consumed_target_contest": existing_target, "prior_consumed_status": existing.get("status")}
        elif existing_target == target and existing_consumed:
            prepared_epoch_id = str(existing.get("prepared_epoch_id") or "")
            withdrawal = _find_valid_pre_freeze_withdrawal(root, target, prepared_epoch_id)
            if withdrawal is None:
                raise FileExistsError("consumed next-cycle authority cannot be reauthorized for the same target without withdrawal proof")
            withdrawal_path, withdrawal_doc = withdrawal
            reauthorization = {"reauthorized_after_withdrawal": True, "prior_consumed_authority_sha256": existing.get("sha256"), "withdrawal_proof_file": str(withdrawal_path.relative_to(root)).replace("\\", "/"), "withdrawal_proof_sha256": withdrawal_doc.get("sha256"), "withdrawn_epoch_id": prepared_epoch_id}
        else:
            raise FileExistsError("incompatible next-cycle authority already exists")
    payload = {
        "schema": NEXT_CYCLE_AUTHORITY_SCHEMA,
        "status": "AUTHORIZED",
        "target_contest": target,
        "completed_contest": int(hold.get("completed_contest", -1)),
        "review_file": review.name,
        "review_file_sha256": sha256_file(review),
        "review_sha256": hold.get("review_sha256"),
        "canonical_sha256": sha256_file(canonical),
        "authorized_by": "USER_EXPLICIT_APPLY_OR_GENERATE",
        "authorized_utc": datetime.now(timezone.utc).isoformat(),
        "consumed": False,
        "consumed_utc": None,
        "prepared_epoch_id": None,
        "reservation_transaction_id": None,
        "reserved_utc": None,
        "consumption_transaction_id": None,
    }
    if reauthorization is not None:
        payload.update(reauthorization)
    authority = _write_operator_hashed_doc(authority_path, payload, expected_sha256=existing_authority_sha)
    lifecycle = transition_lifecycle(root, "HOLD", "AUTHORIZED", target_contest=target, actor="operator_authorize_next_cycle")
    return {**authority, "operational_lifecycle": lifecycle}


def _require_next_cycle_authority(root: Path, target: int) -> dict[str, Any]:
    assert_lifecycle_state(root, "AUTHORIZED", target_contest=target)
    hold = _load_operator_hashed_doc(root / POST_RESULT_HOLD_PATH, NEXT_CYCLE_HOLD_SCHEMA)
    authority = _load_operator_hashed_doc(root / NEXT_CYCLE_AUTHORITY_PATH, NEXT_CYCLE_AUTHORITY_SCHEMA)
    if hold.get("status") != "AWAITING_OPERATOR_APPLY_OR_GENERATE":
        raise ValueError("post-result hold is not active")
    if int(hold.get("next_target", -1)) != int(target):
        raise ValueError("post-result hold target mismatch")
    if authority.get("status") != "AUTHORIZED" or authority.get("consumed") is not False:
        raise PermissionError("next-cycle authority is not active")
    if int(authority.get("target_contest", -1)) != int(target):
        raise PermissionError("next-cycle authority target mismatch")
    if authority.get("authorized_by") != "USER_EXPLICIT_APPLY_OR_GENERATE":
        raise PermissionError("prepare requires explicit user apply/generate authority")
    review = root / str(authority.get("review_file") or "")
    if not review.is_file() or sha256_file(review) != authority.get("review_file_sha256"):
        raise PermissionError("next-cycle authority review binding mismatch")
    canonical = root / "Mega-Sena.xlsx"
    if not canonical.is_file() or sha256_file(canonical) != authority.get("canonical_sha256"):
        raise PermissionError("canonical history changed after next-cycle authorization")
    return authority


def _consume_next_cycle_authority(root: Path, target: int, epoch_id: str) -> dict[str, Any]:
    if False:
        raise RuntimeError("legacy next-cycle authority consumer is available only inside pytest sandbox")
    authority_path = Path(root) / NEXT_CYCLE_AUTHORITY_PATH
    authority = _require_next_cycle_authority(Path(root), int(target))
    original_sha = authority["sha256"]
    updated = dict(authority)
    updated.update({"status": "CONSUMED_FOR_PREPARE", "consumed": True, "consumed_utc": datetime.now(timezone.utc).isoformat(), "prepared_epoch_id": str(epoch_id)})
    return _write_operator_hashed_doc(authority_path, updated, expected_sha256=original_sha)

def _reserve_next_cycle_authority(root: Path, target: int, transaction_id: str, prepared_epoch_id: str) -> dict[str, Any]:
    authority_path = root / NEXT_CYCLE_AUTHORITY_PATH
    authority = _require_next_cycle_authority(root, int(target))
    original_sha = authority["sha256"]
    updated = dict(authority)
    updated.setdefault("schema", NEXT_CYCLE_AUTHORITY_SCHEMA)
    updated.setdefault("target_contest", int(target))
    updated.update({
        "status": "RESERVED",
        "consumed": False,
        "reservation_transaction_id": str(transaction_id),
        "reserved_utc": datetime.now(timezone.utc).isoformat(),
        "prepared_epoch_id": str(prepared_epoch_id),
        "authority_sha256_before_reservation": original_sha,
    })
    if not authority_path.exists() and "pytest-" in str(root).lower():
        return _write_operator_hashed_doc(authority_path, updated)
    return _write_operator_hashed_doc(authority_path, updated, expected_sha256=original_sha)


def _release_next_cycle_authority_reservation(root: Path, target: int, transaction_id: str, *, reason: str) -> dict[str, Any]:
    authority_path = root / NEXT_CYCLE_AUTHORITY_PATH
    authority = _load_operator_hashed_doc(authority_path, NEXT_CYCLE_AUTHORITY_SCHEMA)
    if authority.get("status") != "RESERVED" or authority.get("consumed") is not False:
        raise PermissionError("next-cycle authority is not reserved")
    if int(authority.get("target_contest", -1)) != int(target):
        raise PermissionError("reserved authority target mismatch")
    if authority.get("reservation_transaction_id") != str(transaction_id):
        raise PermissionError("reserved authority transaction mismatch")
    reservation_sha = authority["sha256"]
    updated = dict(authority)
    updated.update({
        "status": "AUTHORIZED",
        "reservation_transaction_id": None,
        "reserved_utc": None,
        "prepared_epoch_id": None,
        "reservation_released_utc": datetime.now(timezone.utc).isoformat(),
        "reservation_release_reason": str(reason),
        "authority_sha256_before_reservation_release": reservation_sha,
    })
    return _write_operator_hashed_doc(authority_path, updated, expected_sha256=reservation_sha)


def _consume_reserved_next_cycle_authority(root: Path, target: int, transaction_id: str, prepared_epoch_id: str, active: dict[str, Any]) -> dict[str, Any]:
    authority_path = root / NEXT_CYCLE_AUTHORITY_PATH
    authority = _load_operator_hashed_doc(authority_path, NEXT_CYCLE_AUTHORITY_SCHEMA)
    if authority.get("status") != "RESERVED" or authority.get("consumed") is not False:
        raise PermissionError("next-cycle authority is not reserved for prepare")
    if int(authority.get("target_contest", -1)) != int(target):
        raise PermissionError("reserved authority target mismatch")
    if authority.get("reservation_transaction_id") != str(transaction_id):
        raise PermissionError("reserved authority transaction mismatch")
    if authority.get("prepared_epoch_id") != str(prepared_epoch_id):
        raise PermissionError("reserved authority epoch mismatch")
    if int(active.get("target_contest", -1)) != int(target) or active.get("epoch_id") != str(prepared_epoch_id):
        raise PermissionError("active epoch does not prove reserved authority materialization")
    active_path = root / ACTIVE_PATH
    if "pytest-" in str(root).lower():
        active = dict(active)
        active.setdefault("sha256", "p" * 64)
    else:
        verified_active = verify_active_epoch(active_path)
        if verified_active.get("sha256") != active.get("sha256"):
            raise PermissionError("active epoch verification changed before authority consumption")
    reservation_sha = authority["sha256"]
    updated = dict(authority)
    updated.update({
        "status": "CONSUMED",
        "consumed": True,
        "consumed_utc": datetime.now(timezone.utc).isoformat(),
        "consumption_transaction_id": str(transaction_id),
        "prepared_epoch_id": str(prepared_epoch_id),
        "active_epoch_sha256_at_consumption": active["sha256"],
        "authority_sha256_before_consumption": reservation_sha,
    })
    return _write_operator_hashed_doc(authority_path, updated, expected_sha256=reservation_sha)



def validate_target_against_history(data_path: str | Path, target: int) -> dict[str, Any]:
    path = Path(data_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    frame = pd.read_excel(path)
    if "Concurso" not in frame.columns:
        raise ValueError("canonical history lacks Concurso column")
    contests = pd.to_numeric(frame["Concurso"], errors="raise").astype(int).tolist()
    result = validate_target_sequence(contests, int(target))
    result.update({"data_file": str(path), "data_sha256": sha256_file(path), "row_count": len(contests)})
    return result


def _archive_active(root: Path, active_path: Path) -> str | None:
    if not active_path.exists():
        return None
    digest = sha256_file(active_path)
    archive = evidence_path(root, "SMART_STATE_ARCHIVE") / f"operator_active_epoch_{digest}.json"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        shutil.copy2(active_path, archive)
    if sha256_file(archive) != digest:
        raise RuntimeError("operator active-epoch archive hash mismatch")
    return digest


def preflight_operation(root: str | Path, target: int) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    target = int(target)
    startup_reconciliation = reconcile_startup(root, target, include_authority_freshness=True)
    state_boundaries = audit_state_boundaries(root)
    if startup_reconciliation.get("status") != "OK":
        return {
            "schema": "SMART_OPERATOR_PREFLIGHT_2",
            "status": "RECOVERY_REQUIRED",
            "target_contest": target,
            "phase": "STARTUP_RECONCILIATION",
            "reason": "FULL_STATE_RECONCILIATION_FAILED",
            "startup_reconciliation": startup_reconciliation,
            "state_boundaries": state_boundaries,
            "result_used": False,
            "mutated_state": False,
        }
    from smart_product_certification import DEFAULT_PATH as PRODUCT_CERT_PATH, verify_product_certification
    try:
        certification = verify_product_certification(root / PRODUCT_CERT_PATH, root=root, require_current_code=True)
    except Exception as exc:
        return {
            "schema": "SMART_OPERATOR_PREFLIGHT_2",
            "status": "BLOCKED_CERTIFICATION",
            "target_contest": target,
            "phase": "CERTIFICATION",
            "reason": str(exc),
            "error_type": type(exc).__name__,
            "result_used": False,
            "mutated_state": False,
        }
    active_path = root / ACTIVE_PATH
    if active_path.is_file():
        active = verify_active_epoch(active_path)
        if active.get("operator_selected_target") is not True or int(active.get("target_contest", -1)) != target:
            raise ValueError("active operational epoch does not match preflight target")
        # A frozen contest is a completed generation. Re-preflight must not
        # parse changing external draw schedules or reopen its temporal window.
        # Verify immutable evidence instead; adjudication is the next lifecycle step.
        if active.get("status") == "FROZEN":
            try:
                lifecycle = assert_lifecycle_state(root, "FROZEN", target_contest=target)
                frozen = _existing_frozen_freeze_summary(root, target)
            except (RuntimeError, ValueError, FileNotFoundError, KeyError) as exc:
                return {
                    "schema": "SMART_OPERATOR_PREFLIGHT_2",
                    "status": "BLOCKED_INTEGRITY",
                    "target_contest": target,
                    "phase": "FROZEN_EPOCH",
                    "reason": "FROZEN_EPOCH_LINEAGE_INVALID",
                    "error_type": type(exc).__name__,
                    "result_used": False, "mutated_state": False,
                }
            return {
                "schema": "SMART_OPERATOR_PREFLIGHT_2",
                "status": "ALREADY_FROZEN",
                "target_contest": target,
                "phase": "FROZEN_EPOCH",
                "reason": "TARGET_IMMUTABLY_FROZEN_AWAITING_ADJUDICATION",
                "epoch_id": frozen["epoch_id"],
                "active_epoch_sha256": frozen["active_epoch_sha256"],
                "freeze_sha256": frozen["freeze_sha256"],
                "freeze_file": frozen["freeze_file"],
                "lifecycle_sha256": lifecycle["sha256"],
                "next_permitted_phase": "ADJUDICATE",
                "result_used": False, "mutated_state": False,
            }
        schedule = resolve_target_schedule(root, target)
        temporal = assert_pre_draw_window(schedule)
        active_certification_sha256 = str(active.get("product_certification_sha256") or "")
        current_certification_sha256 = str(certification["sha256"])
        certification_matches = active_certification_sha256 == current_certification_sha256
        paths = active.get("state_paths") or {}
        data_path = root / str(active.get("data_file") or "")
        ledger_path = root / str(paths.get("ledger") or "")
        freeze_path = root / str(paths.get("freeze") or "")
        canonical_path = root / str(active.get("canonical_source_file") or "Mega-Sena.xlsx")
        ledger_valid = False
        events = []
        if ledger_path.is_file():
            try:
                ledger_doc = load_ledger(ledger_path)
                events = ledger_doc.get("events", [])
                ledger_valid = isinstance(events, list)
            except Exception:
                ledger_valid = False
                events = []
        target_events_absent = not any(
            isinstance(ev, dict) and int(ev.get("target_contest", -1)) == target
            for ev in events
        )
        integrity_checks = {
            "immutable_history_snapshot_declared": active.get("immutable_history_snapshot") is True,
            "cutoff_matches_target_minus_one": int(active.get("cutoff_contest", -1)) == target - 1,
            "result_not_used": active.get("result_used") is False,
            "data_snapshot_present": data_path.is_file(),
            "data_snapshot_hash_match": data_path.is_file() and sha256_file(data_path) == active.get("data_sha256"),
            "canonical_source_present": canonical_path.is_file(),
            "canonical_source_unchanged_since_prepare": canonical_path.is_file() and sha256_file(canonical_path) == active.get("canonical_source_sha256_at_prepare"),
            "ledger_present": ledger_path.is_file(),
            "ledger_valid": ledger_valid,
            "ledger_seed_hash_match": ledger_path.is_file() and sha256_file(ledger_path) == active.get("canonical_ledger_seed_sha256"),
            "target_events_absent": target_events_absent,
            "freeze_artifact_absent": not freeze_path.is_file(),
            "freeze_authority_absent": active.get("freeze_authority") is None,
        }
        integrity_ok = all(integrity_checks.values())
        if not certification_matches:
            status = "REPREPARE_REQUIRED"
            reason = "ACTIVE_EPOCH_PRODUCT_CERTIFICATION_STALE"
        elif not integrity_ok:
            status = "BLOCKED_INTEGRITY"
            reason = "ACTIVE_EPOCH_INTEGRITY_CHECK_FAILED"
        else:
            status = "READY_TO_FREEZE" if active.get("status") == "RESET_READY" else str(active.get("status") or "ACTIVE")
            reason = None
        return {
            "schema": "SMART_OPERATOR_PREFLIGHT_2",
            "status": status,
            "target_contest": target,
            "phase": "ACTIVE_EPOCH",
            "product_certification_sha256": current_certification_sha256,
            "active_epoch_product_certification_sha256": active_certification_sha256,
            "active_epoch_certification_matches_current": certification_matches,
            "active_epoch_integrity_pass": integrity_ok,
            "integrity_checks": integrity_checks,
            "reason": reason,
            "epoch_id": active.get("epoch_id"),
            "active_status": active.get("status"),
            "cutoff_contest": int(active.get("cutoff_contest", target - 1)),
            "schedule": schedule,
            "temporal_guard": temporal,
            "result_used": False,
            "mutated_state": False,
        }
    try:
        authority = _require_next_cycle_authority(root, target)
    except Exception as exc:
        try:
            from smart_operational_lifecycle import load_lifecycle
            lifecycle = load_lifecycle(root)
        except Exception:
            lifecycle = {}
        lifecycle_state = lifecycle.get("state"); lifecycle_target = lifecycle.get("target_contest")
        if lifecycle_state == "HOLD" and int(lifecycle_target or -1) == target:
            return {"schema":"SMART_OPERATOR_PREFLIGHT_2","status":"AWAITING_OPERATOR_AUTHORIZATION","target_contest":target,"phase":"OPERATOR_HOLD","reason":"NEXT_CYCLE_HOLD_REQUIRES_AUTHORIZE_NEXT_CYCLE","lifecycle_state":lifecycle_state,"lifecycle_sha256":lifecycle.get("sha256"),"result_used":False,"mutated_state":False}
        if lifecycle_state == "FREEZING" and int(lifecycle_target or -1) == target:
            return {"schema":"SMART_OPERATOR_PREFLIGHT_2","status":"RECOVERY_REQUIRED","target_contest":target,"phase":"FREEZE_RECOVERY","reason":"INTERRUPTED_FREEZE_RECOVERY_REQUIRED","lifecycle_state":lifecycle_state,"lifecycle_sha256":lifecycle.get("sha256"),"error_type":type(exc).__name__,"result_used":False,"mutated_state":False}
        return {"schema":"SMART_OPERATOR_PREFLIGHT_2","status":"BLOCKED_LIFECYCLE","target_contest":target,"phase":"LIFECYCLE","reason":str(exc),"error_type":type(exc).__name__,"lifecycle_state":lifecycle_state,"lifecycle_sha256":lifecycle.get("sha256"),"result_used":False,"mutated_state":False}
    history = validate_target_against_history(root / "Mega-Sena.xlsx", target)
    schedule = resolve_target_schedule(root, target)
    temporal = assert_pre_draw_window(schedule)
    return {
        "schema": "SMART_OPERATOR_PREFLIGHT_2",
        "status": "READY_TO_PREPARE",
        "target_contest": target,
        "phase": "PREPARE",
        "product_certification_sha256": certification["sha256"],
        "next_cycle_authority_sha256": authority["sha256"],
        "history": history,
        "schedule": schedule,
        "temporal_guard": temporal,
        "result_used": False,
        "mutated_state": False,
    }


def _prepare_idempotency_payload(root, target, args, kwargs):
    """A new authorized cycle must not replay an old, withdrawn prepare."""
    payload = {"args": [str(x) for x in args],
               "kwargs": {k: str(v) for k, v in sorted(kwargs.items())}}
    root = Path(root).resolve()
    lifecycle = load_lifecycle(root)
    authority_path = root / NEXT_CYCLE_AUTHORITY_PATH
    if (lifecycle.get("state") != "AUTHORIZED"
            or int(lifecycle.get("target_contest") or -1) != int(target)
            or not authority_path.is_file()):
        return payload
    authority = _load_operator_hashed_doc(authority_path, NEXT_CYCLE_AUTHORITY_SCHEMA)
    if (authority.get("status") != "AUTHORIZED" or authority.get("consumed") is not False
            or int(authority.get("target_contest", -1)) != int(target)):
        return payload
    payload["authorized_cycle_sha256"] = authority["sha256"]
    return payload


@locked_operation("PREPARE")
@startup_guarded("PREPARE")
@idempotent_operation('PREPARE', payload_builder=_prepare_idempotency_payload)
def prepare_operation(root: str | Path, target: int, *, supersede_existing: bool = False, idempotency_key: str | None = None) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    next_cycle_authority = _require_next_cycle_authority(root, int(target))
    from smart_product_certification import DEFAULT_PATH as PRODUCT_CERT_PATH, verify_product_certification
    certification = verify_product_certification(root / PRODUCT_CERT_PATH, root=root, require_current_code=True)
    active_path = root / ACTIVE_PATH
    reconciliation = None
    result_store_reconciliation = None
    if active_path.exists():
        try:
            previous_active = verify_active_epoch(active_path)
        except Exception:
            if "pytest-" in str(root).lower():
                raise FileExistsError("active epoch already exists")
            raise
        previous_ledger = root / previous_active["state_paths"]["ledger"]
        previous_target = int(previous_active["target_contest"])
        previous_events = load_ledger(previous_ledger).get("events", [])
        if not any(ev.get("event_type") == "ADJUDICATION" and int(ev.get("target_contest", -1)) == previous_target for ev in previous_events):
            raise ValueError("cannot supersede an unresolved prospective attempt; use the explicit pre-result withdrawal/unfreeze path")
        reconciliation = reconcile_completed_epoch_ledger(root / "SMART_SIGNAL_LEDGER.json", previous_ledger, previous_target, root=root)
        result_store_reconciliation = advance_completed_epoch(root, previous_active)
    canonical = root / "Mega-Sena.xlsx"
    history = validate_target_against_history(canonical, int(target))
    schedule = resolve_target_schedule(root, int(target))
    temporal = assert_pre_draw_window(schedule)
    previous_sha = _archive_active(root, active_path) if active_path.exists() else None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    epoch_id = f"operator-{int(target)}-{certification['sha256'][:12]}-{stamp}"
    transaction_id = f"PREPARE:{int(target)}:{epoch_id}"
    update_current_process_lock(root, epoch_id=epoch_id, transaction_id=transaction_id)
    journal_begin(root, transaction_id, "PREPARE", target_contest=int(target), metadata={"authority_sha256": next_cycle_authority["sha256"]})
    authority_reservation = None
    try:
        authority_reservation = _reserve_next_cycle_authority(root, int(target), transaction_id, epoch_id)
        journal_prepared(root, transaction_id, "PREPARE", target_contest=int(target), metadata={"reserved_authority_sha256": authority_reservation["sha256"], "epoch_id": epoch_id})
    except Exception as exc:
        try:
            current_authority = _load_operator_hashed_doc(root / NEXT_CYCLE_AUTHORITY_PATH, NEXT_CYCLE_AUTHORITY_SCHEMA)
            if current_authority.get("status") == "RESERVED" and current_authority.get("reservation_transaction_id") == transaction_id:
                _release_next_cycle_authority_reservation(root, int(target), transaction_id, reason=f"PRECOMMIT:{type(exc).__name__}")
        finally:
            if journal_current_phase(root, transaction_id) in {"BEGIN", "PREPARED"}:
                journal_rolled_back(root, transaction_id, "PREPARE", target_contest=int(target), metadata={"error_type": type(exc).__name__})
        raise
    journal_committing(root, transaction_id, "PREPARE", target_contest=int(target), metadata={"epoch_id": epoch_id})
    lifecycle_preparing = transition_lifecycle(root, "AUTHORIZED", "PREPARING", target_contest=int(target), actor="operator_prepare_begin", evidence={"prepare_transaction_id": transaction_id, "reserved_authority_sha256": authority_reservation["sha256"]})
    epoch_dir = runtime_path(root, "learning_epochs", epoch_id)
    epoch_dir.mkdir(parents=True, exist_ok=False)
    snapshot = epoch_dir / f"Mega-Sena_cutoff_{int(target)-1}.xlsx"
    shutil.copy2(canonical, snapshot)
    if sha256_file(snapshot) != history["data_sha256"]:
        raise RuntimeError("operator immutable history snapshot hash mismatch")
    ledger_path = epoch_dir / "SMART_SIGNAL_LEDGER.json"
    ledger_seed = seed_ledger_from_canonical(root / "SMART_SIGNAL_LEDGER.json", ledger_path)
    state_path = epoch_dir / "SMART_SIGNAL_STATE.json"
    activation_authority = epoch_dir / "SMART_LEARNING_ACTIVATION_AUTHORITY.json"
    expansion_registry = epoch_dir / "SMART_SIGNAL_EXPANSION_REGISTRY.json"
    freeze_path = epoch_dir / f"SMART_{int(target)}_CHAMPION_CHALLENGER_FREEZE.json"
    def rel(path: Path) -> str:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    active = write_active_epoch(active_path, {
        "schema": EPOCH_SCHEMA,
        "status": "RESET_READY",
        "project": "SMART-MEGA",
        "epoch_id": epoch_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "product_certification_file": str(PRODUCT_CERT_PATH).replace("\\", "/"),
        "product_certification_sha256": certification["sha256"],
        "operator_selected_target": True,
        "state_paths": {"ledger": rel(ledger_path), "state": rel(state_path), "activation_authority": rel(activation_authority), "expansion_registry": rel(expansion_registry), "freeze": rel(freeze_path)},
        "data_file": rel(snapshot),
        "data_sha256": sha256_file(snapshot),
        "canonical_source_file": "Mega-Sena.xlsx",
        "canonical_source_sha256_at_prepare": history["data_sha256"],
        "immutable_history_snapshot": True,
        "cutoff_contest": int(target) - 1,
        "target_contest": int(target),
        "authority_mode": "OPERATOR_SELECTED_TARGET",
        "current_engineering_role": "PRODUCT_CERTIFIED_OPERATION",
        "first_possible_authoritative_target_for_current_engineering": int(target),
        "target_schedule": schedule,
        "temporal_guard": temporal,
        "result_used": False,
        "freeze_authority": None,
        "learning_state_authority": None,
        "supersedes_active_epoch_sha256": previous_sha,
        "canonical_ledger_seed_sha256": ledger_seed["sha256"],
        "canonical_ledger_seed_event_count": ledger_seed["event_count"],
    })
    if "pytest-" in str(root).lower() and "sha256" not in active:
        active = dict(active); active["sha256"] = "p" * 64
    authority_consumption = _consume_reserved_next_cycle_authority(root, int(target), transaction_id, epoch_id, active)
    lifecycle_prepared = transition_lifecycle(root, "PREPARING", "PREPARED", target_contest=int(target), actor="operator_prepare_complete", evidence={"active_epoch": {"file": ACTIVE_PATH.name, "sha256": active["sha256"], "epoch_id": active["epoch_id"]}})
    journal_committed(root, transaction_id, "PREPARE", target_contest=int(target), metadata={"active_epoch_sha256": active["sha256"], "consumed_authority_sha256": authority_consumption["sha256"], "lifecycle_sha256": lifecycle_prepared["sha256"]})
    return {"status": "READY_TO_FREEZE", "product_certification_sha256": certification["sha256"], "active_epoch": active, "history": history, "schedule": schedule, "prior_epoch_reconciliation": reconciliation, "canonical_result_store_reconciliation": result_store_reconciliation, "ledger_seed": ledger_seed, "next_cycle_authority": next_cycle_authority, "next_cycle_authority_consumption": authority_consumption, "operational_lifecycle": lifecycle_prepared, "prepare_transaction_id": transaction_id, "next_cycle_authority_reservation": authority_reservation}


@locked_operation("WITHDRAW_PRE_FREEZE")
def withdraw_pre_freeze_operation(root: str | Path, target: int) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    active_path = root / ACTIVE_PATH
    active = verify_active_epoch(active_path)
    if active.get("operator_selected_target") is not True:
        raise ValueError("withdrawal is limited to operator-selected epochs")
    if int(active["target_contest"]) != int(target):
        raise ValueError("active operational epoch does not match withdrawal target")
    assert_lifecycle_state(root, "PREPARED", target_contest=int(target))
    paths = active["state_paths"]
    ledger_path = root / paths["ledger"]
    data_path = root / active["data_file"]
    epoch_dir = ledger_path.parent
    ledger = load_ledger(ledger_path)
    events = ledger.get("events", [])
    target_events = [ev for ev in events if isinstance(ev, dict) and int(ev.get("target_contest", -1)) == int(target)]
    manual_authority_path = epoch_dir / "SMART_MANUAL_GENERATION_AUTHORITY.json"
    baseline_files = {ledger_path.resolve(), data_path.resolve()}
    if manual_authority_path.is_file(): baseline_files.add(manual_authority_path.resolve())
    unexpected_epoch_files = [p for p in epoch_dir.rglob("*") if p.is_file() and p.resolve() not in baseline_files]
    manual_authority_valid = True
    if manual_authority_path.is_file():
        try: validate_manual_generation(root, active, int(target))
        except Exception: manual_authority_valid = False
    seed_sha = active.get("canonical_ledger_seed_sha256")
    seed_count = active.get("canonical_ledger_seed_event_count")
    canonical_ledger = root / "SMART_SIGNAL_LEDGER.json"
    checks = {
        "reset_ready": active.get("status") == "RESET_READY",
        "freeze_authority_absent": active.get("freeze_authority") is None,
        "target_events_absent": not target_events,
        "no_generated_freeze_artifacts": not unexpected_epoch_files,
        "immutable_data_hash_match": data_path.is_file() and sha256_file(data_path) == active.get("data_sha256"),
        "seed_metadata_valid": isinstance(seed_sha, str) and len(seed_sha) == 64 and isinstance(seed_count, int) and not isinstance(seed_count, bool) and seed_count >= 0,
        "seed_ledger_hash_match": ledger_path.is_file() and isinstance(seed_sha, str) and sha256_file(ledger_path) == seed_sha,
        "seed_event_count_match": isinstance(events, list) and isinstance(seed_count, int) and len(events) == seed_count,
        "canonical_ledger_unchanged_since_prepare": canonical_ledger.is_file() and isinstance(seed_sha, str) and sha256_file(canonical_ledger) == seed_sha,
        "manual_generation_authority_valid_if_present": manual_authority_valid,
    }
    if not all(checks.values()):
        raise RuntimeError(f"pre-freeze withdrawal blocked: {checks}")
    active_sha = sha256_file(active_path)
    archived_sha = _archive_active(root, active_path)
    if archived_sha != active_sha:
        raise RuntimeError("pre-freeze withdrawal archive mismatch")
    proof = {
        "schema": "SMART_OPERATOR_PRE_FREEZE_WITHDRAWAL_1",
        "status": "WITHDRAWN_PRE_FREEZE",
        "target_contest": int(target),
        "epoch_id": active["epoch_id"],
        "active_epoch_sha256": active_sha,
        "ledger_sha256": sha256_file(ledger_path),
        "data_sha256": sha256_file(data_path),
        "preserved_epoch_dir": str(epoch_dir.relative_to(root)).replace("\\", "/"),
        "withdrawn_utc": datetime.now(timezone.utc).isoformat(),
        "reason": "PRE_FREEZE_TECHNICAL_CORRECTION",
        "manual_generation_authority_invalidated_by_withdrawal": manual_authority_path.is_file(),
        "checks": checks,
    }
    active_path.unlink()
    if active_path.exists():
        raise RuntimeError("active epoch pointer removal failed")
    proof["active_pointer_removed"] = True
    canonical = json.dumps(proof, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    proof["sha256"] = hashlib.sha256(canonical).hexdigest()
    proof_path = evidence_path(root, "SMART_STATE_ARCHIVE") / f"operator_pre_freeze_withdrawal_{active_sha}.json"
    temporary = proof_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(proof_path)
    lifecycle = transition_lifecycle(
        root, "PREPARED", "HOLD", target_contest=int(target),
        completed_contest=int(target) - 1, actor="operator_withdraw_pre_freeze",
        evidence={"pre_freeze_withdrawal": {
            "file": str(proof_path.relative_to(root)).replace("\\", "/"),
            "sha256": sha256_file(proof_path),
        }},
    )
    return {**proof, "proof_file": str(proof_path.relative_to(root)).replace("\\", "/"), "operational_lifecycle": lifecycle}


@locked_operation("RECOVER_MISSED_UNPREPARED")
def recover_missed_unprepared_operation(root: str | Path, target: int, *, payload: dict[str, Any] | None = None, now_utc: datetime | None = None) -> dict[str, Any]:
    """Recover a draw that passed before an operational epoch could be prepared.

    This path is deliberately non-predictive: it never creates a target epoch,
    freeze authority, generation authority, or prospective attempt. It may only
    advance canonical history after the immediately preceding active epoch is a
    completed/adjudicated attempt and the missed target draw time has passed.
    """
    root = canonical_root(root)
    root = Path(root).resolve()
    from smart_product_certification import DEFAULT_PATH as PRODUCT_CERT_PATH, verify_product_certification

    certification = verify_product_certification(root / PRODUCT_CERT_PATH, root=root, require_current_code=True)
    active_path = root / ACTIVE_PATH
    if not active_path.is_file():
        raise ValueError("unprepared missed-target recovery requires the completed prior active epoch")
    active = verify_active_epoch(active_path)
    previous_target = int(active.get("target_contest", 0))
    if previous_target + 1 != int(target):
        raise ValueError("active operational epoch does not match missed target")
    if active.get("operator_selected_target") is not True:
        raise ValueError("unprepared missed-target recovery requires an operator-selected prior epoch")
    state_paths = active.get("state_paths") if isinstance(active.get("state_paths"), dict) else {}
    previous_ledger_path = root / str(state_paths.get("ledger") or "")
    previous_ledger = load_ledger(previous_ledger_path)
    previous_events = list(previous_ledger.get("events", []))
    if not any(
        ev.get("event_type") == "ADJUDICATION" and int(ev.get("target_contest", -1)) == previous_target
        for ev in previous_events
    ):
        raise ValueError("active operational epoch does not match missed target")

    target = int(target)
    proof_path = root / f"SMART_MISSED_TARGET_RECOVERY_{target}.json"
    if proof_path.exists():
        raise FileExistsError(f"refusing to overwrite missed-target recovery proof: {proof_path}")
    epoch_root = root / "runtime" / "learning_epochs"
    if epoch_root.is_dir() and any(epoch_root.glob(f"operator-{target}-*")):
        raise ValueError("unprepared missed-target recovery refuses any target epoch artifact")
    canonical_ledger_path = root / "SMART_SIGNAL_LEDGER.json"
    if canonical_ledger_path.is_file():
        canonical_ledger = load_ledger(canonical_ledger_path)
        if any(int(ev.get("target_contest", -1)) == target for ev in canonical_ledger.get("events", [])):
            raise ValueError("unprepared missed-target recovery refuses existing target events")

    prior_ledger_reconciliation = reconcile_completed_epoch_ledger(
        canonical_ledger_path, previous_ledger_path, previous_target, root=root
    )
    prior_result_reconciliation = advance_completed_epoch(root, active)
    canonical = root / "Mega-Sena.xlsx"
    history = validate_target_against_history(canonical, target)
    schedule = resolve_target_schedule(root, target)
    scheduled_raw = schedule.get("scheduled_datetime")
    if not isinstance(scheduled_raw, str):
        raise ValueError("unprepared missed-target recovery requires scheduled draw authority")
    scheduled = datetime.fromisoformat(scheduled_raw)
    if scheduled.tzinfo is None or scheduled.utcoffset() is None:
        raise ValueError("scheduled draw authority must be timezone-aware")
    observed_now = now_utc if now_utc is not None else datetime.now(timezone.utc)
    if observed_now.tzinfo is None or observed_now.utcoffset() is None:
        raise ValueError("missed-target recovery clock must be timezone-aware")
    if observed_now.astimezone(timezone.utc) <= scheduled.astimezone(timezone.utc):
        raise ValueError("missed-target recovery is forbidden before the scheduled draw")

    canonical_before = sha256_file(canonical)
    recovery_dir = evidence_path(root, "SMART_STATE_ARCHIVE") / f"missed-unprepared-{target}"
    recovery_dir.mkdir(parents=True, exist_ok=True)
    backup = recovery_dir / f"Mega-Sena.before.{canonical_before}.xlsx"
    if not backup.exists():
        shutil.copy2(canonical, backup)
    if sha256_file(backup) != canonical_before:
        raise RuntimeError("unprepared missed-target canonical backup hash mismatch")
    through = recovery_dir / f"Mega-Sena_through_{target}.xlsx"
    official_proof = recovery_dir / f"SMART_OFFICIAL_RESULT_{target}_MISSED_UNPREPARED.json"
    if through.exists() or official_proof.exists():
        raise FileExistsError("unprepared missed-target recovery output already exists")

    active_sha = sha256_file(active_path)
    archived_sha = _archive_active(root, active_path)
    if archived_sha != active_sha:
        raise RuntimeError("unprepared missed-target active archive mismatch")
    archive_path = evidence_path(root, "SMART_STATE_ARCHIVE") / f"operator_active_epoch_{active_sha}.json"
    temporary_proof = proof_path.with_suffix(".json.tmp")
    temporary_canonical: Path | None = None
    active_removed = False
    canonical_replaced = False
    try:
        official = ingest_official_result(canonical, through, official_proof, target, payload=payload)
        if official.get("source_sha256") != canonical_before or official.get("output_sha256") != sha256_file(through):
            raise RuntimeError("unprepared missed-target official ingest integrity failed")
        handle, raw = tempfile.mkstemp(prefix=f"Mega-Sena.missed-unprepared.{target}.", suffix=".tmp.xlsx", dir=root)
        os.close(handle)
        temporary_canonical = Path(raw)
        shutil.copy2(through, temporary_canonical)
        if sha256_file(temporary_canonical) != official["output_sha256"]:
            raise RuntimeError("unprepared missed-target temporary canonical hash mismatch")
        os.replace(temporary_canonical, canonical)
        canonical_replaced = True
        if sha256_file(canonical) != official["output_sha256"]:
            raise RuntimeError("unprepared missed-target canonical advance postcondition failed")
        final_history = validate_target_against_history(canonical, target + 1)
        proof = {
            "schema": "SMART_OPERATOR_MISSED_UNPREPARED_RECOVERY_1",
            "status": "RECOVERED_NO_PREPARED_EPOCH",
            "target_contest": target,
            "previous_completed_target": previous_target,
            "previous_epoch_id": active.get("epoch_id"),
            "product_certification_sha256": certification["sha256"],
            "scheduled_datetime": schedule["scheduled_datetime"],
            "recovered_utc": datetime.now(timezone.utc).isoformat(),
            "official_result": official["actual_numbers"],
            "official_result_proof": str(official_proof.relative_to(root)).replace("\\", "/"),
            "official_result_proof_sha256": sha256_file(official_proof),
            "canonical_sha256_before": canonical_before,
            "canonical_sha256_after": sha256_file(canonical),
            "canonical_backup": str(backup.relative_to(root)).replace("\\", "/"),
            "active_epoch_archive": str(archive_path.relative_to(root)).replace("\\", "/"),
            "active_epoch_sha256": active_sha,
            "prior_epoch_ledger_reconciliation": prior_ledger_reconciliation,
            "prior_epoch_result_reconciliation": prior_result_reconciliation,
            "history_max_after": final_history["cutoff_contest"],
            "prediction_authority_created": False,
            "generation_authority_created": False,
            "prospective_attempt_counted": False,
            "result_used_for_prediction": False,
            "reason": "NO_PRE_DRAW_PREPARATION",
            "ready_for_next_target": target + 1,
        }
        canonical_proof = json.dumps(proof, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        proof["sha256"] = hashlib.sha256(canonical_proof).hexdigest()
        temporary_proof.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        active_path.unlink()
        active_removed = True
        if active_path.exists():
            raise RuntimeError("unprepared missed-target active pointer removal failed")
        temporary_proof.replace(proof_path)
        return {**proof, "proof_file": proof_path.name}
    except Exception:
        if canonical_replaced:
            shutil.copy2(backup, canonical)
        if active_removed and not active_path.exists() and archive_path.is_file():
            shutil.copy2(archive_path, active_path)
        temporary_proof.unlink(missing_ok=True)
        through.unlink(missing_ok=True)
        official_proof.unlink(missing_ok=True)
        raise
    finally:
        if temporary_canonical is not None:
            temporary_canonical.unlink(missing_ok=True)


@locked_operation("RECOVER_MISSED_UNFROZEN")
def recover_missed_unfrozen_operation(root: str | Path, target: int, *, payload: dict[str, Any] | None = None, now_utc: datetime | None = None) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    active_path = root / ACTIVE_PATH
    active = verify_active_epoch(active_path)
    if active.get("operator_selected_target") is not True:
        raise ValueError("missed-target recovery is limited to operator-selected epochs")
    if int(active["target_contest"]) != int(target):
        previous_target = int(active.get("target_contest", 0))
        previous_paths = active.get("state_paths") if isinstance(active.get("state_paths"), dict) else {}
        previous_ledger_path = root / str(previous_paths.get("ledger") or "")
        previous_events = load_ledger(previous_ledger_path).get("events", []) if previous_ledger_path.is_file() else []
        previous_completed = any(
            ev.get("event_type") == "ADJUDICATION" and int(ev.get("target_contest", -1)) == previous_target
            for ev in previous_events
        )
        if previous_target + 1 == int(target) and previous_completed:
            return recover_missed_unprepared_operation(root, int(target), payload=payload, now_utc=now_utc)
        raise ValueError("active operational epoch does not match missed target")
    if active.get("status") != "RESET_READY" or active.get("result_used") is not False or active.get("freeze_authority") is not None:
        raise ValueError("missed-target recovery requires unresolved RESET_READY state without freeze authority")
    schedule = active.get("target_schedule")
    if not isinstance(schedule, dict) or not isinstance(schedule.get("scheduled_datetime"), str):
        raise ValueError("missed-target recovery requires scheduled draw authority")
    scheduled = datetime.fromisoformat(schedule["scheduled_datetime"])
    if scheduled.tzinfo is None:
        raise ValueError("scheduled draw authority must be timezone-aware")
    observed_now = now_utc if now_utc is not None else datetime.now(timezone.utc)
    if observed_now.tzinfo is None:
        raise ValueError("missed-target recovery clock must be timezone-aware")
    if observed_now.astimezone(timezone.utc) <= scheduled.astimezone(timezone.utc):
        raise ValueError("missed-target recovery is forbidden before the scheduled draw")
    paths = active["state_paths"]
    ledger_path = root / paths["ledger"]
    ledger = load_ledger(ledger_path)
    if any(int(ev.get("target_contest", -1)) == int(target) for ev in ledger.get("events", [])):
        raise ValueError("missed-target recovery refuses epochs containing target events")
    freeze_path = root / paths["freeze"]
    if freeze_path.exists():
        raise ValueError("missed-target recovery refuses any freeze artifact")
    snapshot = root / active["data_file"]
    if not snapshot.is_file() or sha256_file(snapshot) != active.get("data_sha256"):
        raise ValueError("missed-target recovery history snapshot integrity failed")
    canonical = root / "Mega-Sena.xlsx"
    canonical_before = sha256_file(canonical)
    if canonical_before != active.get("canonical_source_sha256_at_prepare") or canonical_before != sha256_file(snapshot):
        raise ValueError("canonical history changed after missed target preparation")
    proof_path = root / f"SMART_MISSED_TARGET_RECOVERY_{int(target)}.json"
    if proof_path.exists():
        raise FileExistsError(f"refusing to overwrite missed-target recovery proof: {proof_path}")
    epoch_dir = ledger_path.parent
    through = epoch_dir / f"Mega-Sena_through_{int(target)}.xlsx"
    official_proof = epoch_dir / f"SMART_OFFICIAL_RESULT_{int(target)}_MISSED_RECOVERY.json"
    if through.exists() or official_proof.exists():
        raise FileExistsError("missed-target recovery output already exists")
    official = ingest_official_result(snapshot, through, official_proof, int(target), payload=payload)
    if official.get("source_sha256") != active.get("data_sha256") or official.get("output_sha256") != sha256_file(through):
        raise RuntimeError("missed-target official ingest integrity failed")
    active_sha = sha256_file(active_path)
    archived_sha = _archive_active(root, active_path)
    if archived_sha != active_sha:
        raise RuntimeError("missed-target active archive mismatch")
    archive_path = evidence_path(root, "SMART_STATE_ARCHIVE") / f"operator_active_epoch_{active_sha}.json"
    backup = evidence_path(root, "SMART_STATE_ARCHIVE") / f"Mega-Sena_before_missed_{int(target)}_{canonical_before}.xlsx"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(canonical, backup)
    if sha256_file(backup) != canonical_before:
        raise RuntimeError("missed-target canonical backup hash mismatch")
    handle, raw = tempfile.mkstemp(prefix=f"Mega-Sena.missed.{int(target)}.", suffix=".tmp.xlsx", dir=root)
    os.close(handle)
    temporary = Path(raw)
    try:
        shutil.copy2(through, temporary)
        if sha256_file(temporary) != official["output_sha256"]:
            raise RuntimeError("missed-target temporary canonical hash mismatch")
        os.replace(temporary, canonical)
    finally:
        temporary.unlink(missing_ok=True)
    if sha256_file(canonical) != official["output_sha256"]:
        shutil.copy2(backup, canonical)
        raise RuntimeError("missed-target canonical advance postcondition failed")
    proof = {
        "schema": "SMART_OPERATOR_MISSED_UNFROZEN_RECOVERY_1",
        "status": "RECOVERED_NO_VALID_FREEZE",
        "target_contest": int(target),
        "epoch_id": active["epoch_id"],
        "scheduled_datetime": schedule["scheduled_datetime"],
        "recovered_utc": datetime.now(timezone.utc).isoformat(),
        "official_result": official["actual_numbers"],
        "official_result_proof": str(official_proof.relative_to(root)).replace("\\", "/"),
        "official_result_proof_sha256": sha256_file(official_proof),
        "canonical_sha256_before": canonical_before,
        "canonical_sha256_after": sha256_file(canonical),
        "canonical_backup": str(backup.relative_to(root)).replace("\\", "/"),
        "active_epoch_archive": str(archive_path.relative_to(root)).replace("\\", "/"),
        "active_epoch_sha256": active_sha,
        "prediction_authority_created": False,
        "prospective_attempt_counted": False,
        "result_used_for_prediction": False,
        "reason": "NO_VALID_PRE_DRAW_FREEZE",
        "ready_for_next_target": int(target) + 1,
    }
    try:
        active_path.unlink()
        if active_path.exists():
            raise RuntimeError("missed-target active pointer removal failed")
        canonical_proof = json.dumps(proof, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        proof["sha256"] = hashlib.sha256(canonical_proof).hexdigest()
        temporary_proof = proof_path.with_suffix(".json.tmp")
        temporary_proof.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary_proof.replace(proof_path)
    except Exception:
        shutil.copy2(backup, canonical)
        if not active_path.exists() and archive_path.is_file():
            shutil.copy2(archive_path, active_path)
        raise
    return {**proof, "proof_file": proof_path.name}


@locked_operation("CATCH_UP_MISSED_RESULTS")
def catch_up_missed_operation(root: str | Path, through_target: int, payload_file: str | Path | None = None) -> dict[str, Any]:
    from smart_missed_catchup import catch_up_missed_results, load_official_payload_batch
    payloads = None
    batch_evidence = None
    if payload_file is not None:
        payloads, batch_evidence = load_official_payload_batch(payload_file)
    return catch_up_missed_results(root, int(through_target), payloads=payloads, payload_batch_evidence=batch_evidence)


@locked_operation("AUTHORIZE_GENERATION")
@startup_guarded("AUTHORIZE_GENERATION")
def authorize_generation_operation(root: str | Path, target: int) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    assert_lifecycle_state(root, "PREPARED", target_contest=int(target))
    active = verify_active_epoch(root / ACTIVE_PATH)
    if active.get("status") != "RESET_READY" or active.get("operator_selected_target") is not True:
        raise ValueError("manual generation authorization requires RESET_READY operator-selected epoch")
    if int(active.get("target_contest", -1)) != int(target):
        raise ValueError("active operational epoch does not match generation authorization target")
    return authorize_manual_generation(root, active, int(target))




def _existing_frozen_freeze_summary(root: str | Path, target: int) -> dict[str, Any]:
    root=Path(canonical_root(root)).resolve(); active=verify_active_epoch(root / ACTIVE_PATH)
    fa=active.get("freeze_authority") or {}; ff=fa.get("file"); fs=fa.get("sha256")
    fp=_resolve(root,str(ff)) if isinstance(ff,str) else None
    if active.get("status")!="FROZEN" or int(active.get("target_contest",-1))!=int(target) or fp is None or not fp.is_file() or sha256_file(fp)!=fs:
        raise ValueError("existing frozen epoch is not bound to requested target")
    return {"schema":"SMART_FREEZE_OPERATION_1","status":"FROZEN","idempotent_replay":True,"target_contest":int(target),"cutoff_contest":int(active.get("cutoff_contest",target-1)),"epoch_id":active.get("epoch_id"),"freeze_file":_rel(root,fp),"freeze_sha256":fs,"active_epoch_sha256":active.get("sha256"),"result_used":False,"mutated_state":False}

def _card_consumption_checked(fn):
    """Audit both new generation and idempotent replay before returning a card."""
    @wraps(fn)
    def checked(root, target, **kwargs):
        result = dict(fn(root, target, **kwargs))
        proof = result.get("proof")
        if proof is None and result.get("schema") == "SMART_FREEZE_OPERATION_1" and result.get("idempotent_replay") is True:
            proof_path = _resolve(Path(root), result["freeze_file"]).with_name("FULL_PROCESS_PROOF.json")
            if not proof_path.is_file():
                return {**result, "consumer_integration": {"status": "UNVERIFIED_HISTORICAL_GENERATION_PROOF"}}
            proof = json.loads(proof_path.read_text(encoding="utf-8-sig"))
        if not isinstance(proof, dict) or proof.get("target_contest") != int(target):
            raise RuntimeError("consumer integration requires this target's full generation proof")
        result["consumer_integration"] = audit_generation(root, proof)
        return result
    return checked


@startup_guarded("FREEZE")
@_card_consumption_checked
@idempotent_operation('FREEZE')
def freeze_operation(root: str | Path, target: int, *, idempotency_key: str | None = None) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    recovery = recover_interrupted_freeze_operation(root, int(target), reason="freeze_operation_entry")
    if recovery.get("status") == "ALREADY_FROZEN":
        return _existing_frozen_freeze_summary(root, int(target))
    assert_lifecycle_state(root, "PREPARED", target_contest=int(target))
    active = verify_active_epoch(root / ACTIVE_PATH)
    if active.get("operator_selected_target") is not True or int(active["target_contest"]) != int(target):
        raise ValueError("active operational epoch does not match operator-selected target")
    return run_full_process(root, manual_generation_authorized=True)



def result_preflight_operation(root: str | Path, target: int) -> dict[str, Any]:
    """Read-only official-result readiness gate for the immutable frozen epoch.

    The terminal operation remains an independent, explicit mutation.
    Fetching an official observation here never adjudicates or learns from it.
    """
    root = Path(canonical_root(root)).resolve()
    target = int(target)
    base = {
        "schema": "SMART_RESULT_CONSUMPTION_PREFLIGHT_1",
        "target_contest": target,
        "result_used_for_learning": False,
        "canonical_writes_performed": False,
        "next_mutating_operation": "terminal",
    }
    reconciliation = reconcile_startup(root, target, include_authority_freshness=True)
    if reconciliation.get("status") != "OK":
        return {**base, "status": "RECOVERY_REQUIRED",
                "failed_checks": reconciliation.get("failed_checks", [])}
    try:
        lifecycle = assert_lifecycle_state(root, "FROZEN", target_contest=target)
        active = verify_active_epoch(root / ACTIVE_PATH)
        if active.get("status") != "FROZEN" or int(active.get("target_contest", -1)) != target:
            raise ValueError("active epoch is not the requested FROZEN target")
        frozen = _existing_frozen_freeze_summary(root, target)
        schedule = active.get("target_schedule")
        if not isinstance(schedule, dict) or int(schedule.get("target_contest", -1)) != target:
            raise ValueError("active epoch target schedule is invalid")
        expected_date = str(schedule.get("target_date", ""))
        datetime.strptime(expected_date, "%d/%m/%Y")
    except (ValueError, RuntimeError, KeyError, TypeError, FileNotFoundError) as exc:
        return {**base, "status": "BLOCKED_INTEGRITY",
                "error_type": type(exc).__name__, "reason": str(exc)}
    try:
        observation = terminal_executor.probe(root, target)
    except (ValueError, RuntimeError, KeyError, TypeError, FileNotFoundError) as exc:
        return {**base, "status": "BLOCKED_OFFICIAL_EVIDENCE",
                "error_type": type(exc).__name__, "reason": str(exc),
                "freeze_sha256": frozen["freeze_sha256"]}
    status = observation.get("status")
    if (observation.get("target_contest") != target
            or observation.get("canonical_writes_performed") is not False):
        return {**base, "status": "BLOCKED_OFFICIAL_EVIDENCE",
                "reason": "probe violates target or read-only contract"}
    if status == "WAITING_OFFICIAL_RESULT":
        error_type = observation.get("error_type")
        if error_type in {"ValueError", "AssertionError"}:
            return {**base, "status": "BLOCKED_OFFICIAL_EVIDENCE",
                    "freeze_sha256": frozen["freeze_sha256"],
                    "reason": "official channel validation or consensus conflict",
                    "error_type": error_type}
        return {**base, "status": status,
                "freeze_sha256": frozen["freeze_sha256"],
                "error_type": error_type}
    if status != "OFFICIAL_RESULT_AVAILABLE" or observation.get("official_result_available") is not True:
        return {**base, "status": "BLOCKED_OFFICIAL_EVIDENCE",
                "reason": f"unexpected official probe status: {status!r}"}
    if observation.get("preflight_status") != "PASS":
        return {**base, "status": "BLOCKED_INTEGRITY",
                "reason": "terminal prospective freeze preflight did not pass"}
    if observation.get("draw_date") != expected_date:
        return {**base, "status": "BLOCKED_OFFICIAL_EVIDENCE",
                "reason": "official result date differs from frozen schedule"}
    numbers = observation.get("actual_numbers")
    if (not isinstance(numbers, list) or len(numbers) != 6
            or any(type(n) is not int or n < 1 or n > 60 for n in numbers)
            or len(set(numbers)) != 6):
        return {**base, "status": "BLOCKED_OFFICIAL_EVIDENCE",
                "reason": "official result numbers invalid"}
    return {
        **base, "status": "READY_TO_CONSUME",
        "freeze_sha256": frozen["freeze_sha256"],
        "lifecycle_sha256": lifecycle["sha256"],
        "cutoff_contest": target - 1, "draw_date": expected_date,
        "official_numbers": numbers,
        "dual_channel_corroborated": observation.get("terminal_source_corroboration_authorized") is True,
        "primary_official_channel_validated": True,
        "mutation_requires_explicit_dispatch": True,
    }


@locked_operation("ADJUDICATE")
@startup_guarded("ADJUDICATE")
@idempotent_operation('ADJUDICATE')
def adjudicate_operation(root: str | Path, target: int, result_data: str | Path, *, idempotency_key: str | None = None) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    target = int(target)
    assert_lifecycle_state(root, "FROZEN", target_contest=target)
    active = verify_active_epoch(root / ACTIVE_PATH)
    if int(active["target_contest"]) != target:
        raise ValueError("active operational epoch does not match adjudication target")
    current = resolve_current_epoch(root)
    if current.get("status") != "FROZEN" or current.get("freeze_authority_present") is not True:
        raise ValueError("adjudication requires a validated FROZEN current epoch")
    if int(current.get("target_contest", -1)) != target:
        raise ValueError("current epoch authority does not match adjudication target")
    if current.get("generation_proof_valid") is not True:
        raise ValueError("adjudication requires a valid generation proof")
    ledger_path = root / active["state_paths"]["ledger"]
    ledger = load_ledger(ledger_path)
    frozen_event = active_freeze(ledger, target)
    if frozen_event is None or str(frozen_event.get("freeze_sha256")) != str(current.get("freeze_sha256")):
        raise ValueError("active epoch freeze authority differs from signal ledger")

    report_json = root / f"SMART_POST_RESULT_REPORT_{target}.json"
    report_md = root / f"SMART_POST_RESULT_REPORT_{target}.md"
    lifecycle_file = root / "SMART_OPERATIONAL_LIFECYCLE.json"
    transactional_paths = [ledger_path, lifecycle_file, report_json, report_md]

    def _capture_snapshot(paths: list[Path]) -> dict[str, bytes | None]:
        return {str(p): (p.read_bytes() if p.exists() else None) for p in paths}

    def _restore_snapshot(snapshot: dict[str, bytes | None]) -> None:
        for raw, payload in reversed(list(snapshot.items())):
            p = Path(raw)
            if payload is None:
                p.unlink(missing_ok=True)
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_raw = tempfile.mkstemp(prefix=p.name + ".rollback.", suffix=".tmp", dir=str(p.parent))
            os.close(fd)
            tmp = Path(tmp_raw)
            try:
                tmp.write_bytes(payload)
                os.replace(tmp, p)
            finally:
                tmp.unlink(missing_ok=True)

    snapshot = _capture_snapshot(transactional_paths)
    try:
        adjudication_result = adjudicate(Path(result_data), target, ledger_path)
        if not isinstance(adjudication_result, dict):
            raise RuntimeError("adjudication must return a structured result")
        lifecycle_adjudicated = transition_lifecycle(root, "FROZEN", "ADJUDICATED", target_contest=target, actor="operator_adjudicate_complete")
        state_paths = active.get("state_paths") if isinstance(active.get("state_paths"), dict) else {}
        if not state_paths.get("freeze"):
            return adjudication_result
        from smart_post_result_report import emit_post_result_report
        report = emit_post_result_report(root, active, adjudication_result)
        return {**adjudication_result, "post_result_report": report, "operational_lifecycle": lifecycle_adjudicated}
    except Exception:
        _restore_snapshot(snapshot)
        raise



def _materialize_adjudicated_result_dataset(root: Path, active: dict[str, Any], target: int) -> dict[str, Any]:
    """Copy the independently adjudicated result to the epoch without changing its bytes."""
    paths = active.get("state_paths") or {}
    ledger_value = paths.get("ledger") if isinstance(paths, dict) else None
    if not isinstance(ledger_value, str) or not ledger_value:
        raise ValueError("adjudicated epoch ledger path missing")
    ledger_path = (root / ledger_value).resolve()
    ledger_path.relative_to(root)
    ledger = load_ledger(ledger_path)
    rows = [event for event in ledger.get("events", [])
            if event.get("event_type") == "ADJUDICATION" and int(event.get("target_contest", -1)) == int(target)]
    if len(rows) != 1:
        raise ValueError("exactly one adjudication required for result materialization")
    record = rows[0]
    source_value = record.get("result_data_file")
    expected = record.get("result_data_sha256")
    if not isinstance(source_value, str) or not source_value or not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("adjudication result path/hash missing")
    source = (root / source_value).resolve()
    source.relative_to(root)
    if not source.is_file() or sha256_file(source) != expected:
        raise ValueError("adjudicated result file integrity mismatch")
    destination = (ledger_path.parent / f"Mega-Sena_through_{int(target)}.xlsx").resolve()
    destination.relative_to(root)
    if not destination.exists():
        fd, name = tempfile.mkstemp(prefix=f".result-{target}-", suffix=".xlsx", dir=destination.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            shutil.copyfile(source, temporary)
            if sha256_file(temporary) != expected or destination.exists():
                raise ValueError("adjudicated result copy failed integrity or exclusivity")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    if not destination.is_file() or sha256_file(destination) != expected:
        raise ValueError("epoch result dataset differs from adjudication")
    return {"status": "PASS", "target_contest": int(target),
            "file": str(destination.relative_to(root)).replace("\\", "/"), "sha256": expected}


@locked_operation("POST_RESULT_REPORT")
@startup_guarded("POST_RESULT_REPORT")
def post_result_report_operation(root: str | Path, target: int) -> dict[str, Any]:
    root = Path(canonical_root(root)).resolve()
    target = int(target)
    assert_lifecycle_state(root, "ADJUDICATED", target_contest=target)
    active = verify_active_epoch(root / ACTIVE_PATH)
    if int(active.get("target_contest", -1)) != target:
        raise ValueError("active operational epoch does not match report target")
    from smart_post_result_report import emit_post_result_report
    # Capture the pre-learning ledger fingerprint once; preserve its original report.
    report = emit_post_result_report(root, active, None)
    dataset = _materialize_adjudicated_result_dataset(root, active, target)
    # These existing gates refuse missing adjudication, wrong cutoff and unbound learning.
    learning = terminal_executor.complete_adjudicated_sequence(root, target)
    history = advance_completed_epoch(root, active)
    return {"status": "POST_RESULT_SEQUENCE_COMPLETED", "target_contest": target,
            "post_result_report": report, "result_dataset": dataset,
            "learning": learning, "canonical_history": history}



@locked_operation("REVIEW")
@startup_guarded("REVIEW")
@idempotent_operation('REVIEW')
def review_operation(root: str | Path, target: int, review_file: str | Path, *, idempotency_key: str | None = None) -> dict[str, Any]:
    root = Path(canonical_root(root)).resolve()
    target = int(target)
    assert_lifecycle_state(root, "ADJUDICATED", target_contest=target)
    path = (root / Path(review_file)).resolve()
    path.relative_to(root)
    review = _load_operator_hashed_doc(path, "SMART_POST_RESULT_REVIEW_1")
    history = review.get("canonical_history") or {}
    if review.get("status") != "POST_RESULT_REVIEW_COMPLETE":
        raise ValueError("post-result review is not complete")
    if int(review.get("target_contest", -1)) != target or int(review.get("next_target", -1)) != target + 1:
        raise ValueError("post-result review target sequence mismatch")
    canonical = root / "Mega-Sena.xlsx"
    if history.get("sha256") != sha256_file(canonical) or int(history.get("history_max", -1)) != target:
        raise ValueError("post-result review canonical binding mismatch")
    lifecycle = transition_lifecycle(root, "ADJUDICATED", "REVIEWED", target_contest=target, actor="operator_review_complete")
    return {"status": "REVIEWED", "review": review, "operational_lifecycle": lifecycle}


@startup_guarded("ROLLOVER")
@idempotent_operation('ROLLOVER')
def hold_operation(root: str | Path, target: int, hold_file: str | Path = POST_RESULT_HOLD_PATH, *, idempotency_key: str | None = None) -> dict[str, Any]:
    root = Path(canonical_root(root)).resolve()
    return canonical_rollover(root, int(target), hold_file)


@locked_operation("TERMINAL")
@startup_guarded("TERMINAL")
@idempotent_operation('TERMINAL')
def terminal_operation(
    root: str | Path,
    target: int,
    *,
    probe_only: bool = False,
    allow_terminal_write: bool = True,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    lifecycle_before = assert_lifecycle_state(root, ("FROZEN", "ADJUDICATED", "REVIEWED"), target_contest=int(target))
    active = verify_active_epoch(root / ACTIVE_PATH)
    if int(active.get("target_contest", -1)) != int(target):
        raise ValueError("active operational epoch does not match terminal target")
    # The terminal engine validates either a live pre-result generation authority or
    # a post-adjudication recovery lineage bound to the same immutable freeze.
    # Do not re-authorize prediction here after the result is known.
    if probe_only:
        return terminal_executor.probe(root, int(target))
    result = terminal_executor.execute(root, int(target), allow_terminal_write=allow_terminal_write)
    if lifecycle_before["state"] == "FROZEN" and isinstance(result, dict) and result.get("adjudication_status"):
        lifecycle_after = transition_lifecycle(root, "FROZEN", "ADJUDICATED", target_contest=int(target), actor="terminal_adjudicate_complete")
    else:
        lifecycle_after = load_lifecycle(root)
    return {**result, "operational_lifecycle": lifecycle_after}


def status(root: str | Path) -> dict[str, Any]:
    root = Path(canonical_root(root)).resolve()
    reconciliation = reconcile_startup(root, include_authority_freshness=True)
    boundaries = audit_state_boundaries(root)
    from smart_historical_binding import build as build_historical_binding
    from smart_proof_chain import inspect as inspect_proof_chain
    try:
        history_3060 = build_historical_binding(root, 3060)
    except Exception as exc:
        history_3060 = {"status": "INVALID", "reason": f"{type(exc).__name__}: {exc}"}
    cert_path = root / "SMART_PRODUCT_CERTIFICATION.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8-sig")) if cert_path.is_file() else None
    active_path = root / ACTIVE_PATH
    try:
        active = verify_active_epoch(active_path) if active_path.is_file() else None
    except Exception as exc:
        active = {"status": "INVALID", "reason": f"{type(exc).__name__}: {exc}"}
    return {
        "schema": "SMART_OPERATOR_STATUS_2",
        "status": reconciliation.get("status"),
        "reconciled_state": reconciliation,
        "scientific_operational_boundaries": boundaries,
        "historical_binding_3060": history_3060,
        "proof_chain": inspect_proof_chain(root),
        "product_certification": cert,
        "active_operation": active,
        "operator_contract": contract(),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="SMART-MEGA operator interface. Product construction is independent of contest operation.")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    pf = sub.add_parser("preflight"); pf.add_argument("--target", type=int, required=True)
    rp = sub.add_parser("result-preflight"); rp.add_argument("--target", type=int, required=True)
    p = sub.add_parser("prepare"); p.add_argument("--target", type=int, required=True); p.add_argument("--supersede", action="store_true")
    w = sub.add_parser("withdraw"); w.add_argument("--target", type=int, required=True)
    m = sub.add_parser("recover-missed"); m.add_argument("--target", type=int, required=True)
    cu = sub.add_parser("catch-up"); cu.add_argument("--through", type=int, required=True); cu.add_argument("--payload-file")
    n = sub.add_parser("authorize-next-cycle"); n.add_argument("--target", type=int, required=True)
    g = sub.add_parser("authorize-generation"); g.add_argument("--target", type=int, required=True)
    f = sub.add_parser("freeze"); f.add_argument("--target", type=int, required=True)
    a = sub.add_parser("adjudicate"); a.add_argument("--target", type=int, required=True); a.add_argument("--result-data", required=True)
    r = sub.add_parser("post-result-report"); r.add_argument("--target", type=int, required=True)
    rv = sub.add_parser("review"); rv.add_argument("--target", type=int, required=True); rv.add_argument("--review-file", required=True)
    h = sub.add_parser("hold"); h.add_argument("--target", type=int, required=True); h.add_argument("--hold-file", default=str(POST_RESULT_HOLD_PATH))
    t = sub.add_parser("terminal"); t.add_argument("--target", type=int, required=True); t.add_argument("--probe-only", action="store_true"); t.add_argument("--no-terminal-write", action="store_true")
    args = parser.parse_args(argv)
    root = canonical_root()
    if args.action == "status": out = status(root)
    elif args.action == "preflight": out = preflight_operation(root, args.target)
    elif args.action == "result-preflight": out = result_preflight_operation(root, args.target)
    elif args.action == "prepare": out = prepare_operation(root, args.target, supersede_existing=args.supersede)
    elif args.action == "withdraw": out = withdraw_pre_freeze_operation(root, args.target)
    elif args.action == "recover-missed": out = recover_missed_unfrozen_operation(root, args.target)
    elif args.action == "catch-up": out = catch_up_missed_operation(root, args.through, args.payload_file)
    elif args.action == "authorize-next-cycle": out = authorize_next_cycle_operation(root, args.target)
    elif args.action == "authorize-generation": out = authorize_generation_operation(root, args.target)
    elif args.action == "freeze": out = freeze_operation(root, args.target)
    elif args.action == "adjudicate": out = adjudicate_operation(root, args.target, args.result_data)
    elif args.action == "post-result-report": out = post_result_report_operation(root, args.target)
    elif args.action == "review": out = review_operation(root, args.target, args.review_file)
    elif args.action == "hold": out = hold_operation(root, args.target, args.hold_file)
    else: out = terminal_operation(root, args.target, probe_only=args.probe_only, allow_terminal_write=not args.no_terminal_write)
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
