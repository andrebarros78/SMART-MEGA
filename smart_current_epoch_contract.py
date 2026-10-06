from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from smart_learning_epoch_reset import verify_active_epoch
from smart_operational_lifecycle import load_lifecycle
from smart_prospective_authority_lock import adjudicated_lock_evidence, verify_lock

SCHEMA = "SMART_CURRENT_EPOCH_CONTRACT_2"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()



RECOVERY_PROOF_SCHEMA = "SMART_FULL_PROCESS_RECOVERY_PROOF_1"


def _sha_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _project_path(root: Path, value: str, *, label: str) -> Path:
    raw = Path(value)
    candidate = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} escapes project root") from exc
    return candidate


def _read_self_hashed(path: Path, *, schema: str, label: str, expected_status: str = "PASS") -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"{label} cannot be parsed") from exc
    if not isinstance(obj, dict) or obj.get("schema") != schema or obj.get("status") != expected_status:
        raise ValueError(f"{label} schema/status invalid")
    observed = obj.get("sha256")
    canonical = dict(obj)
    canonical.pop("sha256", None)
    if not isinstance(observed, str) or len(observed) != 64 or observed.lower() != _sha_json(canonical):
        raise ValueError(f"{label} self-hash invalid")
    return obj


def _verify_ref(root: Path, ref: Any, *, label: str, expected_file: str | None = None,
                expected_sha256: str | None = None) -> tuple[Path, str]:
    if not isinstance(ref, dict) or not isinstance(ref.get("file"), str) or not isinstance(ref.get("sha256"), str):
        raise ValueError(f"{label} reference invalid")
    path = _project_path(root, ref["file"], label=label)
    if not path.is_file():
        raise ValueError(f"{label} file missing")
    observed = _sha(path)
    if observed.lower() != str(ref["sha256"]).lower():
        raise ValueError(f"{label} file hash mismatch")
    if expected_file is not None:
        expected = _project_path(root, expected_file, label=f"{label} expected file")
        if path != expected:
            raise ValueError(f"{label} file binding mismatch")
    if expected_sha256 is not None and observed.lower() != str(expected_sha256).lower():
        raise ValueError(f"{label} expected hash mismatch")
    return path, observed


def validate_generation_proof(root: str | Path, active: dict[str, Any], freeze_doc: dict[str, Any],
                              freeze_sha256: str, *, historical_only: bool = False) -> dict[str, Any]:
    root = Path(root).resolve()
    state_paths = active.get("state_paths")
    if not isinstance(state_paths, dict) or not isinstance(state_paths.get("ledger"), str):
        raise ValueError("FROZEN epoch state_paths/ledger missing")
    epoch_dir = _project_path(root, state_paths["ledger"], label="active epoch ledger").parent
    original = epoch_dir / "FULL_PROCESS_PROOF.json"
    if original.is_file():
        proof = _read_self_hashed(original, schema="SMART_FULL_PROCESS_PROOF_2", label="full-process proof")
        checks = proof.get("trace_checks")
        if proof.get("epoch_id") != active.get("epoch_id"):
            raise ValueError("full-process proof epoch mismatch")
        if int(proof.get("target_contest", -1)) != int(active["target_contest"]) or int(proof.get("cutoff_contest", -1)) != int(active["cutoff_contest"]):
            raise ValueError("full-process proof target/cutoff mismatch")
        if proof.get("freeze_sha256") != freeze_sha256:
            raise ValueError("full-process proof freeze mismatch")
        if proof.get("result_used") is not False or not isinstance(checks, dict) or not checks or not all(v is True for v in checks.values()):
            raise ValueError("full-process proof is not a complete pre-result causal proof")
        return {"valid": True, "mode": "ORIGINAL_FULL_PROCESS_PROOF", "file": str(original.relative_to(root)).replace("\\", "/"), "sha256": _sha(original)}

    recovery = epoch_dir / "FULL_PROCESS_RECOVERY_PROOF.json"
    if not recovery.is_file():
        raise ValueError("FROZEN current-engineering epoch missing generation proof")
    proof = _read_self_hashed(recovery, schema=RECOVERY_PROOF_SCHEMA, label="full-process recovery proof")
    if proof.get("recovery_kind") != "POST_FREEZE_EVIDENCE_RECOVERY" or proof.get("recovery_reason") != "ORIGINAL_FULL_PROCESS_PROOF_MISSING":
        raise ValueError("full-process recovery proof recovery semantics invalid")
    if proof.get("prediction_content_mutated") is not False or proof.get("retroactive_rewrite") is not False or proof.get("result_used") is not False:
        raise ValueError("full-process recovery proof violates pre-result immutability")
    if proof.get("epoch_id") != active.get("epoch_id") or proof.get("active_epoch_sha256") != active.get("sha256"):
        raise ValueError("full-process recovery proof epoch binding mismatch")
    if int(proof.get("target_contest", -1)) != int(active["target_contest"]) or int(proof.get("cutoff_contest", -1)) != int(active["cutoff_contest"]):
        raise ValueError("full-process recovery proof target/cutoff mismatch")
    freeze_ref = active.get("freeze_authority") or {}
    _verify_ref(root, proof.get("freeze"), label="recovery freeze", expected_file=str(freeze_ref.get("file", "")), expected_sha256=freeze_sha256)
    _verify_ref(root, proof.get("immutable_data"), label="recovery immutable data", expected_file=str(active["data_file"]), expected_sha256=str(active["data_sha256"]))
    state_ref = active.get("learning_state_authority") or {}
    _verify_ref(root, proof.get("signal_state"), label="recovery signal state", expected_file=str(state_ref.get("file", "")), expected_sha256=str(state_ref.get("sha256", "")))
    prospective = active.get("prospective_registration")
    if not isinstance(prospective, dict) or prospective.get("result_used") is not False:
        raise ValueError("full-process recovery proof prospective registration invalid")
    for key, label in (("probability_ledger", "probability ledger"), ("frontier_report", "frontier report"), ("frontier_freeze", "frontier freeze")):
        source_key = {"probability_ledger": "probability_ledger_file", "frontier_report": "frontier_report_file", "frontier_freeze": "frontier_freeze_file"}[key]
        sha_key = source_key.replace("_file", "_sha256")
        _verify_ref(root, proof.get(key), label=f"recovery {label}", expected_file=str(prospective[source_key]), expected_sha256=str(prospective[sha_key]))
    for key, phase in (("pre_freeze_total_integration", "PRE_FREEZE"), ("post_freeze_total_integration", "POST_FREEZE")):
        gate_path, _ = _verify_ref(root, proof.get(key), label=f"recovery {phase} integration")
        gate = json.loads(gate_path.read_text(encoding="utf-8-sig"))
        if gate.get("status") != "PASS" or gate.get("phase") != phase or proof[key].get("status") != "PASS" or proof[key].get("phase") != phase:
            raise ValueError(f"recovery {phase} integration proof invalid")
    cert_path, _ = _verify_ref(root, proof.get("product_certification_snapshot"), label="recovery product certification snapshot")
    cert = json.loads(cert_path.read_text(encoding="utf-8-sig"))
    cert_canonical = dict(cert); cert_observed = cert_canonical.pop("sha256", None)
    if cert_observed != active.get("product_certification_sha256") or cert_observed != proof["product_certification_snapshot"].get("internal_sha256") or cert_observed != _sha_json(cert_canonical):
        raise ValueError("recovery product certification semantic hash mismatch")
    gi_ref = freeze_doc.get("global_integrity_proof") or {}
    _verify_ref(root, proof.get("global_integrity_snapshot"), label="recovery global integrity snapshot", expected_sha256=str(gi_ref.get("sha256", "")))
    ledger_path = _project_path(root, state_paths["ledger"], label="recovery ledger")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8-sig"))
    target = int(active["target_contest"])
    target_adjudications = [ev for ev in ledger.get("events", []) if isinstance(ev, dict) and ev.get("event_type") == "ADJUDICATION" and int(ev.get("target_contest", -1)) == target]
    if len(target_adjudications) > 1:
        raise ValueError("full-process recovery proof sees multiple target adjudications")
    if target_adjudications:
        adjudication = target_adjudications[0]
        actual = [int(x) for x in adjudication.get("actual_numbers", [])]
        if adjudication.get("freeze_sha256") != freeze_sha256 or adjudication.get("retroactive_rewrite") is not False:
            raise ValueError("post-adjudication historical proof is not bound to immutable freeze")
        if len(actual) != 6 or len(set(actual)) != 6 or any(x < 1 or x > 60 for x in actual):
            raise ValueError("post-adjudication historical proof has invalid official numbers")
        if historical_only is not True:
            raise ValueError("full-process recovery proof cannot authorize an already-adjudicated target")
    checks = proof.get("checks")
    if not isinstance(checks, dict) or not checks:
        raise ValueError("full-process recovery proof checks missing")
    required_true = [k for k in checks if k not in {"prediction_content_mutated", "retroactive_rewrite", "result_used"}]
    if not all(checks.get(k) is True for k in required_true):
        raise ValueError("full-process recovery proof contains failed checks")
    if checks.get("prediction_content_mutated") is not False or checks.get("retroactive_rewrite") is not False or checks.get("result_used") is not False:
        raise ValueError("full-process recovery proof mutation/result checks invalid")
    return {"valid": True, "mode": "RECOVERED_FULL_PROCESS_PROOF", "file": str(recovery.relative_to(root)).replace("\\", "/"), "sha256": _sha(recovery)}


HOLD_SCHEMA = "SMART_NEXT_CYCLE_HOLD_1"
REVIEW_SCHEMA = "SMART_POST_RESULT_REVIEW_1"
HOLD_STATUS = "AWAITING_OPERATOR_APPLY_OR_GENERATE"


def _resolve_post_result_hold(root: Path) -> dict[str, Any] | None:
    hold_path = root / "SMART_NEXT_CYCLE_HOLD.json"
    if not hold_path.is_file():
        return None
    try:
        hold = json.loads(hold_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError("post-result hold cannot be parsed") from exc
    if not isinstance(hold, dict) or hold.get("schema") != HOLD_SCHEMA or hold.get("status") != HOLD_STATUS:
        raise ValueError("post-result hold schema/status invalid")
    observed = hold.get("sha256")
    canonical_hold = dict(hold); canonical_hold.pop("sha256", None)
    if not isinstance(observed, str) or observed.lower() != _sha_json(canonical_hold):
        raise ValueError("post-result hold self-hash invalid")
    completed = int(hold.get("completed_contest", -1))
    target = int(hold.get("next_target", -1))
    if completed <= 0 or target != completed + 1:
        raise ValueError("post-result hold contest sequence invalid")
    if hold.get("automatic_prepare_forbidden") is not True or hold.get("prepare_allowed") is not False or hold.get("generation_allowed") is not False or hold.get("operator_command_required") is not True:
        raise ValueError("post-result hold authority flags invalid")
    if hold.get("required_command_semantics") != "USER_EXPLICIT_APPLY_OR_GENERATE":
        raise ValueError("post-result hold command semantics invalid")
    canonical = root / "Mega-Sena.xlsx"
    if not canonical.is_file():
        raise ValueError("post-result hold canonical history missing")
    canonical_sha = _sha(canonical)
    if canonical_sha != hold.get("canonical_sha256_at_review"):
        raise ValueError("post-result hold canonical history hash mismatch")
    review_file = hold.get("review_file")
    if not isinstance(review_file, str):
        raise ValueError("post-result hold review file missing")
    review_path = _project_path(root, review_file, label="post-result review")
    if not review_path.is_file() or _sha(review_path) != hold.get("review_file_sha256"):
        raise ValueError("post-result hold review file hash mismatch")
    try:
        review = json.loads(review_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError("post-result review cannot be parsed") from exc
    if not isinstance(review, dict) or review.get("schema") != REVIEW_SCHEMA or review.get("status") != "POST_RESULT_REVIEW_COMPLETE":
        raise ValueError("post-result review schema/status invalid")
    review_observed = review.get("sha256")
    review_canonical = dict(review); review_canonical.pop("sha256", None)
    if not isinstance(review_observed, str) or review_observed.lower() != _sha_json(review_canonical):
        raise ValueError("post-result review self-hash invalid")
    if review_observed != hold.get("review_sha256") or int(review.get("target_contest", -1)) != completed or int(review.get("next_target", -1)) != target:
        raise ValueError("post-result hold/review binding mismatch")
    if review.get("stop_required") is not True or review.get("terminal_state") != HOLD_STATUS:
        raise ValueError("post-result review does not require lifecycle hold")
    authority_present = (root / "SMART_NEXT_CYCLE_AUTHORITY.json").is_file()
    return {
        "schema": SCHEMA,
        "epoch_id": None,
        "status": "POST_RESULT_HOLD",
        "post_result_hold": True,
        "active_epoch_sha256": None,
        "authority_mode": "POST_RESULT_HOLD",
        "current_engineering_role": "POST_RESULT_ANALYSIS_HOLD",
        "first_possible_authoritative_target_for_current_engineering": target,
        "data_file": "Mega-Sena.xlsx",
        "data_sha256": canonical_sha,
        "cutoff_contest": completed,
        "target_contest": target,
        "result_used": False,
        "freeze_authority_present": False,
        "freeze_file": None,
        "freeze_sha256": None,
        "top6": None,
        "freeze_origin": None,
        "scientific_adjudication_authority": False,
        "current_engineering_generation_authority": False,
        "parallel_locked_experiment": None,
        "parallel_attempts_must_be_counted_separately": False,
        "parallel_experiment_adjudicated": False,
        "post_adjudication": False,
        "historical_pre_result_authority_preserved": False,
        "historical_generation_proof_valid": False,
        "rollover_required": False,
        "generation_proof_valid": False,
        "generation_proof_mode": None,
        "generation_proof_file": None,
        "generation_proof_sha256": None,
        "scientific_claim_status": "UNPROVEN_PROSPECTIVE",
        "terminal_authority": False,
        "prepare_allowed": False,
        "generation_allowed": False,
        "next_cycle_authority_present": authority_present,
        "operator_prepare_authorized": False,
        "next_cycle_authority_sha256": None,
        "operator_command_required": True,
        "required_command_semantics": "USER_EXPLICIT_APPLY_OR_GENERATE",
        "post_result_review_file": review_file,
        "post_result_review_sha256": review_observed,
        "post_result_hold_file": hold_path.name,
        "post_result_hold_sha256": observed,
    }


def _resolve_authorized_cycle(root: Path, lifecycle: dict[str, Any]) -> dict[str, Any]:
    if (root / "SMART_ACTIVE_EPOCH.json").exists():
        raise ValueError("lifecycle AUTHORIZED cannot contain an active operational epoch")
    hold = _resolve_post_result_hold(root)
    if hold is None:
        raise ValueError("lifecycle AUTHORIZED requires valid post-result hold evidence")
    target = hold["target_contest"]
    completed = hold["cutoff_contest"]
    if lifecycle.get("target_contest") != target or lifecycle.get("completed_contest") != completed:
        raise ValueError("lifecycle AUTHORIZED hold target/cutoff binding mismatch")
    authority_path = root / "SMART_NEXT_CYCLE_AUTHORITY.json"
    authority = _read_self_hashed(
        authority_path, schema="SMART_NEXT_CYCLE_AUTHORITY_1",
        label="next-cycle authority", expected_status="AUTHORIZED",
    )
    if authority.get("consumed") is not False or authority.get("authorized_by") != "USER_EXPLICIT_APPLY_OR_GENERATE":
        raise ValueError("next-cycle authority requires unconsumed explicit user authorization")
    for field, expected in (("target_contest", target), ("completed_contest", completed)):
        if type(authority.get(field)) is not int or authority[field] != expected:
            raise ValueError(f"next-cycle authority {field} binding mismatch")
    for field in ("prepared_epoch_id", "reservation_transaction_id", "consumption_transaction_id"):
        if authority.get(field) is not None:
            raise ValueError("next-cycle authority already prepared, reserved or consumed")
    review_path = _project_path(root, hold["post_result_review_file"], label="post-result review")
    bindings = {
        "review_file": hold["post_result_review_file"],
        "review_file_sha256": _sha(review_path),
        "review_sha256": hold["post_result_review_sha256"],
        "canonical_sha256": hold["data_sha256"],
    }
    if any(authority.get(field) != expected for field, expected in bindings.items()):
        raise ValueError("next-cycle authority history/review binding mismatch")
    return {
        **hold,
        "lifecycle_state": "AUTHORIZED",
        "lifecycle_revision": lifecycle["revision"],
        "lifecycle_sha256": lifecycle["sha256"],
        "operator_prepare_authorized": True,
        "next_cycle_authority_sha256": authority["sha256"],
    }


def resolve(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root).resolve()
    lifecycle = load_lifecycle(root)
    if lifecycle["state"] == "AUTHORIZED":
        return _resolve_authorized_cycle(root, lifecycle)
    if lifecycle["state"] == "HOLD":
        hold = _resolve_post_result_hold(root)
        if hold is None:
            raise ValueError("lifecycle HOLD requires valid post-result hold evidence")
        return {**hold, "lifecycle_state": "HOLD", "lifecycle_revision": lifecycle["revision"], "lifecycle_sha256": lifecycle["sha256"]}
    active_path = root / "SMART_ACTIVE_EPOCH.json"
    if not active_path.is_file():
        raise ValueError(f"lifecycle state {lifecycle['state']} requires an active operational epoch")
    active = verify_active_epoch(active_path)
    data_path = (root / active["data_file"]).resolve()
    if not data_path.is_file() or _sha(data_path) != active["data_sha256"]:
        raise ValueError("active epoch canonical data hash mismatch")
    status = active["status"]
    parallel_locked_experiment = active.get("parallel_locked_experiment")
    parallel_attempts_must_be_counted_separately = bool(active.get("parallel_attempts_must_be_counted_separately"))
    if parallel_locked_experiment is not None:
        if not isinstance(parallel_locked_experiment, dict):
            raise ValueError("parallel locked experiment must be an object")
        lock_file = active.get("prospective_authority_lock_file")
        lock_sha = active.get("prospective_authority_lock_sha256")
        if not isinstance(lock_file, str) or not isinstance(lock_sha, str):
            raise ValueError("parallel locked experiment authority lock missing")
        parallel_experiment_adjudicated = False
        try:
            lock = verify_lock(root / lock_file, root=root)
        except ValueError as exc:
            if "no longer matches live unresolved authority" not in str(exc):
                raise
            evidence = adjudicated_lock_evidence(root / lock_file, root=root)
            if evidence["lock_sha256"] != lock_sha:
                raise ValueError("adjudicated parallel authority lock hash mismatch")
            if evidence["freeze_sha256"] != parallel_locked_experiment.get("freeze_sha256"):
                raise ValueError("adjudicated parallel freeze differs from active epoch")
            if int(evidence["target_contest"]) != int(active["target_contest"]):
                raise ValueError("adjudicated parallel target differs from active target")
            parallel_experiment_adjudicated = True
            lock = verify_lock(root / lock_file, root=None)
        if lock.get("sha256") != lock_sha:
            raise ValueError("parallel authority lock hash mismatch")
        auth = lock["experiment_authority"]
        if auth.get("freeze_sha256") != parallel_locked_experiment.get("freeze_sha256"):
            raise ValueError("parallel locked experiment hash differs from authority lock")
        if int(auth.get("target_contest", -1)) != int(active["target_contest"]):
            raise ValueError("parallel locked experiment target differs from active target")
        if not parallel_attempts_must_be_counted_separately:
            raise ValueError("parallel locked experiment requires separate-attempt accounting")
    parallel_experiment_adjudicated = locals().get("parallel_experiment_adjudicated", False)
    freeze_authority = active.get("freeze_authority")
    freeze_file = None
    freeze_sha = None
    top6 = None
    scientific_adjudication_authority = False
    current_engineering_generation_authority = False
    freeze_origin = None
    post_adjudication = False
    historical_generation_proof_valid = False
    if status == "RESET_READY":
        if freeze_authority is not None or active.get("result_used") is not False:
            raise ValueError("RESET_READY epoch must have no freeze authority and no result use")
    elif status == "FROZEN":
        if not isinstance(freeze_authority, dict):
            raise ValueError("FROZEN epoch missing freeze authority")
        freeze_file = str(freeze_authority["file"])
        fp = (root / freeze_file).resolve()
        if not fp.is_file():
            raise ValueError("current freeze authority file missing")
        freeze_sha = _sha(fp)
        if freeze_sha != freeze_authority.get("sha256"):
            raise ValueError("current freeze authority hash mismatch")
        freeze_doc = json.loads(fp.read_text(encoding="utf-8"))
        if int(freeze_doc.get("target_contest", -1)) != int(active["target_contest"]):
            raise ValueError("current freeze target mismatch")
        if int(freeze_doc.get("cutoff_contest", -1)) != int(active["cutoff_contest"]):
            raise ValueError("current freeze cutoff mismatch")
        top6 = freeze_doc.get("governed_challenger_top6") or freeze_doc.get("challenger", {}).get("top6") or freeze_doc.get("champion", {}).get("top6")
        scientific_adjudication_authority = bool(freeze_authority.get("scientific_adjudication_authority", True))
        current_engineering_generation_authority = bool(freeze_authority.get("current_engineering_generation_authority", True))
        freeze_origin = freeze_authority.get("origin", "CURRENT_ENGINEERING_EPOCH")
        if active.get("authority_mode") == "CARRY_FORWARD_UNRESOLVED_PROSPECTIVE":
            if not scientific_adjudication_authority or current_engineering_generation_authority:
                raise ValueError("carry-forward freeze authority semantics invalid")
            if active.get("current_engineering_role") != "SHADOW_ONLY_FOR_LOCKED_TARGET":
                raise ValueError("carry-forward epoch must keep current engineering shadow-only")
            lock_file = active.get("prospective_authority_lock_file")
            lock_sha = active.get("prospective_authority_lock_sha256")
            if not isinstance(lock_file, str) or not isinstance(lock_sha, str):
                raise ValueError("carry-forward epoch authority lock missing")
            lock = verify_lock(root / lock_file, root=root)
            if lock.get("sha256") != lock_sha:
                raise ValueError("carry-forward epoch authority lock hash mismatch")
            auth = lock["experiment_authority"]
            if auth.get("freeze_sha256") != freeze_sha or int(auth.get("target_contest", -1)) != int(active["target_contest"]):
                raise ValueError("carry-forward epoch differs from authority lock")
        ledger_path = _project_path(root, str(active["state_paths"]["ledger"]), label="active epoch ledger")
        ledger_doc = json.loads(ledger_path.read_text(encoding="utf-8-sig"))
        target_adjudications = [ev for ev in ledger_doc.get("events", []) if isinstance(ev, dict) and ev.get("event_type") == "ADJUDICATION" and int(ev.get("target_contest", -1)) == int(active["target_contest"])]
        if len(target_adjudications) > 1:
            raise ValueError("active epoch contains multiple target adjudications")
        post_adjudication = len(target_adjudications) == 1
        if post_adjudication:
            adjudication = target_adjudications[0]
            actual = [int(x) for x in adjudication.get("actual_numbers", [])]
            if adjudication.get("freeze_sha256") != freeze_sha or adjudication.get("retroactive_rewrite") is not False:
                raise ValueError("active post-adjudication state is not bound to immutable freeze")
            if len(actual) != 6 or len(set(actual)) != 6 or any(x < 1 or x > 60 for x in actual):
                raise ValueError("active post-adjudication official numbers invalid")
            current_engineering_generation_authority = False
            scientific_adjudication_authority = False
            historical = validate_generation_proof(root, active, freeze_doc, str(freeze_sha), historical_only=True)
            historical_generation_proof_valid = historical.get("valid") is True
            generation_proof = {**historical, "valid": False, "mode": "POST_ADJUDICATION_HISTORICAL_" + str(historical.get("mode"))}
        else:
            generation_proof = ({"valid": True, "mode": "CARRY_FORWARD_AUTHORITY_LOCK", "file": str(active.get("prospective_authority_lock_file")), "sha256": str(active.get("prospective_authority_lock_sha256"))}
                                if current_engineering_generation_authority is False
                                else validate_generation_proof(root, active, freeze_doc, str(freeze_sha)))
    else:
        raise ValueError(f"unsupported active epoch status: {status}")
    generation_proof = locals().get("generation_proof")
    return {
        "schema": SCHEMA,
        "epoch_id": active["epoch_id"],
        "status": status,
        "active_epoch_sha256": active["sha256"],
        "authority_mode": ("POST_ADJUDICATION_ROLLOVER_PENDING" if parallel_experiment_adjudicated else active.get("authority_mode", "LEGACY_UNSPECIFIED")),
        "current_engineering_role": active.get("current_engineering_role", "AUTHORITATIVE_CURRENT_EPOCH"),
        "first_possible_authoritative_target_for_current_engineering": active.get("first_possible_authoritative_target_for_current_engineering", active["target_contest"]),
        "data_file": active["data_file"],
        "data_sha256": active["data_sha256"],
        "cutoff_contest": int(active["cutoff_contest"]),
        "target_contest": int(active["target_contest"]),
        "result_used": bool(active.get("result_used")),
        "freeze_authority_present": freeze_authority is not None,
        "freeze_file": freeze_file,
        "freeze_sha256": freeze_sha,
        "top6": top6,
        "freeze_origin": freeze_origin,
        "scientific_adjudication_authority": scientific_adjudication_authority,
        "current_engineering_generation_authority": current_engineering_generation_authority,
        "parallel_locked_experiment": parallel_locked_experiment,
        "parallel_attempts_must_be_counted_separately": parallel_attempts_must_be_counted_separately,
        "parallel_experiment_adjudicated": parallel_experiment_adjudicated,
        "post_adjudication": post_adjudication,
        "historical_pre_result_authority_preserved": bool(post_adjudication and historical_generation_proof_valid),
        "historical_generation_proof_valid": bool(historical_generation_proof_valid),
        "rollover_required": bool(parallel_experiment_adjudicated or post_adjudication),
        "generation_proof_valid": bool(generation_proof and generation_proof.get("valid") is True) if status == "FROZEN" and not post_adjudication else False,
        "generation_proof_mode": generation_proof.get("mode") if generation_proof else None,
        "generation_proof_file": generation_proof.get("file") if generation_proof else None,
        "generation_proof_sha256": generation_proof.get("sha256") if generation_proof else None,
        "scientific_claim_status": "UNPROVEN_PROSPECTIVE",
        "terminal_authority": False,
    }
