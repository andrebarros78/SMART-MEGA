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


def write_unverified_history_audit(
    root: Path, scope: dict[str, Any], *, target: int,
    independent_audit_file: str, atomic_write_json: Callable,
) -> dict[str, Any]:
    """Persist incomplete scientific audit without silently promoting history."""
    if (scope.get("status") != "DEGRADED_HISTORICAL_EVIDENCE_MISSING"
            or scope.get("active_freeze_verified") is not True
            or scope.get("promotion_authority") is not False
            or not scope.get("unverified_contests")):
        raise ValueError("unverified-history audit requires verified current freeze and real history gaps")
    result = {
        "schema": "SMART_HISTORICAL_EVIDENCE_NONPROMOTION_AUDIT_1",
        "status": "DEGRADED_HISTORICAL_EVIDENCE_MISSING",
        "target_contest": target,
        "historical_verified": False,
        "scientific_coverage_certified": False,
        "independent_full_audit_completed": False,
        "promotion_authority": False,
        "terminal_promotion_permitted": False,
        "active_freeze_verified": True,
        "unverified_contests": list(scope["unverified_contests"]),
        "prospective_ledger": {
            "status": "NOT_PROVEN_HISTORICAL_EVIDENCE_MISSING",
            "pair_count": None,
            "no_future_leakage": False,
        },
    }
    atomic_write_json(root / independent_audit_file, result)
    return result

def select_terminal_audit(
    root: Path, scoped: dict[str, Any] | None, binding: dict[str, Any], *,
    independent_audit: Callable, unverified_audit: Callable,
) -> dict[str, Any]:
    """Preserve strict independent auditing unless historical gaps require a nonpromotable report."""
    if scoped is not None and scoped["unverified_contests"]:
        return unverified_audit(root, scoped)
    return independent_audit(root, binding=binding)