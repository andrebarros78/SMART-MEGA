"""Read-only recovery validation for operator-controlled SMART-MEGA.

Batch selection and adjudication lineage verification cannot authorize a card,
rewrite a result, advance a historical epoch, or promote a predictive model.
The operator supplies the existing evidence readers as explicit collaborators.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def select_recovery_batch(root: Path, payload_file: str | Path | None) -> Path | None:
    """Select a bounded project-relative official batch without opening it."""
    if payload_file is None:
        return None
    incoming = Path(payload_file)
    if incoming.is_absolute() or not incoming.parts or ".." in incoming.parts:
        raise ValueError("recovery official batch must be project-relative")
    candidate = root
    for part in incoming.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError("recovery official batch symbolic link forbidden")
    if not candidate.is_file() or not candidate.resolve().is_relative_to(root):
        raise ValueError("recovery official batch file absent or outside repository")
    if candidate.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("recovery official batch file exceeds size limit")
    return candidate


def verify_adjudication_lineage(
    root: Path,
    active: dict[str, Any],
    target: int,
    frozen_sha256: str,
    observation: dict[str, Any],
    *,
    load_ledger: Callable,
    active_freeze: Callable,
    read_authority: Callable,
) -> bool:
    """Accept an immutable completed adjudication only with operator evidence.

    This is not a fresh prospective-readiness certification; it cannot upgrade
    original timing or source authority, and cannot alter any result or weight.
    """
    paths = active.get("state_paths")
    if not isinstance(paths, dict) or not paths.get("ledger"):
        return False
    path = Path(str(paths["ledger"]))
    if path.is_absolute() or ".." in path.parts:
        return False
    ledger_path = root / path
    if (not ledger_path.is_file() or ledger_path.is_symlink()
            or not ledger_path.resolve().is_relative_to(root)):
        return False
    if observation.get("result_input_authority") != "OPERATOR":
        return False
    ledger = load_ledger(ledger_path)
    freeze = active_freeze(ledger, target)
    if not isinstance(freeze, dict) or freeze.get("freeze_sha256") != frozen_sha256:
        return False
    # Malformed operator adjudication entries invalidate the lineage;
    # they must not crash recovery or be ignored beside a valid entry.
    events = []
    for row in ledger.get("events", []):
        if not isinstance(row, dict) or row.get("event_type") != "ADJUDICATION":
            continue
        try:
            event_target = int(row.get("target_contest", -1))
        except (TypeError, ValueError, OverflowError):
            return False
        if event_target == target:
            events.append(row)
    if len(events) != 1:
        return False
    adjudication = events[0]
    if (adjudication.get("freeze_sha256") != frozen_sha256
            or adjudication.get("retroactive_rewrite") is not False
            or adjudication.get("actual_numbers") != observation.get("actual_numbers")):
        return False
    authority = read_authority(root, target)
    return (authority.get("source") == "OPERATOR"
            and authority.get("actual_numbers") == adjudication["actual_numbers"]
            and authority.get("predictive_weight_authorized") is False)
