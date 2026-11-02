"""Fail-closed official ingest and adjudication dispatch for frozen target epochs.

All identity, validation, sequencing and operator authorization remain supplied
by the canonical terminal engine; no prediction or policy weights are changed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from smart_terminal_idempotency import (
    verified_existing_ingest, replay_existing_adjudication,
)


def ensure_ingest(
    root: Path, payload: dict[str, Any], binding: dict[str, Any] | None = None, *,
    target: int, cutoff: int, result_data: str, ingest_proof: str,
    normalize_primary: Callable, read_json: Callable, sha256_file: Callable,
    load_draws: Callable, runtime_binding: Callable, contest_max: Callable,
    ingest: Callable,
) -> dict[str, Any]:
    output = root / result_data
    proof_path = root / ingest_proof
    normalized = normalize_primary(payload)
    existing = verified_existing_ingest(
        output, proof_path, normalized, target=target,
        read_json=read_json, sha256_file=sha256_file, load_draws=load_draws,
    )
    if existing is not None:
        return existing
    binding = binding or runtime_binding(root)
    source = binding["data"]
    if contest_max(source) != cutoff:
        raise ValueError("active pre-result dataset must end at cutoff before first target ingest")
    return ingest(source, output, proof_path, target, payload)


def ensure_adjudication(
    root: Path, actual_numbers: list[int], binding: dict[str, Any] | None = None, *,
    target: int, result_data: str, runtime_binding: Callable,
    load_ledger: Callable, target_events: Callable, adjudicate: Callable,
) -> dict[str, Any]:
    binding = binding or runtime_binding(root)
    ledger_path = binding["ledger"]
    expected_freeze_sha256 = binding["freeze_sha256"]
    ledger = load_ledger(ledger_path)
    existing = target_events(ledger, "ADJUDICATION")
    previous = replay_existing_adjudication(
        existing, actual_numbers, expected_freeze_sha256, target,
    )
    if previous is not None:
        return previous
    cwd = Path.cwd()
    try:
        os.chdir(root)
        result = adjudicate(root / result_data, target, ledger_path)
    finally:
        os.chdir(cwd)
    result["status"] = "ADJUDICATED"
    return result
