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
from smart_scoped_history_gate import inspect_freeze_evidence
from smart_terminal_historical_freeze import write_unverified_history_audit as _historical_write_unverified_audit
from smart_terminal_historical_freeze import precheck_historical_freeze_evidence as _historical_freeze_precheck
from smart_terminal_historical_freeze import select_terminal_audit as _select_terminal_audit
from smart_terminal_official_ingest import ensure_ingest as _official_ingest_guard
from smart_terminal_official_ingest import ensure_adjudication as _official_adjudication_guard
from smart_terminal_official_evidence import (
    ensure_primary_payload as _official_ensure_primary,
    ensure_monotonic_consensus as _official_ensure_consensus,
    load_existing_official_evidence as _official_load_existing,
    acquire_official_result as _official_acquire_result,
)
from smart_terminal_result_store import advance_canonical_result_store as _store_advance
from smart_terminal_result_store import dispatch_result_store as _dispatch_result_store
from smart_terminal_epoch_names import epoch_runtime_names as _epoch_runtime_names
from smart_terminal_execution_preflight import validate_execution_preflight as _execute_preflight_validate
from smart_terminal_execution_preflight import build_execution_readiness as _build_execution_readiness
from smart_terminal_execution_status import build_terminal_execution_status as _build_terminal_execution_status
from smart_terminal_probe import probe_terminal_result as _probe_terminal_result
from smart_terminal_mission_promotion import promote_terminal_mission as _mission_proof_persist
from smart_terminal_learned_state import (
    agent_from_prestate as _learned_agent_from_prestate,
    verify_existing_learned_policy as _learned_verify_existing_policy,
    ensure_learned_state as _learned_ensure_state,
)
from smart_terminal_sequential_learning import ensure_learning_and_sequence as _ensure_terminal_sequence
from smart_terminal_stale_coverage import run_terminal_independent_audit as _run_stale_independent_audit
from smart_terminal_stale_coverage import build_degraded_result_audit as _build_degraded_result_audit
from smart_terminal_stale_coverage import verified_stale_coverage_observations as _resolve_stale_coverage_observations
from smart_terminal_runtime_binding import resolve_runtime_binding as _resolve_terminal_runtime_binding
from smart_terminal_active_epoch import active_epoch_binding as _resolve_active_epoch_binding
from smart_terminal_prospective_lock import preserved_lock_binding as _prospective_lock_binding
from smart_terminal_result_data import (
    contest_max as _result_contest_max,
    target_events as _result_target_events,
    normalize_primary as _result_normalize_primary,
    payload_from_normalized as _result_payload_from_normalized,
    consensus_rank as _result_consensus_rank,
    draw_map as _result_draw_map,
)
from smart_terminal_integrity import (
    file_sha256 as _integrity_file_sha256,
    read_json_object as _integrity_read_json_object,
    atomic_write_json as _integrity_atomic_write_json,
    project_local_path as _integrity_project_local_path,
    validate_post_result_temporal_guard as _integrity_validate_post_result_temporal_guard,
)

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
    return _integrity_file_sha256(path)


def _read_json(path: Path) -> dict[str, Any]:
    return _integrity_read_json_object(path)


def _atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    return _integrity_atomic_write_json(path, document)


def _project_local(root: Path, value: str | Path, label: str) -> Path:
    return _integrity_project_local_path(root, value, label)


def _validate_post_result_temporal_guard(
    active: dict[str, Any], freeze_doc: dict[str, Any], target: int,
) -> str:
    return _integrity_validate_post_result_temporal_guard(active, freeze_doc, target)


def _active_epoch_binding(root: Path) -> dict[str, Any] | None:
    """Compatibility facade: preserve engine dependency patch points."""
    return _resolve_active_epoch_binding(
        root, target=TARGET, cutoff=CUTOFF, learned_state=LEARNED_STATE,
        verify_active_epoch=verify_active_epoch, project_local=_project_local,
        sha256_file=sha256_file, read_json=_read_json,
        load_ledger=champion_challenger.load_ledger,
        active_freeze=champion_challenger.active_freeze,
        target_events=_target_events, resolve_current_epoch=resolve_current_epoch,
        validate_temporal_guard=_validate_post_result_temporal_guard,
    )


def _preflight_readiness(root: Path, binding: dict[str, Any]) -> dict[str, Any]:
    """Keep the engine's patchable preflight boundary intact."""
    return _build_execution_readiness(
        root, binding, target=TARGET, cutoff=CUTOFF,
        legacy_preflight=preflight.build_preflight,
    )


def _preserved_lock_binding(root: Path) -> dict[str, Any]:
    """Maintain the terminal-engine authority and patch points."""
    return _prospective_lock_binding(
        root, target=TARGET, cutoff=CUTOFF, learned_state=LEARNED_STATE,
        verify_lock=verify_lock, sha256_file=sha256_file,
        load_ledger=champion_challenger.load_ledger,
        active_freeze=champion_challenger.active_freeze,
        target_events=_target_events,
    )


def _runtime_binding(root: Path) -> dict[str, Any]:
    """Preserve externally patchable terminal-engine evidence boundaries."""
    return _resolve_terminal_runtime_binding(
        root, expected_freeze_sha256=EXPECTED_FREEZE_SHA256,
        pre_result_data=PRE_RESULT_DATA, learned_state=LEARNED_STATE,
        active_epoch_binding=_active_epoch_binding,
        current_paths=preflight._current_paths,
        load_ledger=champion_challenger.load_ledger,
        target_events=_target_events,
        preserved_lock_binding=_preserved_lock_binding,
    )

def _contest_max(path: Path) -> int:
    return _result_contest_max(path)


def _target_events(ledger: dict[str, Any], event_type: str) -> list[dict[str, Any]]:
    return _result_target_events(ledger, event_type, TARGET)


def _normalized_primary(payload: dict[str, Any]) -> dict[str, Any]:
    return _result_normalize_primary(payload, TARGET, official_ingest.validate_official_payload)


def _payload_from_normalized(normalized: dict[str, Any]) -> dict[str, Any]:
    return _result_payload_from_normalized(normalized, TARGET)


def _ensure_primary_payload(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return _official_ensure_primary(
        root, payload, primary_payload_file=PRIMARY_PAYLOAD,
        normalize_primary=_normalized_primary, read_json=_read_json,
        atomic_write_json=_atomic_write_json,
    )


def _consensus_rank(document: dict[str, Any]) -> int:
    return _result_consensus_rank(document)


def _ensure_monotonic_consensus(root: Path, document: dict[str, Any]) -> dict[str, Any]:
    return _official_ensure_consensus(
        root, document, target=TARGET, consensus_file=CONSENSUS_FILE,
        consensus_rank=_consensus_rank, read_json=_read_json,
        atomic_write_json=_atomic_write_json,
    )


def _load_existing_official_evidence(root: Path) -> tuple[dict[str, Any], dict[str, Any]] | None:
    return _official_load_existing(
        root, primary_payload_file=PRIMARY_PAYLOAD, consensus_file=CONSENSUS_FILE,
        normalize_primary=_normalized_primary, read_json=_read_json,
    )


def _ensure_ingest(root: Path, payload: dict[str, Any], binding: dict[str, Any] | None = None) -> dict[str, Any]:
    return _official_ingest_guard(
        root, payload, binding, target=TARGET, cutoff=CUTOFF,
        result_data=RESULT_DATA, ingest_proof=INGEST_PROOF,
        normalize_primary=_normalized_primary, read_json=_read_json,
        sha256_file=sha256_file, load_draws=load_draws,
        runtime_binding=_runtime_binding, contest_max=_contest_max,
        ingest=official_ingest.ingest,
    )


def _ensure_adjudication(root: Path, actual_numbers: list[int], binding: dict[str, Any] | None = None) -> dict[str, Any]:
    return _official_adjudication_guard(
        root, actual_numbers, binding, target=TARGET, result_data=RESULT_DATA,
        runtime_binding=_runtime_binding,
        load_ledger=champion_challenger.load_ledger,
        target_events=_target_events, adjudicate=adjudicator.adjudicate,
    )


def _agent_from_prestate(prestate: dict[str, Any], *, target_contest: int) -> SmartSignalAgent:
    return _learned_agent_from_prestate(
        prestate, target_contest=target_contest, agent_factory=SmartSignalAgent,
    )


def _verify_existing_learned_policy(prestate: dict[str, Any], learned: dict[str, Any], target: int) -> None:
    return _learned_verify_existing_policy(
        prestate, learned, target, agent_from_prestate=_agent_from_prestate,
    )


def _ensure_learned_state(root: Path, binding: dict[str, Any] | None = None) -> dict[str, Any]:
    binding = binding or _runtime_binding(root)
    return _learned_ensure_state(
        root, binding, target=TARGET, cutoff=CUTOFF, result_data=RESULT_DATA,
        sha256_file=sha256_file, read_json=_read_json, load_draws=load_draws,
        agent_from_prestate=_agent_from_prestate,
        verify_existing_learned_policy=_verify_existing_learned_policy,
        atomic_write_json=_atomic_write_json,
    )


def _ensure_learning_and_sequence(root: Path, binding: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retain the terminal-engine authoritative dependencies and API."""
    binding = binding or _runtime_binding(root)
    return _ensure_terminal_sequence(
        root, binding, target=TARGET, result_data=RESULT_DATA,
        learning_event=sequential.LEARNING_EVENT, proof_event=sequential.PROOF_EVENT,
        load_ledger=champion_challenger.load_ledger, target_events=_target_events,
        append_learning_update=sequential.append_learning_update,
        append_sequence_proof=sequential.append_sequence_proof,
        validate_target_sequence=sequential.validate_target_sequence,
    )


def _verified_stale_coverage_observations(root: Path, bindings: list[Path]) -> list[dict[str, Any]]:
    """Preserve the terminal engine's external audit and hash patch points."""
    from smart_source_identity import sha256_source_file

    return _resolve_stale_coverage_observations(
        root, bindings, read_json=_read_json, sha256_file=sha256_file,
        sha256_source_file=sha256_source_file,
        coverage_binding_schema=independent_audit.COVERAGE_BINDING_SCHEMA,
        audit_coverage_binding=independent_audit.audit_coverage_binding,
    )


def _degraded_result_audit(root: Path, binding: dict[str, Any],
                           bindings: list[Path]) -> dict[str, Any]:
    """Preserve P14 independent audit hooks without promoting stale coverage."""
    return _build_degraded_result_audit(
        root, binding, bindings, target=TARGET, schema=independent_audit.SCHEMA,
        verified_stale_coverage_observations=_verified_stale_coverage_observations,
        policy_snapshot=independent_audit.policy_snapshot,
        audit_independence=independent_audit.audit_independence,
        audit_prospective_ledger=independent_audit.audit_prospective_ledger,
        audit_deterministic_replay=independent_audit.audit_deterministic_replay,
        load_material_deficiency_registry=independent_audit.load_material_deficiency_registry,
        sha256_json=independent_audit.sha256_json,
    )


def _run_independent_audit(root: Path, binding: dict[str, Any] | None = None) -> dict[str, Any]:
    """Keep terminal evidence callbacks patchable at the engine boundary."""
    binding = binding or _runtime_binding(root)
    return _run_stale_independent_audit(
        root, binding, target=TARGET, audit_filename=INDEPENDENT_AUDIT_FILE,
        coverage_bindings=COVERAGE_BINDINGS,
        invoke_independent_audit=independent_audit.run_independent_audit,
        degraded_result_audit=_degraded_result_audit,
        atomic_write_json=_atomic_write_json,
    )


def _draw_map(path: Path) -> dict[int, tuple[int, ...]]:
    return _result_draw_map(path, official_ingest.BALL_COLUMNS)


def _advance_canonical_result_store(root: Path) -> dict[str, Any]:
    """Preserve terminal engine authority and injectable hash/data operations."""
    return _store_advance(
        root, target=TARGET, cutoff=CUTOFF, result_data=RESULT_DATA,
        result_store_proof=RESULT_STORE_PROOF, draw_map=_draw_map,
        sha256_file=sha256_file, read_json=_read_json,
        atomic_write_json=_atomic_write_json,
    )


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
    # Keep the legacy AST-extracted evaluator directly executable for audit tests.
    from smart_terminal_evaluation import evaluate_terminal_evidence
    return evaluate_terminal_evidence(
        freeze_event=freeze_event,
        freeze=freeze,
        adjudications=_target_events(ledger, "ADJUDICATION"),
        ledger=ledger,
        consensus=consensus,
        audit=audit,
        sequence_validation=sequence_validation,
        target=TARGET,
        cutoff=CUTOFF,
        expected_freeze_sha256=expected_freeze_sha256,
    )

def _promote_terminal_mission(root: Path, evaluation: dict[str, Any], consensus: dict[str, Any], audit: dict[str, Any], sequence: dict[str, Any], binding: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retain terminal engine's verified evaluator and independent proof inputs."""
    return _mission_proof_persist(
        root, evaluation, consensus, audit, sequence, binding,
        target=TARGET, terminal_proof=TERMINAL_PROOF,
        consensus_file=CONSENSUS_FILE,
        independent_audit_file=INDEPENDENT_AUDIT_FILE,
        load_mission_status=load_mission_status,
        write_mission_status=write_mission_status,
        runtime_binding=_runtime_binding,
        sha256_file=sha256_file, mission_sha256_json=mission_sha256_json,
        atomic_write_json=_atomic_write_json,
    )


def _default_operator_fetcher(root: Path) -> Fetcher:
    """Only local operator declaration is used by direct engine entrypoints."""
    from smart_operator_result import fetch as operator_fetch
    return lambda target: operator_fetch(root, target)


def probe(root: str | Path, fetcher: Fetcher | None = None) -> dict[str, Any]:
    """Preserve legacy engine probe interface and runtime patch points."""
    return _probe_terminal_result(
        root, fetcher, target=TARGET, schema=SCHEMA, canonical_root=canonical_root,
        default_operator_fetcher=_default_operator_fetcher,
        runtime_binding=_runtime_binding, sha256_file=sha256_file,
        load_ledger=champion_challenger.load_ledger, target_events=_target_events,
        load_existing_official_evidence=_load_existing_official_evidence,
        preflight_readiness=_preflight_readiness, normalize_primary=_normalized_primary,
    )


def _precheck_historical_freeze_evidence(
    root: Path, ledger: dict[str, Any], *,
    allow_unverified_history: bool = False,
    current_sha256: str | None = None,
) -> dict[str, Any] | None:
    """Preserve engine authority injection and both strict/scoped policies."""
    return _historical_freeze_precheck(
        root, ledger, target=TARGET,
        inspect_freeze_evidence=inspect_freeze_evidence,
        resolve_audit_evidence=independent_audit._resolve_audit_evidence,
        allow_unverified_history=allow_unverified_history,
        current_sha256=current_sha256,
    )


def _unverified_history_audit(root: Path, scope: dict[str, Any]) -> dict[str, Any]:
    """Persist only non-promotable history when current freeze is verified."""
    return _historical_write_unverified_audit(
        root, scope, target=TARGET,
        independent_audit_file=INDEPENDENT_AUDIT_FILE,
        atomic_write_json=_atomic_write_json,
    )


def execute(root: str | Path, fetcher: Fetcher | None = None, *, allow_terminal_write: bool = True) -> dict[str, Any]:
    root = canonical_root(root)
    root = Path(root).resolve()
    if fetcher is None:
        fetcher = _default_operator_fetcher(root)
    binding = _runtime_binding(root)
    adjudications, scoped = _execute_preflight_validate(
        root, binding,
        sha256_file=sha256_file,
        load_ledger=champion_challenger.load_ledger,
        target_events=_target_events,
        historical_precheck=_precheck_historical_freeze_evidence,
        preflight_readiness=_preflight_readiness,
    )
    payload, consensus, waiting = _official_acquire_result(
        root, fetcher, adjudications, target=TARGET, schema=SCHEMA,
        load_existing=_load_existing_official_evidence,
        ensure_primary=_ensure_primary_payload,
        ensure_consensus=_ensure_monotonic_consensus,
    )
    if waiting is not None:
        return waiting

    normalized = _normalized_primary(payload)
    ingest = _ensure_ingest(root, payload, binding=binding)
    adjudication = _ensure_adjudication(root, normalized["numbers"], binding=binding)
    learned = _ensure_learned_state(root, binding=binding)
    sequence_validation = _ensure_learning_and_sequence(root, binding=binding)
    audit = _select_terminal_audit(
        root, scoped, binding,
        independent_audit=_run_independent_audit,
        unverified_audit=_unverified_history_audit,
    )
    result_store = _dispatch_result_store(
        root, binding, epoch_advance=history_advance.advance_completed_epoch,
        canonical_advance=_advance_canonical_result_store,
    )
    ledger = champion_challenger.load_ledger(binding["ledger"])
    consensus = _read_json(root / CONSENSUS_FILE)
    evaluation = evaluate_terminal_rule(root, ledger, consensus, audit, sequence_validation, binding=binding)

    mission = load_mission_status(root / "SMART_MISSION_STATUS.json", root=root)
    if evaluation["eligible_for_mission_proven"] and allow_terminal_write:
        mission = _promote_terminal_mission(root, evaluation, consensus, audit, sequence_validation, binding=binding)

    status = _build_terminal_execution_status(
        schema=SCHEMA, target=TARGET,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        normalized=normalized, consensus=consensus, ingest=ingest,
        adjudication=adjudication, learned=learned,
        sequence_validation=sequence_validation, audit=audit,
        result_store=result_store, evaluation=evaluation, mission=mission,
    )
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
        overrides = _epoch_runtime_names(active, selected)
        names = tuple(overrides)
        saved = {name: globals()[name] for name in names}
        try:
            globals().update(overrides)
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
