"""Resolve and verify frozen terminal evidence before pure scientific evaluation.

The engine injects all authority, hash, ledger and evaluator dependencies.
This layer cannot promote scientific status or modify source evidence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def evaluate_verified_terminal_evidence(
    root: Path, ledger: dict[str, Any], consensus: dict[str, Any],
    audit: dict[str, Any], sequence_validation: dict[str, Any],
    binding: dict[str, Any] | None = None, *,
    target: int, cutoff: int, active_freeze: Callable,
    runtime_binding: Callable, sha256_file: Callable,
    read_json: Callable, target_events: Callable,
    evaluate_terminal_evidence: Callable,
) -> dict[str, Any]:
    """Preserve terminal freeze identity and fail-closed hash validation."""
    freeze_event = active_freeze(ledger, target)
    if freeze_event is None:
        raise ValueError("active 3054 freeze is missing")
    freeze_path = Path(str(freeze_event["freeze_file"]))
    if not freeze_path.is_absolute():
        freeze_path = root / freeze_path
    binding = binding or runtime_binding(root)
    expected_freeze_sha256 = binding["freeze_sha256"]
    if not freeze_path.is_file() or sha256_file(freeze_path) != expected_freeze_sha256:
        raise ValueError("active target freeze artifact hash mismatch")
    if binding["mode"] == "ACTIVE_EPOCH" and freeze_path.resolve() != Path(binding["freeze"]).resolve():
        raise ValueError("ledger freeze path differs from active epoch authority")
    freeze = read_json(freeze_path)
    return evaluate_terminal_evidence(
        freeze_event=freeze_event,
        freeze=freeze,
        adjudications=target_events(ledger, "ADJUDICATION"),
        ledger=ledger,
        consensus=consensus,
        audit=audit,
        sequence_validation=sequence_validation,
        target=target,
        cutoff=cutoff,
        expected_freeze_sha256=expected_freeze_sha256,
    )
