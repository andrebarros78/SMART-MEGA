"""Fail-closed read-only replay of historical ingest and adjudication authority.

Helpers cannot ingest or adjudicate. The terminal dispatcher preserves the
original first-write boundary, callback order and numerical evidence contracts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def verified_existing_ingest(
    output: Path, proof_path: Path, normalized: dict[str, Any], *,
    target: int, read_json: Callable, sha256_file: Callable,
    load_draws: Callable,
) -> dict[str, Any] | None:
    """Replay complete verified ingest, rejecting partial or changed artifacts."""
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
    return None


def replay_existing_adjudication(
    existing: list[dict[str, Any]], actual_numbers: list[int],
    expected_freeze_sha256: str, target: int,
) -> dict[str, Any] | None:
    """Preserve one immutable adjudication, or authorize first-time dispatch."""
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
    return None
