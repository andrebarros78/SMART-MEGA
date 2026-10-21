"""Bounded fast prefilter for historical video checkpoints.

The index is a candidate list, not an authority. The original verified reader
must still validate every selected checkpoint, and production remains blocked.
"""
from __future__ import annotations
from pathlib import Path


def candidate_checkpoints(root: str | Path, target_contest: str, *, limit: int = 512) -> list[Path]:
    """Identify earlier numeric-contest checkpoints without opening media or files."""
    target = str(target_contest)
    if not target.isascii() or not target.isdecimal() or int(target) <= 0:
        raise ValueError("INVALID_TARGET_CONTEST")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 512:
        raise ValueError("INVALID_CHECKPOINT_LIMIT")
    directory = Path(root)
    if not directory.is_dir() or directory.is_symlink():
        return []
    matches = []
    for item in directory.glob("contest_[0-9]*.json"):
        ident = item.stem.removeprefix("contest_")
        if ident.isascii() and ident.isdecimal() and 1 <= len(ident) <= 12:
            n = int(ident)
            if n < int(target):
                matches.append((n, item))
    matches.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in matches[:limit]]


def learning_metrics(*, discovered: int, eligible: int, reused: int, elapsed_ms: float) -> dict:
    """Metrics are descriptive only. Never grant source access or predictive weight."""
    if min(discovered, eligible, reused, elapsed_ms) < 0 or eligible > discovered or reused > eligible:
        raise ValueError("INVALID_METRICS")
    return {
        "schema": "SMART_VISUAL_LEARNING_EFFICIENCY_V1",
        "discovered_checkpoints": discovered,
        "eligible_checkpoints": eligible,
        "reused_checkpoints": reused,
        "elapsed_ms": elapsed_ms,
        "predictive_weight": 0.0,
        "predictive_evidence": "NOT_ESTABLISHED",
    }
