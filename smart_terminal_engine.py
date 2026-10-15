from __future__ import annotations
from smart_canonical_identity import canonical_root

from smart_mission_status import load_mission_status, write_mission_status, sha256_json as mission_sha256_json

import hashlib
import json
import os
import shutil
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

import adjudicate_signal_challenger as adjudicator
import smart_3054_adjudication_preflight as preflight
import smart_independent_audit as independent_audit
import smart_official_evidence_consensus as official_consensus
import smart_official_result_ingest as official_ingest
import smart_prospective_authority as prospective_authority
import smart_sequential_prospective_proof as sequential
import smart_champion_challenger as champion_challenger
import smart_canonical_history_advance as history_advance
from smart_current_epoch_contract import resolve as resolve_current_epoch
from smart_learning_epoch_reset import verify_active_epoch
from smart_signal_agent import SmartSignalAgent
from smart_v2_engine import load_draws
from smart_prospective_authority_lock import verify_lock

SCHEMA = "SMART_TERMINAL_ENGINE_LEGACY_COMPAT_V1"
TARGET = 3054
CUTOFF = 3053
EXPECTED_FREEZE_SHA256: str | None = None
PRE_RESULT_DATA = "Mega-Sena_through_3053_v2.xlsx"
RESULT_DATA = "Mega-Sena_through_3054_official.xlsx"
INGEST_PROOF = "SMART_OFFICIAL_RESULT_INGEST_3054.json"
PRIMARY_PAYLOAD = "SMART_3054_OFFICIAL_PRIMARY_PAYLOAD.json"
CONSENSUS_FILE = "SMART_3054_OFFICIAL_EVIDENCE_CURRENT.json"
LEARNED_STATE = "SMART_SIGNAL_STATE_3054_LEARNED.json"
RESULT_STORE_PROOF = "SMART_CANONICAL_RESULT_STORE_ADVANCE_3054.json"
TERMINAL_PROOF = "SMART_TERMINAL_6OF6_PROOF_3054.json"
STATUS_FILE = "SMART_3054_TERMINAL_EXECUTOR_STATUS.json"
INDEPENDENT_AUDIT_FILE = "SMART_P14_INDEPENDENT_AUDIT_CURRENT.json"
_ACTIVE_CONTEXT_LOCK = threading.RLock()
COVERAGE_BINDINGS = (
    "SMART_P14_COVERAGE_BINDING_AUDIT.json",
    "SMART_P14_COVERAGE_BINDING_ORCHESTRATOR.json",
    "SMART_P14_COVERAGE_BINDING_PROMOTION.json",
    "SMART_P14_COVERAGE_BINDING_EVIDENCE_ONLY.json",
)

Fetcher = Callable[[int], tuple[dict[str, Any], dict[str, Any]]]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON object required: {path}")
    return obj


def _atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp = Path(temporary)
    try:
        temp.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()



def _project_local(root: Path, value: str | Path, label: str) -> Path:
    path = (root / Path(value)).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} escapes canonical root") from exc
    return path


def _active_epoch_binding(root: Path) -> dict[str, Any] | None:
    root = Path(root).resolve()
    active_path = root / "SMART_ACTIVE_EPOCH.json"
    if not active_path.is_file():
        return None
    active = verify_active_epoch(active_path)
    if int(active.get("target_contest", -1)) != int(TARGET):
        return None
    if int(active.get("cutoff_contest", -1)) != int(CUTOFF) or CUTOFF != TARGET - 1:
        raise ValueError("active epoch target/cutoff mismatch")
    if active.get("status") != "FROZEN" or active.get("result_used") is not False:
        raise ValueError("active epoch is not a frozen authority")
    state_paths = active.get("state_paths")
    if not isinstance(state_paths, dict):
        raise ValueError("active epoch state paths missing")
    freeze = _project_local(root, str(state_paths.get("freeze", "")), "active freeze")
    ledger = _project_local(root, str(state_paths.get("ledger", "")), "active ledger")
    state = _project_local(root, str(state_paths.get("state", "")), "active state")
    data = _project_local(root, str(active.get("data_file", "")), "active cutoff data")
    for path, label in ((freeze, "freeze"), (ledger, "ledger"), (state, "state"), (data, "cutoff data")):
        if not path.is_file():
            raise ValueError(f"active epoch {label} missing")
    freeze_auth = active.get("freeze_authority") if isinstance(active.get("freeze_authority"), dict) else {}
    expected_freeze = str(freeze_auth.get("sha256") or "")
    if len(expected_freeze) != 64 or sha256_file(freeze) != expected_freeze:
        raise ValueError("active epoch freeze hash mismatch")
    if int(freeze_auth.get("target_contest", -1)) != TARGET or int(freeze_auth.get("cutoff_contest", -1)) != CUTOFF:
        raise ValueError("active epoch freeze authority target/cutoff mismatch")
    if str(active.get("data_sha256", "")) != sha256_file(data):
        raise ValueError("active epoch cutoff data hash mismatch")
    state_auth = active.get("learning_state_authority") if isinstance(active.get("learning_state_authority"), dict) else {}
    if state_auth.get("sha256") and str(state_auth.get("sha256")) != sha256_file(state):
        raise ValueError("active epoch learning state hash mismatch")
    freeze_doc = _read_json(freeze)
    if int(freeze_doc.get("target_contest", -1)) != TARGET or int(freeze_doc.get("cutoff_contest", -1)) != CUTOFF:
        raise ValueError("active epoch freeze document target/cutoff mismatch")
    if freeze_doc.get("frozen_before_result") is not True or freeze_doc.get("causal_cutoff") is not True:
        raise ValueError("active epoch freeze is not causally pre-result")
    ledger_doc = champion_challenger.load_ledger(ledger)
    freeze_event = champion_challenger.active_freeze(ledger_doc, TARGET)
    if freeze_event is None or freeze_event.get("freeze_sha256") != expected_freeze:
        raise ValueError("active epoch ledger does not preserve the authoritative freeze")
    adjudications = _target_events(ledger_doc, "ADJUDICATION")
    if len(adjudications) > 1:
        raise ValueError("multiple target adjudications are forbidden")
    if not adjudications:
        current = resolve_current_epoch(root)
        if current.get("status") != "FROZEN" or int(current.get("target_contest", -1)) != int(TARGET):
            raise ValueError("current epoch contract does not match terminal target")
        if current.get("freeze_authority_present") is not True or current.get("generation_proof_valid") is not True:
            raise ValueError("current epoch lacks frozen generation authority")
        if str(current.get("freeze_sha256") or "") != expected_freeze:
            raise ValueError("current epoch freeze differs from active authority")
        expected_ledger = str(active.get("ledger_sha256") or "")
        if len(expected_ledger) == 64 and sha256_file(ledger) != expected_ledger:
            raise ValueError("unadjudicated active ledger hash changed")
        mode = "ACTIVE_EPOCH"
    else:
        adjudication = adjudications[0]
        if adjudication.get("freeze_sha256") != expected_freeze:
            raise ValueError("post-result adjudication is not bound to the authoritative freeze")
        actual = [int(x) for x in adjudication.get("actual_numbers", [])]
        if len(actual) != 6 or len(set(actual)) != 6 or any(x < 1 or x > 60 for x in actual):
            raise ValueError("post-result adjudication numbers are invalid")
        if adjudication.get("retroactive_rewrite") is not False:
            raise ValueError("post-result adjudication permits retroactive rewrite")
        guard = active.get("temporal_guard") if isinstance(active.get("temporal_guard"), dict) else {}
        if guard.get("status") != "PASS" or int(guard.get("target_contest", -1)) != TARGET:
            raise ValueError("post-result recovery lacks valid pre-draw temporal guard")
        if guard.get("before_scheduled_draw") is not True or guard.get("result_used") is not False:
            raise ValueError("post-result recovery temporal guard is not causal")
        current = {
            "status": "POST_RESULT_RECOVERY",
            "target_contest": TARGET,
            "freeze_authority_present": True,
            "generation_proof_valid": False,
            "historical_pre_result_authority_preserved": True,
            "freeze_sha256": expected_freeze,
        }
        mode = "ACTIVE_EPOCH_POST_ADJUDICATION_RECOVERY"
    return {
        "mode": mode,
        "freeze": freeze,
        "freeze_sha256": expected_freeze,
        "ledger": ledger,
        "state": state,
        "data": data,
        "learned": ledger.parent / LEARNED_STATE,
        "active": active,
        "current": current,
    }

def _preflight_readiness(root: Path, binding: dict[str, Any]) -> dict[str, Any]:
    if binding.get("mode") == "ACTIVE_EPOCH":
        return {
            "readiness_status": "PASS",
            "target_contest": TARGET,
            "cutoff_contest": CUTOFF,
            "generation_proof_valid": binding.get("current", {}).get("generation_proof_valid") is True,
            "freeze_sha256": binding.get("freeze_sha256"),
            "result_used": False,
        }
    return preflight.build_preflight(root)


def _preserved_lock_binding(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    lock_path = root / "SMART_PROSPECTIVE_AUTHORITY_LOCK.json"
    lock = verify_lock(lock_path)
    auth = lock.get("experiment_authority", {})
    if int(auth.get("target_contest", -1)) != TARGET or int(auth.get("cutoff_contest", -1)) != CUTOFF:
        raise ValueError("preserved prospective lock target/cutoff mismatch")
    if auth.get("eligible_for_scientific_adjudication") is not True:
        raise ValueError("preserved prospective lock lacks scientific adjudication authority")
    if auth.get("eligible_to_prove_post_freeze_engineering_version") is not False:
        raise ValueError("preserved prospective lock could falsely credit post-freeze engineering")
    if auth.get("immutable_until_adjudication") is not True:
        raise ValueError("preserved prospective lock is not immutable until adjudication")

    freeze = root / str(auth.get("freeze_file", ""))
    data = root / str(auth.get("data_file", ""))
    state = root / str(auth.get("signal_state_file", ""))
    ledger_path = root / str(auth.get("ledger_file", ""))
    for path, expected in (
        (freeze, str(auth.get("freeze_sha256", ""))),
        (data, str(auth.get("data_sha256", ""))),
        (state, str(auth.get("signal_state_sha256", ""))),
    ):
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"preserved prospective lock dependency mismatch: {path.name}")
    if not ledger_path.is_file():
        raise ValueError("preserved prospective signal ledger missing")
    ledger = champion_challenger.load_ledger(ledger_path)
    active = champion_challenger.active_freeze(ledger, TARGET)
    if active is None or active.get("freeze_sha256") != auth.get("freeze_sha256"):
        raise ValueError("preserved prospective lock no longer resolves to the active frozen attempt")
    adjudications = _target_events(ledger, "ADJUDICATION")
    if len(adjudications) > 1:
        raise ValueError("multiple 3054 adjudications are forbidden")
    if not adjudications:
        if sha256_file(ledger_path) != auth.get("ledger_sha256"):
            raise ValueError("unadjudicated preserved signal ledger hash changed")
    else:
        adjudication = adjudications[0]
        if adjudication.get("freeze_sha256") != auth.get("freeze_sha256"):
            raise ValueError("stored adjudication is not bound to the preserved freeze")
        actual = [int(x) for x in adjudication.get("actual_numbers", [])]
        if len(actual) != 6 or len(set(actual)) != 6 or any(x < 1 or x > 60 for x in actual):
            raise ValueError("stored adjudication actual numbers are invalid")

    return {
        "mode": "LOCKED_PROSPECTIVE_AUTHORITY",
        "freeze": freeze,
        "freeze_sha256": str(auth["freeze_sha256"]),
        "ledger": ledger_path,
        "state": state,
        "data": data,
        "learned": root / LEARNED_STATE,
    }


def _runtime_binding(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    if isinstance(EXPECTED_FREEZE_SHA256, str) and len(EXPECTED_FREEZE_SHA256) == 64:
        return {
            "mode": "EXPLICIT_LEGACY_TEST_OVERRIDE",
            "freeze": root / "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json",
            "freeze_sha256": EXPECTED_FREEZE_SHA256,
            "ledger": root / "SMART_SIGNAL_LEDGER.json",
            "state": root / "SMART_SIGNAL_STATE_3054_V2.json",
            "data": root / PRE_RESULT_DATA,
            "learned": root / LEARNED_STATE,
        }
    active_binding = _active_epoch_binding(root)
    if active_binding is not None:
        return active_binding
    try:
        paths = preflight._current_paths(root)
    except Exception:
        ledger_path = root / "SMART_SIGNAL_LEDGER.json"
        if ledger_path.is_file():
            ledger = champion_challenger.load_ledger(ledger_path)
            if len(_target_events(ledger, "ADJUDICATION")) == 1:
                return _preserved_lock_binding(root)
        raise
    freeze_sha = str(paths.get("authority_freeze_sha256", ""))
    if len(freeze_sha) != 64:
        raise ValueError("terminal executor freeze authority hash missing")
    mode = "ACTIVE_EPOCH" if paths.get("adjudication_authority_mode") == "ACTIVE_EPOCH_FROZEN" else "LOCKED_PROSPECTIVE_AUTHORITY"
    return {
        "mode": mode,
        "freeze": paths["freeze"],
        "freeze_sha256": freeze_sha,
        "ledger": paths["ledger"],
        "state": paths["state"],
        "data": paths["data"],
        "learned": paths["ledger"].parent / LEARNED_STATE if mode == "ACTIVE_EPOCH" else root / LEARNED_STATE,
    }

def _contest_max(path: Path) -> int:
    frame = pd.read_excel(path, usecols=["Concurso"])
    if frame.empty:
        raise ValueError("result store is empty")
    contests = frame["Concurso"].astype(int)
    if contests.duplicated().any():
        raise ValueError("result store contains duplicate contests")
    return int(contests.max())


def _target_events(ledger: dict[str, Any], event_type: str) -> list[dict[str, Any]]:
    return [
        event for event in ledger.get("events", [])
        if event.get("event_type") == event_type and int(event.get("target_contest", -1)) == TARGET
    ]


def _normalized_primary(payload: dict[str, Any]) -> dict[str, Any]:
    validated = official_ingest.validate_official_payload(payload, TARGET)
    return {
        "target_contest": TARGET,
        "draw_date": validated["draw_date_text"],
        "numbers": validated["numbers"],
    }


def _payload_from_normalized(normalized: dict[str, Any]) -> dict[str, Any]:
    return {
        "numero": TARGET,
        "dataApuracao": normalized["draw_date"],
        "listaDezenas": [f"{int(number):02d}" for number in normalized["numbers"]],
        "acumulado": False,
    }


def _ensure_primary_payload(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = root / PRIMARY_PAYLOAD
    normalized = _normalized_primary(payload)
    if path.exists():
        existing = _read_json(path)
        if _normalized_primary(existing) != normalized:
            raise ValueError("official primary payload conflicts with immutable first observation")
        return existing
    _atomic_write_json(path, payload)
    return payload


def _consensus_rank(document: dict[str, Any]) -> int:
    return 2 if document.get("terminal_source_corroboration_authorized") is True else 1


def _ensure_monotonic_consensus(root: Path, document: dict[str, Any]) -> dict[str, Any]:
    if int(document.get("target_contest", -1)) != TARGET:
        raise ValueError("official consensus target mismatch")
    primary = document.get("primary", {})
    if primary.get("validated") is not True:
        raise ValueError("official consensus primary channel is not validated")
    path = root / CONSENSUS_FILE
    if not path.exists():
        _atomic_write_json(path, document)
        return document
    existing = _read_json(path)
    if (
        existing.get("primary", {}).get("numbers") != primary.get("numbers")
        or existing.get("primary", {}).get("draw_date") != primary.get("draw_date")
    ):
        raise ValueError("official consensus primary observation changed")
    if _consensus_rank(document) < _consensus_rank(existing):
        return existing
    if _consensus_rank(document) == _consensus_rank(existing) and document.get("status") == existing.get("status"):
        return existing
    _atomic_write_json(path, document)
    return document


def _load_existing_official_evidence(root: Path) -> tuple[dict[str, Any], dict[str, Any]] | None:
    payload_path = root / PRIMARY_PAYLOAD
    consensus_path = root / CONSENSUS_FILE
    if not payload_path.exists() and not consensus_path.exists():
        return None
    if not payload_path.exists() or not consensus_path.exists():
        raise ValueError("official evidence is partially present")
    payload = _read_json(payload_path)
    consensus = _read_json(consensus_path)
    normalized = _normalized_primary(payload)
    if consensus.get("primary", {}).get("numbers") != normalized["numbers"]:
        raise ValueError("stored official payload and consensus disagree")
    if consensus.get("primary", {}).get("draw_date") != normalized["draw_date"]:
        raise ValueError("stored official payload and consensus date disagree")
    return payload, consensus


def _ensure_ingest(root: Path, payload: dict[str, Any], binding: dict[str, Any] | None = None) -> dict[str, Any]:
    output = root / RESULT_DATA
    proof_path = root / INGEST_PROOF
    normalized = _normalized_primary(payload)
    if output.exists() or proof_path.exists():
        if not output.exists() or not proof_path.exists():
            raise ValueError("official result ingest is partially present")
        proof = _read_json(proof_path)
        if int(proof.get("target_contest", -1)) != TARGET or proof.get("actual_numbers") != normalized["numbers"]:
            raise ValueError("existing official ingest proof conflicts with official result")
        if proof.get("output_sha256") != sha256_file(output):
            raise ValueError("existing official ingest output hash mismatch")
        _, contests = load_draws(output)
        if int(contests[-1]) != TARGET:
            raise ValueError("existing official ingest output does not end at target")
        return proof
    binding = binding or _runtime_binding(root)
    source = binding["data"]
    if _contest_max(source) != CUTOFF:
        raise ValueError("active pre-result dataset must end at cutoff before first target ingest")
    return official_ingest.ingest(source, output, proof_path, TARGET, payload)


def _ensure_adjudication(root: Path, actual_numbers: list[int], binding: dict[str, Any] | None = None) -> dict[str, Any]:
    binding = binding or _runtime_binding(root)
    ledger_path = binding["ledger"]
    expected_freeze_sha256 = binding["freeze_sha256"]
    ledger = champion_challenger.load_ledger(ledger_path)
    existing = _target_events(ledger, "ADJUDICATION")
    if len(existing) > 1:
        raise ValueError("multiple 3054 adjudications are forbidden")
    if existing:
        event = existing[0]
        if sorted(int(x) for x in event.get("actual_numbers", [])) != sorted(actual_numbers):
            raise ValueError("existing 3054 adjudication conflicts with official result")
        if event.get("freeze_sha256") != expected_freeze_sha256:
            raise ValueError("existing adjudication references a freeze outside the active epoch")
        return {
            "status": "ALREADY_ADJUDICATED_EVENT_PRESERVED",
            "target_contest": TARGET,
            "actual_numbers": event["actual_numbers"],
            "champion_hits": int(event["champion_hits"]),
            "challenger_hits": int(event["challenger_hits"]),
            "e_value_after": float(event["e_value_after"]),
        }
    cwd = Path.cwd()
    try:
        os.chdir(root)
        result = adjudicator.adjudicate(root / RESULT_DATA, TARGET, ledger_path)
    finally:
        os.chdir(cwd)
    result["status"] = "ADJUDICATED"
    return result


def _agent_from_prestate(prestate: dict[str, Any]) -> SmartSignalAgent:
    return SmartSignalAgent(
        start=int(prestate["start_index"]),
        eta=float(prestate["eta"]),
        redundancy_threshold=float(prestate["redundancy_consensus_threshold"]),
        meta_strength=float(prestate["meta_strength"]),
        calibration_strength=float(prestate["calibration_strength"]),
    )


def _ensure_learned_state(root: Path, binding: dict[str, Any] | None = None) -> dict[str, Any]:
    binding = binding or _runtime_binding(root)
    through = root / RESULT_DATA
    learned_path = binding["learned"]
    prestate_path = binding["state"]
    pre_result_data = binding["data"]
    data_sha = sha256_file(through)
    if learned_path.exists():
        state = _read_json(learned_path)
        if int(state.get("last_contest", -1)) != TARGET or state.get("data_sha256") != data_sha:
            raise ValueError("existing learned state is not bound to official target data")
        return state
    prestate = _read_json(prestate_path)
    if int(prestate.get("last_contest", -1)) != CUTOFF:
        raise ValueError("active epoch prestate does not end at cutoff")
    if prestate.get("data_sha256") != sha256_file(pre_result_data):
        raise ValueError("active epoch prestate data hash mismatch")
    draws, contests = load_draws(through)
    if int(contests[-1]) != TARGET:
        raise ValueError("official result data does not end at target")
    agent = _agent_from_prestate(prestate)
    cwd = Path.cwd()
    try:
        os.chdir(root)
        agent.replay_history(draws, contests)
        state = agent.state_document(data_sha256=data_sha)
    finally:
        os.chdir(cwd)
    state.update({
        "sequential_learning_target": TARGET,
        "learning_after_adjudication": True,
        "official_result_learning": True,
        "retroactive_rewrite": False,
        "source_prestate_sha256": sha256_file(prestate_path),
        "source_freeze_sha256": binding["freeze_sha256"],
        "authority_mode": binding["mode"],
    })
    _atomic_write_json(learned_path, state)
    return state


def _ensure_learning_and_sequence(root: Path, binding: dict[str, Any] | None = None) -> dict[str, Any]:
    binding = binding or _runtime_binding(root)
    ledger_path = binding["ledger"]
    learned_path = binding["learned"]
    ledger = champion_challenger.load_ledger(ledger_path)
    learning = _target_events(ledger, sequential.LEARNING_EVENT)
    proofs = _target_events(ledger, sequential.PROOF_EVENT)
    if len(learning) > 1 or len(proofs) > 1:
        raise ValueError("duplicate target learning/proof events are forbidden")
    if not learning:
        sequential.append_learning_update(ledger_path, TARGET, learned_path, root / RESULT_DATA)
    ledger = champion_challenger.load_ledger(ledger_path)
    proofs = _target_events(ledger, sequential.PROOF_EVENT)
    if not proofs:
        sequential.append_sequence_proof(ledger_path, TARGET)
    ledger = champion_challenger.load_ledger(ledger_path)
    validation = sequential.validate_target_sequence(
        ledger, TARGET, require_learning=True, require_proof=True, verify_files=True, root=root
    )
    if validation.get("valid") is not True:
        raise RuntimeError("target sequential proof validation failed")
    return validation


def _verified_stale_coverage_observations(root: Path, bindings: list[Path]) -> list[dict[str, Any]]:
    """Record old P14 coverage as STALE evidence, never new source coverage."""
    from smart_source_identity import sha256_source_file

    observed = []
    for path in bindings:
        path = Path(path).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or path.is_symlink():
            raise ValueError("P14 coverage binding path is unsafe")
        doc = _read_json(path)
        if doc.get("schema") != independent_audit.COVERAGE_BINDING_SCHEMA:
            raise ValueError("P14 coverage binding schema invalid")
        raw_source = doc.get("source_file")
        raw_report = doc.get("coverage_report_file")
        if (not isinstance(raw_source, str) or not isinstance(raw_report, str)
                or Path(raw_source).is_absolute() or Path(raw_report).is_absolute()):
            raise ValueError("P14 coverage source/report path invalid")
        source = (root / raw_source).resolve()
        report = (root / raw_report).resolve()
        if (not source.is_relative_to(root.resolve()) or not report.is_relative_to(root.resolve())
                or not source.is_file() or not report.is_file()
                or source.is_symlink() or report.is_symlink()):
            raise ValueError("P14 coverage evidence path is unsafe or missing")
        if sha256_file(report) != doc.get("coverage_report_sha256"):
            raise ValueError("P14 coverage historical report hash mismatch")
        old_hash = doc.get("source_sha256")
        live_hash = sha256_source_file(source)
        if old_hash == live_hash:
            # A current source must still pass the ORIGINAL 100% P14 gate.
            independent_audit.audit_coverage_binding(root, path)
        observed.append({
            "binding_file": path.relative_to(root).as_posix(),
            "historical_source_sha256": old_hash,
            "current_source_sha256": live_hash,
            "source_file": source.relative_to(root).as_posix(),
            "report_sha256_verified": True,
            "current_source_coverage_proven": old_hash == live_hash,
        })
    if not any(not row["current_source_coverage_proven"] for row in observed):
        raise RuntimeError("cannot classify a fully current P14 coverage set as stale")
    return observed


def _degraded_result_audit(root: Path, binding: dict[str, Any],
                           bindings: list[Path]) -> dict[str, Any]:
    """Independent replay remains mandatory; P14 certification remains blocked.

    Post-draw observations must be retained even when historical 100% coverage
    evidence is stale, but no such observation can earn scientific promotion.
    All other audit errors remain fatal.
    """
    stale = _verified_stale_coverage_observations(root, bindings)
    policy = independent_audit.policy_snapshot()
    independence = independent_audit.audit_independence(root)
    prospective = independent_audit.audit_prospective_ledger(root, binding["ledger"])
    replay = independent_audit.audit_deterministic_replay(
        root, binding["data"], TARGET, start=1000
    )
    deficiency_registry = independent_audit.load_material_deficiency_registry(root=root)
    result = {
        "schema": independent_audit.SCHEMA,
        "status": "DEGRADED_P14_COVERAGE_STALE",
        "scientific_coverage_certified": False,
        "terminal_promotion_permitted": False,
        "promotion_authority": False,
        "historical_coverage_source_bindings": stale,
        "coverage": {"status": "BLOCKED_STALE_SOURCE_HASH", "bindings": stale},
        "independence": independence,
        "policy": policy,
        "prospective_ledger": prospective,
        "deterministic_replay": replay,
        "checks": {
            "coverage_lines_and_branches": False,
            "hash_integrity": False,
            "deterministic_replay": True,
            "future_leakage_absent": True,
            "full_champion_comparison": True,
            "promotion_lineage_recomputed": True,
            "independence_no_forbidden_dependencies": True,
            "independent_freeze_decision_oracle":
                replay.get("independent_decision_oracle", {}).get("verified") is True,
        },
        "independent_of_promotion_decision": True,
        "material_deficiency_registry": deficiency_registry,
        "material_deficiencies": list(deficiency_registry["open_deficiencies"]),
    }
    result["sha256"] = independent_audit.sha256_json(result)
    return result


def _run_independent_audit(root: Path, binding: dict[str, Any] | None = None) -> dict[str, Any]:
    binding = binding or _runtime_binding(root)
    bindings = [root / name for name in COVERAGE_BINDINGS]
    cwd = Path.cwd()
    try:
        os.chdir(root)
        try:
            report = independent_audit.run_independent_audit(
                root, binding["ledger"], bindings, binding["data"], TARGET, start=1000
            )
        except ValueError as exc:
            if str(exc) != "coverage binding source hash mismatch":
                raise
            report = _degraded_result_audit(root, binding, bindings)
    finally:
        os.chdir(cwd)
    if report.get("status") not in {"PASS", "DEGRADED_P14_COVERAGE_STALE"}:
        raise RuntimeError("independent audit did not pass")
    _atomic_write_json(root / INDEPENDENT_AUDIT_FILE, report)
    return report


def _draw_map(path: Path) -> dict[int, tuple[int, ...]]:
    frame = pd.read_excel(path)
    required = {"Concurso", *official_ingest.BALL_COLUMNS}
    if not required.issubset(frame.columns):
        raise ValueError("result store draw columns missing")
    result: dict[int, tuple[int, ...]] = {}
    for _, row in frame.iterrows():
        contest = int(row["Concurso"])
        numbers = tuple(sorted(int(row[column]) for column in official_ingest.BALL_COLUMNS))
        if contest in result or len(set(numbers)) != 6:
            raise ValueError("invalid result store draw sequence")
        result[contest] = numbers
    return result


def _advance_canonical_result_store(root: Path) -> dict[str, Any]:
    canonical = root / "Mega-Sena.xlsx"
    through = root / RESULT_DATA
    proof_path = root / RESULT_STORE_PROOF
    canonical_draws = _draw_map(canonical)
    through_draws = _draw_map(through)
    max_current = max(canonical_draws)
    if max(through_draws) != TARGET:
        raise ValueError("official through-dataset does not end at 3054")
    for contest, numbers in canonical_draws.items():
        if through_draws.get(contest) != numbers:
            raise ValueError(f"canonical result prefix mismatch at contest {contest}")
    if max_current == TARGET:
        if canonical_draws != through_draws:
            raise ValueError("already-advanced canonical result store differs from official through-dataset")
        if proof_path.exists():
            return _read_json(proof_path)
        raise ValueError("canonical store already advanced without its proof")
    if max_current != CUTOFF:
        raise ValueError("canonical result store is not at expected pre-advance cutoff")
    before_sha = sha256_file(canonical)
    fd, temporary = tempfile.mkstemp(prefix="Mega-Sena.3054.", suffix=".tmp.xlsx", dir=root)
    os.close(fd)
    temp = Path(temporary)
    try:
        shutil.copyfile(through, temp)
        if _draw_map(temp) != through_draws:
            raise RuntimeError("temporary canonical result store verification failed")
        os.replace(temp, canonical)
    finally:
        if temp.exists():
            temp.unlink()
    proof = {
        "schema": "SMART_CANONICAL_RESULT_STORE_ADVANCE_1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_contest": TARGET,
        "canonical_sha256_before": before_sha,
        "canonical_sha256_after": sha256_file(canonical),
        "official_through_file": through.name,
        "official_through_sha256": sha256_file(through),
        "prefix_preserved": True,
        "canonical_max_after": TARGET,
        "draw_fields_authoritative": True,
        "auxiliary_non_signal_fields_may_be_null_until_later_official_reconciliation": True,
        "retroactive_rewrite": False,
        "status": "PASS",
    }
    _atomic_write_json(proof_path, proof)
    return proof


def evaluate_terminal_rule(
    root: Path,
    ledger: dict[str, Any],
    consensus: dict[str, Any],
    audit: dict[str, Any],
    sequence_validation: dict[str, Any],
    binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    freeze_event = champion_challenger.active_freeze(ledger, TARGET)
    if freeze_event is None:
        raise ValueError("active 3054 freeze is missing")
    freeze_path = Path(str(freeze_event["freeze_file"]))
    if not freeze_path.is_absolute():
        freeze_path = root / freeze_path
    binding = binding or _runtime_binding(root)
    expected_freeze_sha256 = binding["freeze_sha256"]
    if not freeze_path.is_file() or sha256_file(freeze_path) != expected_freeze_sha256:
        raise ValueError("active target freeze artifact hash mismatch")
    if binding["mode"] == "ACTIVE_EPOCH" and freeze_path.resolve() != Path(binding["freeze"]).resolve():
        raise ValueError("ledger freeze path differs from active epoch authority")
    freeze = _read_json(freeze_path)
    adjudications = _target_events(ledger, "ADJUDICATION")
    if len(adjudications) != 1:
        raise ValueError("terminal rule requires exactly one 3054 adjudication")
    adjudication = adjudications[0]
    actual = sorted(int(x) for x in adjudication["actual_numbers"])
    champion_top6 = sorted(int(x) for x in freeze["champion"]["top6"])
    recomputed_hits = len(set(actual) & set(champion_top6))
    target_adjudication_count = len(adjudications)
    total_adjudication_count = sum(1 for event in ledger.get("events", []) if event.get("event_type") == "ADJUDICATION")
    prospective = audit.get("prospective_ledger", {})
    primary = consensus.get("primary", {})
    checks = {
        "freeze_hash_immutable": freeze_event.get("freeze_sha256") == expected_freeze_sha256,
        "freeze_before_result": freeze_event.get("frozen_before_result") is True and freeze.get("frozen_before_result") is True,
        "causal_cutoff_3053": int(freeze_event.get("cutoff_contest", -1)) == CUTOFF and int(freeze.get("cutoff_contest", -1)) == CUTOFF,
        "single_active_production_top6": freeze.get("champion_remains_active") is True and freeze.get("production_switch_performed") is False,
        "official_primary_validated": primary.get("validated") is True,
        "official_numbers_match_adjudication": sorted(int(x) for x in primary.get("numbers", [])) == actual,
        "sequential_proof_valid": sequence_validation.get("valid") is True and sequence_validation.get("proof_recorded") is True,
        "independent_audit_pass": audit.get("status") == "PASS" and prospective.get("status") == "PASS",
        "all_attempts_counted": int(prospective.get("pair_count", -1)) == total_adjudication_count,
        "no_future_leakage": prospective.get("no_future_leakage") is True,
        "source_corroborated": consensus.get("terminal_source_corroboration_authorized") is True,
        "exact_6of6": recomputed_hits == 6 and int(adjudication.get("champion_hits", -1)) == 6,
        "retroactive_rewrite_absent": adjudication.get("retroactive_rewrite") is False,
    }
    exact = checks["exact_6of6"]
    non_source_checks = all(value for key, value in checks.items() if key != "source_corroborated")
    eligible = all(checks.values())
    if not exact:
        status = "MISSION_ACTIVE_RESULT_ADJUDICATED_NO_6OF6"
    elif not checks["source_corroborated"] and non_source_checks:
        status = "MISSION_ACTIVE_6OF6_PENDING_SOURCE_CORROBORATION"
    elif eligible:
        status = "MISSION_PROVEN_ELIGIBLE"
    else:
        status = "MISSION_ACTIVE_6OF6_BLOCKED_BY_TERMINAL_GUARD"
    return {
        "schema": "SMART_TERMINAL_RULE_EVALUATION_1",
        "target_contest": TARGET,
        "status": status,
        "eligible_for_mission_proven": eligible,
        "frozen_top6": champion_top6,
        "actual_numbers": actual,
        "recomputed_hits": recomputed_hits,
        "adjudication_count": target_adjudication_count,
        "total_adjudication_count": total_adjudication_count,
        "audited_pair_count": prospective.get("pair_count"),
        "checks": checks,
    }


def _promote_terminal_mission(root: Path, evaluation: dict[str, Any], consensus: dict[str, Any], audit: dict[str, Any], sequence: dict[str, Any], binding: dict[str, Any] | None = None) -> dict[str, Any]:
    if evaluation.get("eligible_for_mission_proven") is not True:
        raise ValueError("terminal mission promotion requires a fully eligible evaluation")
    mission_path = root / "SMART_MISSION_STATUS.json"
    mission = load_mission_status(mission_path, root=root)
    if mission.get("terminal_6of6_proven") is True:
        return mission
    if mission.get("status") != "MISSION_ACTIVE":
        raise ValueError("unexpected mission state before terminal promotion")
    binding = binding or _runtime_binding(root)
    proof = {
        "schema": "SMART_TERMINAL_6OF6_PROOF_1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_contest": TARGET,
        "terminal_rule": mission.get("terminal_rule"),
        "evaluation": evaluation,
        "freeze_file": binding["freeze"].resolve().relative_to(root.resolve()).as_posix(),
        "freeze_sha256": binding["freeze_sha256"],
        "signal_ledger_file": binding["ledger"].resolve().relative_to(root.resolve()).as_posix(),
        "signal_ledger_sha256": sha256_file(binding["ledger"]),
        "official_evidence_file": CONSENSUS_FILE,
        "official_evidence_sha256": sha256_file(root / CONSENSUS_FILE),
        "independent_audit_file": INDEPENDENT_AUDIT_FILE,
        "independent_audit_sha256": sha256_file(root / INDEPENDENT_AUDIT_FILE),
        "sequence_sha256": sequence.get("sequence_sha256"),
        "all_attempts_counted": evaluation["checks"]["all_attempts_counted"],
        "independent_audit_pass": audit.get("status") == "PASS",
        "source_corroborated": consensus.get("terminal_source_corroboration_authorized") is True,
        "retroactive_selection_prohibited": True,
        "status": "MISSION_PROVEN",
    }
    proof["sha256"] = mission_sha256_json(proof)
    proof_path = root / TERMINAL_PROOF
    _atomic_write_json(proof_path, proof)
    mission = dict(mission)
    mission.update({
        "status": "MISSION_PROVEN",
        "terminal_6of6_proven": True,
        "scientific_predictive_status": "TERMINAL_PROSPECTIVE_6OF6_OBSERVED",
        "proven_target_contest": TARGET,
        "proven_top6": evaluation["frozen_top6"],
        "official_actual_numbers": evaluation["actual_numbers"],
        "terminal_proof_file": TERMINAL_PROOF,
        "terminal_proof_sha256": sha256_file(proof_path),
        "independent_audit_file": INDEPENDENT_AUDIT_FILE,
        "official_evidence_file": CONSENSUS_FILE,
        "proven_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    try:
        write_mission_status(mission_path, mission, root=root)
    except Exception:
        # Active-epoch proof is non-authoritative until SMART_MISSION_STATUS binds it.
        # Remove the just-written candidate on ordinary failure; if the process is
        # interrupted before cleanup, epoch-scoped placement keeps top-level
        # terminal claim inventory consistent.
        if proof_path.is_file() and sha256_file(proof_path) == mission.get("terminal_proof_sha256"):
            proof_path.unlink()
        raise
    return mission


def _default_operator_fetcher(root: Path) -> Fetcher:
    """Only local operator declaration is used by direct engine entrypoints."""
    from smart_operator_result import fetch as operator_fetch
    return lambda target: operator_fetch(root, target)


def probe(root: str | Path, fetcher: Fetcher | None = None) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    if fetcher is None:
        fetcher = _default_operator_fetcher(root)
    binding = _runtime_binding(root)
    if not Path(binding["freeze"]).is_file() or sha256_file(Path(binding["freeze"])) != binding["freeze_sha256"]:
        raise ValueError("active epoch freeze hash differs from immutable authority")
    ledger = champion_challenger.load_ledger(binding["ledger"])
    adjudications = _target_events(ledger, "ADJUDICATION")
    existing = _load_existing_official_evidence(root)
    if not adjudications:
        readiness = _preflight_readiness(root, binding)
        if readiness.get("readiness_status") != "PASS":
            raise RuntimeError("3054 preflight is not PASS")
    else:
        readiness = {"readiness_status": "POST_RESULT_SEQUENCE_IN_PROGRESS_OR_COMPLETE"}
    try:
        payload, consensus = fetcher(TARGET)
    except Exception as exc:
        if existing is None and not adjudications:
            return {
                "schema": SCHEMA,
                "target_contest": TARGET,
                "status": "WAITING_OFFICIAL_RESULT",
                "preflight_status": readiness["readiness_status"],
                "official_result_available": False,
                "canonical_writes_performed": False,
                "error_type": type(exc).__name__,
                "terminal_6of6_proven": False,
            }
        if existing is None:
            raise
        payload, consensus = existing
        return {
            "schema": SCHEMA,
            "target_contest": TARGET,
            "status": "OFFICIAL_RESULT_ALREADY_CAPTURED_REFRESH_UNAVAILABLE",
            "preflight_status": readiness["readiness_status"],
            "official_result_available": True,
            "canonical_writes_performed": False,
            "error_type": type(exc).__name__,
            "terminal_source_corroboration_authorized": consensus.get("terminal_source_corroboration_authorized") is True,
            "terminal_6of6_proven": False,
        }
    normalized = _normalized_primary(payload)
    return {
        "schema": SCHEMA,
        "target_contest": TARGET,
        "status": "OFFICIAL_RESULT_AVAILABLE",
        "preflight_status": readiness["readiness_status"],
        "official_result_available": True,
        "actual_numbers": normalized["numbers"],
        "draw_date": normalized["draw_date"],
        "terminal_source_corroboration_authorized": consensus.get("terminal_source_corroboration_authorized") is True,
        "result_input_authority": consensus.get("primary", {}).get("channel"),
        "canonical_writes_performed": False,
        "terminal_6of6_proven": False,
    }


def execute(root: str | Path, fetcher: Fetcher | None = None, *, allow_terminal_write: bool = True) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    if fetcher is None:
        fetcher = _default_operator_fetcher(root)
    binding = _runtime_binding(root)
    if not Path(binding["freeze"]).is_file() or sha256_file(Path(binding["freeze"])) != binding["freeze_sha256"]:
        raise ValueError("active epoch freeze hash differs from immutable authority")
    ledger = champion_challenger.load_ledger(binding["ledger"])
    adjudications = _target_events(ledger, "ADJUDICATION")
    if len(adjudications) > 1:
        raise ValueError("multiple 3054 adjudications are forbidden")
    if not adjudications:
        readiness = _preflight_readiness(root, binding)
        if readiness.get("readiness_status") != "PASS":
            raise RuntimeError("3054 preflight is not PASS")
    existing = _load_existing_official_evidence(root)
    try:
        fresh_payload, fresh_consensus = fetcher(TARGET)
    except Exception as exc:
        if existing is None and not adjudications:
            return {
                "schema": SCHEMA,
                "target_contest": TARGET,
                "status": "WAITING_OFFICIAL_RESULT",
                "preflight_status": "PASS",
                "official_result_available": False,
                "canonical_writes_performed": False,
                "error_type": type(exc).__name__,
                "terminal_6of6_proven": False,
            }
        if existing is None:
            raise
        payload, consensus = existing
    else:
        payload = _ensure_primary_payload(root, fresh_payload)
        consensus = _ensure_monotonic_consensus(root, fresh_consensus)

    normalized = _normalized_primary(payload)
    ingest = _ensure_ingest(root, payload, binding=binding)
    adjudication = _ensure_adjudication(root, normalized["numbers"], binding=binding)
    learned = _ensure_learned_state(root, binding=binding)
    sequence_validation = _ensure_learning_and_sequence(root, binding=binding)
    audit = _run_independent_audit(root, binding=binding)
    result_store = history_advance.advance_completed_epoch(root, binding["active"]) if binding.get("mode") == "ACTIVE_EPOCH" else _advance_canonical_result_store(root)
    ledger = champion_challenger.load_ledger(binding["ledger"])
    consensus = _read_json(root / CONSENSUS_FILE)
    evaluation = evaluate_terminal_rule(root, ledger, consensus, audit, sequence_validation, binding=binding)

    mission = load_mission_status(root / "SMART_MISSION_STATUS.json", root=root)
    if evaluation["eligible_for_mission_proven"] and allow_terminal_write:
        mission = _promote_terminal_mission(root, evaluation, consensus, audit, sequence_validation, binding=binding)

    status = {
        "schema": SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_contest": TARGET,
        "status": evaluation["status"] if mission.get("terminal_6of6_proven") is not True else "MISSION_PROVEN",
        "official_result_available": True,
        "actual_numbers": normalized["numbers"],
        "official_evidence_status": consensus.get("status"),
        "terminal_source_corroboration_authorized": consensus.get("terminal_source_corroboration_authorized") is True,
        "ingest_status": ingest.get("schema"),
        "adjudication_status": adjudication.get("status", "ADJUDICATED"),
        "champion_hits": int(adjudication["champion_hits"]),
        "challenger_hits": int(adjudication["challenger_hits"]),
        "learned_state_last_contest": int(learned["last_contest"]),
        "sequence_valid": sequence_validation.get("valid") is True,
        "independent_audit_status": audit.get("status"),
        "audited_pair_count": audit.get("prospective_ledger", {}).get("pair_count"),
        "canonical_result_store_status": result_store.get("status"),
        "terminal_evaluation": evaluation,
        "mission_state": mission.get("status"),
        "terminal_6of6_proven": mission.get("terminal_6of6_proven") is True,
    }
    _atomic_write_json(root / STATUS_FILE, status)
    return status


@contextmanager
def active_epoch_context(root: str | Path, target: int):
    root = canonical_root(root)
    global SCHEMA, TARGET, CUTOFF, PRE_RESULT_DATA, RESULT_DATA, INGEST_PROOF, PRIMARY_PAYLOAD
    global CONSENSUS_FILE, LEARNED_STATE, RESULT_STORE_PROOF, TERMINAL_PROOF, STATUS_FILE, INDEPENDENT_AUDIT_FILE
    root = Path(root).resolve()
    with _ACTIVE_CONTEXT_LOCK:
        active = verify_active_epoch(root / "SMART_ACTIVE_EPOCH.json")
        selected = int(active.get("target_contest", -1))
        if int(target) != selected:
            raise ValueError("requested terminal target differs from active epoch")
        state_paths = active.get("state_paths")
        if not isinstance(state_paths, dict) or not state_paths.get("ledger"):
            raise ValueError("active epoch ledger path missing")
        epoch_rel = Path(str(state_paths["ledger"])).parent
        names = ("SCHEMA", "TARGET", "CUTOFF", "PRE_RESULT_DATA", "RESULT_DATA", "INGEST_PROOF", "PRIMARY_PAYLOAD", "CONSENSUS_FILE", "LEARNED_STATE", "RESULT_STORE_PROOF", "TERMINAL_PROOF", "STATUS_FILE", "INDEPENDENT_AUDIT_FILE")
        saved = {name: globals()[name] for name in names}
        try:
            SCHEMA = "SMART_TERMINAL_EXECUTOR_ACTIVE_EPOCH_1"
            TARGET = selected
            CUTOFF = selected - 1
            PRE_RESULT_DATA = str(active.get("data_file", ""))
            RESULT_DATA = (epoch_rel / f"Mega-Sena_through_{selected}.xlsx").as_posix()
            INGEST_PROOF = (epoch_rel / f"SMART_OFFICIAL_RESULT_INGEST_{selected}.json").as_posix()
            PRIMARY_PAYLOAD = (epoch_rel / f"SMART_{selected}_OFFICIAL_PRIMARY_PAYLOAD.json").as_posix()
            CONSENSUS_FILE = (epoch_rel / f"SMART_{selected}_OFFICIAL_EVIDENCE_CURRENT.json").as_posix()
            LEARNED_STATE = f"SMART_SIGNAL_STATE_{selected}_LEARNED.json"
            RESULT_STORE_PROOF = f"SMART_CANONICAL_HISTORY_ADVANCE_{selected}.json"
            TERMINAL_PROOF = (epoch_rel / f"SMART_TERMINAL_6OF6_PROOF_{selected}.json").as_posix()
            STATUS_FILE = (epoch_rel / f"SMART_TERMINAL_EXECUTOR_STATUS_{selected}.json").as_posix()
            INDEPENDENT_AUDIT_FILE = (epoch_rel / f"SMART_P14_INDEPENDENT_AUDIT_{selected}.json").as_posix()
            yield active
        finally:
            for name, value in saved.items():
                globals()[name] = value


def probe_active_epoch(root: str | Path, target: int, fetcher: Fetcher | None = None) -> dict[str, Any]:
    root = canonical_root(root)
    with active_epoch_context(root, target):
        return probe(root, fetcher=fetcher)


def execute_active_epoch(root: str | Path, target: int, fetcher: Fetcher | None = None, *, allow_terminal_write: bool = True) -> dict[str, Any]:
    root = canonical_root(root)
    with active_epoch_context(root, target):
        return execute(root, fetcher=fetcher, allow_terminal_write=allow_terminal_write)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(canonical_root()))
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--no-terminal-write", action="store_true")
    args = parser.parse_args()
    root = canonical_root(args.root)
    result = probe(root) if args.probe_only else execute(root, allow_terminal_write=not args.no_terminal_write)
    if args.probe_only:
        _atomic_write_json(root / STATUS_FILE, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
