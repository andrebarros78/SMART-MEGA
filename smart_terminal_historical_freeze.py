"""Precheck immutable freeze evidence for scoped and strict terminal epochs.

Historical gaps are never treated as scientific promotion authority.
The caller supplies the current target and independent evidence resolver.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def precheck_historical_freeze_evidence(
    root: Path, ledger: dict[str, Any], *,
    target: int, inspect_freeze_evidence: Callable,
    resolve_audit_evidence: Callable,
    allow_unverified_history: bool = False,
    current_sha256: str | None = None,
) -> dict[str, Any] | None:
    """Guard current freeze; retain missing prior freezes as unverified only when scoped.

    The legacy/independent proof path keeps its original strict behavior.
    """
    if allow_unverified_history:
        return inspect_freeze_evidence(
            root, ledger, target, resolve_audit_evidence,
            current_sha256=current_sha256,
        )
    targets = {target}
    targets.update(
        int(event["target_contest"])
        for event in ledger.get("events", [])
        if event.get("event_type") == "ADJUDICATION"
    )
    for event in ledger.get("events", []):
        if event.get("event_type") != "FREEZE":
            continue
        contest = int(event.get("target_contest", -1))
        if contest not in targets:
            continue
        try:
            resolve_audit_evidence(
                root, str(event.get("freeze_file", "")),
                str(event.get("freeze_sha256", "")), "frozen artifact"
            )
        except (ValueError, OSError) as exc:
            raise ValueError(
                f"historical freeze evidence unavailable for contest {contest}"
            ) from exc
    return None