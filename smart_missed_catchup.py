from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from smart_agent_runtime import sha256_file
from smart_canonical_history_advance import advance_completed_epoch
from smart_canonical_identity import canonical_root
from smart_champion_challenger import load_ledger
from smart_crash_safe_io import atomic_write_text
from smart_learning_epoch_reset import verify_active_epoch
from smart_official_result_ingest import ingest as ingest_official_result, validate_official_payload
from smart_operational_lifecycle import load_lifecycle, recover_to_hold
from smart_product_certification import DEFAULT_PATH as PRODUCT_CERT_PATH, verify_product_certification
from smart_rollover import archive_completed_epoch
from smart_storage_surfaces import evidence_path
from smart_terminal_executor import complete_adjudicated_sequence

RECOVERY_SCHEMA = "SMART_MISSED_TARGET_CATCHUP_1"
OFFICIAL_BATCH_SCHEMA = "SMART_OFFICIAL_RESULT_BATCH_1"
REVIEW_SCHEMA = "SMART_POST_RESULT_REVIEW_1"
HOLD_SCHEMA = "SMART_NEXT_CYCLE_HOLD_1"
HOLD_STATUS = "AWAITING_OPERATOR_APPLY_OR_GENERATE"


def _sha_json(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _self_hashed(payload: dict[str, Any]) -> dict[str, Any]:
    doc = dict(payload)
    doc.pop("sha256", None)
    doc["sha256"] = _sha_json(doc)
    return doc


def _write_create_only(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        raise FileExistsError(path)
    doc = _self_hashed(payload)
    tmp = path.with_suffix(path.suffix + ".tmp")
    atomic_write_text(tmp, json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    if path.exists():
        tmp.unlink(missing_ok=True)
        raise FileExistsError(path)
    os.replace(tmp, path)
    return doc


def _read_hashed(path: Path, schema: str) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict) or obj.get("schema") != schema:
        raise ValueError(f"unexpected schema: {path.name}")
    observed = obj.get("sha256")
    body = dict(obj); body.pop("sha256", None)
    if not isinstance(observed, str) or observed != _sha_json(body):
        raise ValueError(f"self-hash mismatch: {path.name}")
    return obj


def _replace_hashed(path: Path, payload: dict[str, Any], schema: str) -> dict[str, Any]:
    previous = _read_hashed(path, schema) if path.exists() else None
    doc = dict(payload)
    doc["revision"] = int(previous.get("revision", 0)) + 1 if previous else 1
    doc["previous_document_sha256"] = previous.get("sha256") if previous else None
    doc = _self_hashed(doc)
    tmp = path.with_suffix(path.suffix + ".tmp")
    atomic_write_text(tmp, json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    if previous is not None:
        latest = _read_hashed(path, schema)
        if latest.get("sha256") != previous.get("sha256"):
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"CAS conflict: {path.name}")
    os.replace(tmp, path)
    return doc


def _history(root: Path) -> dict[str, Any]:
    canonical = root / "Mega-Sena.xlsx"
    frame = pd.read_excel(canonical)
    if "Concurso" not in frame.columns:
        raise ValueError("canonical history lacks Concurso column")
    contests = pd.to_numeric(frame["Concurso"], errors="raise").astype(int).tolist()
    if not contests or contests != sorted(contests) or len(contests) != len(set(contests)):
        raise ValueError("canonical history must be strictly ordered and unique")
    if contests != list(range(contests[0], contests[-1] + 1)):
        raise ValueError("canonical history contains gaps")
    return {"max": contests[-1], "rows": len(contests), "sha256": sha256_file(canonical)}


def _assert_completed_active(root: Path, active: dict[str, Any], lifecycle: dict[str, Any]) -> int:
    target = int(active.get("target_contest", -1))
    if lifecycle.get("state") not in {"ADJUDICATED", "REVIEWED"}:
        raise ValueError("catch-up with an active epoch requires ADJUDICATED or REVIEWED lifecycle")
    if int(lifecycle.get("target_contest", -1)) != target:
        raise ValueError("active epoch/lifecycle target mismatch")
    ledger = root / str((active.get("state_paths") or {}).get("ledger") or "")
    events = load_ledger(ledger).get("events", [])
    count = sum(1 for ev in events if isinstance(ev, dict) and ev.get("event_type") == "ADJUDICATION" and int(ev.get("target_contest", -1)) == target)
    if count != 1:
        raise ValueError("catch-up requires exactly one adjudication for the active completed target")
    return target



def load_official_payload_batch(path: str | Path) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    batch_path = Path(path)
    if not batch_path.is_file():
        raise FileNotFoundError(batch_path)
    obj = json.loads(batch_path.read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict) or obj.get("schema") != OFFICIAL_BATCH_SCHEMA:
        raise ValueError("official result batch schema invalid")
    if obj.get("authority") != "CAIXA_LOTERIAS_OFFICIAL_API":
        raise ValueError("official result batch authority invalid")
    observed = obj.get("sha256")
    body = dict(obj); body.pop("sha256", None)
    if not isinstance(observed, str) or observed != _sha_json(body):
        raise ValueError("official result batch self-hash invalid")
    rows = obj.get("results")
    if not isinstance(rows, list) or not rows:
        raise ValueError("official result batch results missing")
    payloads: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("official result batch row invalid")
        target = int(row.get("numero", -1))
        validate_official_payload(row, target)
        expected_endpoint = f"https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/{target}"
        if row.get("endpoint") != expected_endpoint:
            raise ValueError(f"official result batch endpoint mismatch for target {target}")
        if target in payloads:
            raise ValueError("official result batch contains duplicate target")
        payloads[target] = row
    ordered = sorted(payloads)
    if ordered != list(range(ordered[0], ordered[-1] + 1)):
        raise ValueError("official result batch target sequence contains gaps")
    evidence = {
        "schema": OFFICIAL_BATCH_SCHEMA,
        "file": batch_path.name,
        "file_sha256": sha256_file(batch_path),
        "document_sha256": observed,
        "authority": obj["authority"],
        "retrieved_at_utc": obj.get("retrieved_at_utc"),
        "capture_transport": obj.get("capture_transport"),
        "targets": ordered,
    }
    return payloads, evidence

def _payload_for(payloads: dict[int, dict[str, Any]] | None, target: int) -> dict[str, Any] | None:
    if payloads is None:
        return None
    value = payloads.get(int(target))
    if value is None:
        value = payloads.get(str(int(target)))  # type: ignore[arg-type]
    if value is not None:
        validate_official_payload(value, target)
    return value


def catch_up_missed_results(
    root: str | Path,
    through_target: int,
    *,
    payloads: dict[int, dict[str, Any]] | None = None,
    payload_batch_evidence: dict[str, Any] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Advance only known official results across a gap and restore HOLD.

    No target in this path receives a prepared epoch, generation authority, freeze,
    or prospective attempt. The operation ends at HOLD for through_target + 1.
    """
    root = Path(canonical_root(root)).resolve()
    through_target = int(through_target)
    observed_now = now_utc or datetime.now(timezone.utc)
    if observed_now.tzinfo is None or observed_now.utcoffset() is None:
        raise ValueError("catch-up clock must be timezone-aware")
    certification = verify_product_certification(root / PRODUCT_CERT_PATH, root=root, require_current_code=True)
    lifecycle_before = load_lifecycle(root)
    if lifecycle_before.get("state") not in {"ADJUDICATED", "REVIEWED", "HOLD"}:
        raise ValueError("missed-result catch-up requires ADJUDICATED, REVIEWED, or HOLD lifecycle")

    canonical = root / "Mega-Sena.xlsx"
    active_path = root / "SMART_ACTIVE_EPOCH.json"
    hold_path = root / "SMART_NEXT_CYCLE_HOLD.json"
    lifecycle_path = root / "SMART_OPERATIONAL_LIFECYCLE.json"
    initial_canonical = canonical.read_bytes()
    initial_active = active_path.read_bytes() if active_path.is_file() else None
    initial_hold = hold_path.read_bytes() if hold_path.is_file() else None
    initial_lifecycle = lifecycle_path.read_bytes()

    active = verify_active_epoch(active_path) if active_path.is_file() else None
    archive = None
    prior_advance = None
    completed_active_target: int | None = None
    history_advance_path: Path | None = None
    history_advance_preexisting = False
    if active is not None:
        completed_active_target = _assert_completed_active(root, active, lifecycle_before)
        history_advance_path = root / f"SMART_CANONICAL_HISTORY_ADVANCE_{completed_active_target}.json"
        history_advance_preexisting = history_advance_path.exists()
        # An adjudication is not a completed epoch until its official-result
        # learning update and sequential proof have been recorded.
        complete_adjudicated_sequence(root, completed_active_target)
        prior_advance = advance_completed_epoch(root, active)
    elif lifecycle_before.get("state") != "HOLD":
        raise ValueError("catch-up without active epoch requires lifecycle HOLD")

    history = _history(root)
    start_target = int(history["max"]) + 1
    if through_target < int(history["max"]):
        raise ValueError("catch-up through target cannot move canonical history backward")

    recovery_proofs: list[dict[str, Any]] = []
    previous_proof_sha: str | None = None
    created_paths: list[Path] = []
    created_dirs: list[Path] = []
    try:
        for target in range(start_target, through_target + 1):
            if any((root / "runtime" / "learning_epochs").glob(f"operator-{target}-*")):
                raise ValueError(f"catch-up refuses target {target}: operational epoch artifact exists")
            proof_path = root / f"SMART_MISSED_TARGET_RECOVERY_{target}.json"
            if proof_path.exists():
                raise FileExistsError(f"catch-up refuses existing recovery proof: {proof_path.name}")
            before = sha256_file(canonical)
            recovery_dir = evidence_path(root, "SMART_STATE_ARCHIVE", f"missed-catchup-{target}")
            recovery_dir_preexisting = recovery_dir.exists()
            recovery_dir.mkdir(parents=True, exist_ok=True)
            if not recovery_dir_preexisting:
                created_dirs.append(recovery_dir)
            backup = recovery_dir / f"Mega-Sena.before.{before}.xlsx"
            if not backup.exists():
                shutil.copy2(canonical, backup)
            if sha256_file(backup) != before:
                raise RuntimeError("catch-up canonical backup mismatch")
            through = recovery_dir / f"Mega-Sena_through_{target}.xlsx"
            official_proof = recovery_dir / f"SMART_OFFICIAL_RESULT_{target}_MISSED_CATCHUP.json"
            if through.exists() or official_proof.exists():
                raise FileExistsError(f"catch-up target {target} staged output exists")
            official = ingest_official_result(canonical, through, official_proof, target, payload=_payload_for(payloads, target))
            # Published official result is the post-draw authority for this non-predictive path.
            official_doc = _read_hashed(official_proof, "SMART_OFFICIAL_RESULT_INGEST_1")
            draw_date = datetime.strptime(str(official_doc["draw_date"]), "%d/%m/%Y").date()
            if draw_date > observed_now.astimezone(timezone.utc).date():
                raise ValueError("catch-up refuses an official result dated in the future")
            fd, raw = tempfile.mkstemp(prefix=f"Mega-Sena.catchup.{target}.", suffix=".tmp.xlsx", dir=root)
            os.close(fd)
            temp = Path(raw)
            try:
                shutil.copy2(through, temp)
                if sha256_file(temp) != official["output_sha256"]:
                    raise RuntimeError("catch-up staged canonical hash mismatch")
                os.replace(temp, canonical)
            finally:
                temp.unlink(missing_ok=True)
            after_history = _history(root)
            if int(after_history["max"]) != target:
                raise RuntimeError("catch-up canonical sequence postcondition failed")
            proof = _write_create_only(proof_path, {
                "schema": RECOVERY_SCHEMA,
                "status": "RECOVERED_OFFICIAL_RESULT_NO_PREDICTION",
                "target_contest": target,
                "previous_completed_target": target - 1,
                "recovered_utc": datetime.now(timezone.utc).isoformat(),
                "official_result": official["actual_numbers"],
                "official_result_proof": str(official_proof.relative_to(root)).replace("\\", "/"),
                "official_result_proof_sha256": sha256_file(official_proof),
                "official_result_batch": payload_batch_evidence,
                "canonical_sha256_before": before,
                "canonical_sha256_after": after_history["sha256"],
                "canonical_backup": str(backup.relative_to(root)).replace("\\", "/"),
                "previous_recovery_sha256": previous_proof_sha,
                "prediction_authority_created": False,
                "generation_authority_created": False,
                "freeze_authority_created": False,
                "prospective_attempt_counted": False,
                "result_used_for_prediction": False,
                "future_information_used_for_prior_predictions": False,
                "ready_for_next_target": target + 1,
            })
            created_paths.extend([proof_path, through, official_proof])
            previous_proof_sha = proof["sha256"]
            recovery_proofs.append({"file": proof_path.name, "sha256": proof["sha256"], "target_contest": target})

        final_history = _history(root)
        completed = int(final_history["max"])
        if completed != through_target:
            raise RuntimeError("catch-up final history does not equal requested through target")
        review_path = root / f"SMART_POST_RESULT_REVIEW_{completed}.json"
        if review_path.exists():
            review = _read_hashed(review_path, REVIEW_SCHEMA)
            if int(review.get("target_contest", -1)) != completed or (review.get("canonical_history") or {}).get("sha256") != final_history["sha256"]:
                raise ValueError("existing final review conflicts with catch-up result")
        else:
            review = _write_create_only(review_path, {
                "schema": REVIEW_SCHEMA,
                "status": "POST_RESULT_REVIEW_COMPLETE",
                "target_contest": completed,
                "next_target": completed + 1,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "source": f"MISSED_RESULT_CATCHUP_THROUGH_{completed}",
                "canonical_history": {"file": "Mega-Sena.xlsx", "sha256": final_history["sha256"], "history_max": completed, "row_count": final_history["rows"]},
                "recovery_chain": recovery_proofs,
                "learning_policy": {"automatic_weight_change": False, "requires_out_of_sample_validation": True, "future_information_used": False},
                "operator_next_action": "HOLD_OR_AUTHORIZE_NEXT_CYCLE",
                "stop_required": True,
                "terminal_state": HOLD_STATUS,
                "automatic_weight_change_performed": False,
                "statistical_adjustment_authorized": False,
                "result_used_for_prediction": False,
                "no_future_leakage": True,
                "reviewed_utc": datetime.now(timezone.utc).isoformat(),
                "parecer": "MISSED_RESULTS_RECONCILED; CANONICAL_ADVANCED; NO_RETROACTIVE_GENERATION",
            })
            created_paths.append(review_path)
        hold = _replace_hashed(hold_path, {
            "schema": HOLD_SCHEMA,
            "status": HOLD_STATUS,
            "completed_contest": completed,
            "next_target": completed + 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "review_file": review_path.name,
            "review_file_sha256": sha256_file(review_path),
            "review_sha256": review["sha256"],
            "canonical_sha256_at_review": final_history["sha256"],
            "automatic_prepare_forbidden": True,
            "prepare_allowed": False,
            "reason": "MISSED_RESULT_CATCHUP_COMPLETE_OPERATOR_REQUIRED",
            "generation_allowed": False,
            "operator_command_required": True,
            "required_command_semantics": "USER_EXPLICIT_APPLY_OR_GENERATE",
        }, HOLD_SCHEMA)
        if completed_active_target is not None:
            archive = archive_completed_epoch(root, completed_active_target)
        lifecycle = recover_to_hold(root, completed_contest=completed, evidence={
            "missed_result_catchup": {"start_target": start_target, "through_target": completed, "proofs": recovery_proofs, "product_certification_sha256": certification["sha256"], "official_result_batch": payload_batch_evidence},
            "post_result_review": {"file": review_path.name, "sha256": sha256_file(review_path)},
            "post_result_hold": {"file": hold_path.name, "sha256": hold["sha256"]},
            **({"rollover_archive": {"manifest": archive["archive_manifest"], "sha256": archive["archive_manifest_sha256"]}} if archive else {}),
        })
        return {
            "schema": "SMART_MISSED_RESULT_CATCHUP_OPERATION_1",
            "status": "CAUGHT_UP_TO_HOLD",
            "start_target": start_target,
            "through_target": completed,
            "next_target": completed + 1,
            "recovery_count": len(recovery_proofs),
            "recovery_proofs": recovery_proofs,
            "canonical_sha256": final_history["sha256"],
            "post_result_review": {"file": review_path.name, "sha256": review["sha256"]},
            "post_result_hold": {"file": hold_path.name, "sha256": hold["sha256"]},
            "operational_lifecycle": lifecycle,
            "prior_epoch_history_advance": prior_advance,
            "prior_epoch_archive": archive,
            "prediction_authority_created": False,
            "generation_authority_created": False,
            "retroactive_generation_performed": False,
        }
    except Exception:
        # Restore mutable operational authority surfaces to their exact pre-operation
        # bytes. Immutable archives may remain as non-authoritative evidence only.
        canonical.write_bytes(initial_canonical)
        if initial_active is None:
            active_path.unlink(missing_ok=True)
        else:
            active_path.write_bytes(initial_active)
        if initial_hold is None:
            hold_path.unlink(missing_ok=True)
        else:
            hold_path.write_bytes(initial_hold)
        lifecycle_path.write_bytes(initial_lifecycle)
        if history_advance_path is not None and not history_advance_preexisting:
            history_advance_path.unlink(missing_ok=True)
        for path in reversed(created_paths):
            path.unlink(missing_ok=True)
        for directory in reversed(created_dirs):
            if directory.exists():
                shutil.rmtree(directory)
        raise
