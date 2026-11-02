"""Coordinate post-result evidence, guarded mission decision and status persistence.

All scientific authority remains with injected evaluator and promotion implementation.
The coordinator never changes the eligibility policy or constructs new proof.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def finalize_terminal_result(
    root: Path, binding: dict[str, Any], *,
    normalized: dict[str, Any], ingest: dict[str, Any],
    adjudication: dict[str, Any], learned: dict[str, Any],
    sequence_validation: dict[str, Any], audit: dict[str, Any],
    result_store: dict[str, Any], schema: str, target: int,
    status_file: str, consensus_file: str, allow_terminal_write: bool,
    load_ledger: Callable, read_json: Callable, evaluate_terminal_rule: Callable,
    load_mission_status: Callable, promote_terminal_mission: Callable,
    build_terminal_execution_status: Callable, atomic_write_json: Callable,
    current_time_utc: Callable,
) -> dict[str, Any]:
    """Preserve strict evaluation -> mission -> status ordering, with no fallback."""
    ledger = load_ledger(binding["ledger"])
    consensus = read_json(root / consensus_file)
    evaluation = evaluate_terminal_rule(
        root, ledger, consensus, audit, sequence_validation, binding=binding
    )
    mission = load_mission_status(root / "SMART_MISSION_STATUS.json", root=root)
    if evaluation["eligible_for_mission_proven"] and allow_terminal_write:
        mission = promote_terminal_mission(
            root, evaluation, consensus, audit, sequence_validation, binding=binding
        )
    status = build_terminal_execution_status(
        schema=schema, target=target, created_at_utc=current_time_utc(),
        normalized=normalized, consensus=consensus, ingest=ingest,
        adjudication=adjudication, learned=learned,
        sequence_validation=sequence_validation, audit=audit,
        result_store=result_store, evaluation=evaluation, mission=mission,
    )
    atomic_write_json(root / status_file, status)
    return status
