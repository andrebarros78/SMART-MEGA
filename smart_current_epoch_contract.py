from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from smart_learning_epoch_reset import verify_active_epoch
from smart_prospective_authority_lock import adjudicated_lock_evidence, verify_lock

SCHEMA = "SMART_CURRENT_EPOCH_CONTRACT_2"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root).resolve()
    active_path = root / "SMART_ACTIVE_EPOCH.json"
    if not active_path.is_file():
        raise ValueError("SMART_ACTIVE_EPOCH.json missing; current authority cannot be inferred from legacy artifacts")
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
    else:
        raise ValueError(f"unsupported active epoch status: {status}")
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
        "rollover_required": parallel_experiment_adjudicated,
        "scientific_claim_status": "UNPROVEN_PROSPECTIVE",
        "terminal_authority": False,
    }
