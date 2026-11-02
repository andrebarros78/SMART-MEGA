"""Immutable official-result payload and monotonic evidence storage.

Only the original caller controls result authority, normalization and persistence.
The predicates here preserve prior arbitration and conflict rejection behavior.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def ensure_primary_payload(
    root: Path, payload: dict[str, Any], *,
    primary_payload_file: str,
    normalize_primary: Callable,
    read_json: Callable, atomic_write_json: Callable,
) -> dict[str, Any]:
    path = root / primary_payload_file
    normalized = normalize_primary(payload)
    if path.exists():
        existing = read_json(path)
        if normalize_primary(existing) != normalized:
            raise ValueError("official primary payload conflicts with immutable first observation")
        return existing
    atomic_write_json(path, payload)
    return payload


def ensure_monotonic_consensus(
    root: Path, document: dict[str, Any], *,
    target: int, consensus_file: str, consensus_rank: Callable,
    read_json: Callable, atomic_write_json: Callable,
) -> dict[str, Any]:
    if int(document.get("target_contest", -1)) != target:
        raise ValueError("official consensus target mismatch")
    primary = document.get("primary", {})
    if primary.get("validated") is not True:
        raise ValueError("official consensus primary channel is not validated")
    path = root / consensus_file
    if not path.exists():
        atomic_write_json(path, document)
        return document
    existing = read_json(path)
    if (
        existing.get("primary", {}).get("numbers") != primary.get("numbers")
        or existing.get("primary", {}).get("draw_date") != primary.get("draw_date")
    ):
        raise ValueError("official consensus primary observation changed")
    if consensus_rank(document) < consensus_rank(existing):
        return existing
    if consensus_rank(document) == consensus_rank(existing) and document.get("status") == existing.get("status"):
        return existing
    atomic_write_json(path, document)
    return document


def load_existing_official_evidence(
    root: Path, *, primary_payload_file: str, consensus_file: str,
    normalize_primary: Callable, read_json: Callable,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    payload_path = root / primary_payload_file
    consensus_path = root / consensus_file
    if not payload_path.exists() and not consensus_path.exists():
        return None
    if not payload_path.exists() or not consensus_path.exists():
        raise ValueError("official evidence is partially present")
    payload = read_json(payload_path)
    consensus = read_json(consensus_path)
    normalized = normalize_primary(payload)
    if consensus.get("primary", {}).get("numbers") != normalized["numbers"]:
        raise ValueError("stored official payload and consensus disagree")
    if consensus.get("primary", {}).get("draw_date") != normalized["draw_date"]:
        raise ValueError("stored official payload and consensus date disagree")
    return payload, consensus


def acquire_official_result(
    root: Path, fetcher: Callable, adjudications: list[dict[str, Any]], *,
    target: int, schema: str, load_existing: Callable,
    ensure_primary: Callable, ensure_consensus: Callable,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    existing = load_existing(root)
    try:
        fresh_payload, fresh_consensus = fetcher(target)
    except Exception as exc:
        if existing is None and not adjudications:
            return None, None, {
                "schema": schema,
                "target_contest": target,
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
        payload = ensure_primary(root, fresh_payload)
        consensus = ensure_consensus(root, fresh_consensus)

    return payload, consensus, None
