"""Fail-closed official ingest and adjudication dispatch for frozen target epochs.

All identity, validation, sequencing and operator authorization remain supplied
by the canonical terminal engine; no prediction or policy weights are changed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable


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
    if output.exists() or proof_path.exists():
        if not output.exists() or not proof_path.exists():
            raise ValueError("official result ingest is partially present")
        proof = read_json(proof_path)
        if int(proof.get("target_contest", -1)) != target or proof.get("actual_numbers") != normalized["numbers"]:
            raise ValueError("existing official ingest proof conflicts with official result")
        if proof.get("output_sha256") != sha256_file(output):
            raise ValueError("existing official ingest output hash mismatch")
        _, contests = load_draws(output)
        if int(contests[-1]) != target:
            raise ValueError("existing official ingest output does not end at target")
        return proof
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
            "target_contest": target,
            "actual_numbers": event["actual_numbers"],
            "champion_hits": int(event["champion_hits"]),
            "challenger_hits": int(event["challenger_hits"]),
            "e_value_after": float(event["e_value_after"]),
        }
    cwd = Path.cwd()
    try:
        os.chdir(root)
        result = adjudicate(root / result_data, target, ledger_path)
    finally:
        os.chdir(cwd)
    result["status"] = "ADJUDICATED"
    return result