"""Separate current-epoch operational integrity from historical scientific coverage.

An absent prior freeze can never become evidence by inference or reconstruction.
This gate does not grant scientific promotion even when all files verify.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def inspect_freeze_evidence(
    root: Path,
    ledger: dict[str, Any],
    target: int,
    verifier: Callable[[Path, str, str, str], Any],
    *,
    current_sha256: str | None = None,
) -> dict[str, Any]:
    """Check the active freeze strictly; classify missing prior freezes as unverified.

    ``verifier`` is the repository's immutable hash/path evidence resolver. No
    metadata or original event is changed. This is a scoped operational gate,
    NOT an independent prospective or statistical certification.
    """
    root = Path(root).resolve()
    target = int(target)
    events = ledger.get("events")
    if not isinstance(events, list):
        raise ValueError("historical ledger events invalid")
    adjudicated = {
        int(event["target_contest"])
        for event in events
        if isinstance(event, dict) and event.get("event_type") == "ADJUDICATION"
    }
    current = [event for event in events
               if isinstance(event, dict) and event.get("event_type") == "FREEZE"
               and int(event.get("target_contest", -1)) == target
               and (current_sha256 is None or event.get("freeze_sha256") == current_sha256)]
    if len(current) != 1:
        raise ValueError("current target requires exactly one hash-bound active freeze")
    event = current[0]
    try:
        verifier(root, str(event.get("freeze_file", "")), str(event.get("freeze_sha256", "")), "frozen artifact")
    except (ValueError, OSError) as exc:
        raise ValueError(f"current active freeze evidence unavailable for contest {target}") from exc

    unverified = set()
    for event in events:
        if not isinstance(event, dict) or event.get("event_type") != "FREEZE":
            continue
        contest = int(event.get("target_contest", -1))
        if contest == target or contest not in adjudicated:
            continue
        try:
            verifier(root, str(event.get("freeze_file", "")), str(event.get("freeze_sha256", "")), "frozen artifact")
        except (ValueError, OSError):
            unverified.add(contest)
    missing = sorted(unverified)
    return {
        "schema": "SMART_SCOPED_HISTORICAL_FREEZE_EVIDENCE_1",
        "status": "DEGRADED_HISTORICAL_EVIDENCE_MISSING" if missing else "PASS_SCOPED_FREEZE_EVIDENCE",
        "target_contest": target,
        "active_freeze_verified": True,
        "unverified_contests": missing,
        "historical_verified": not bool(missing),
        "promotion_authority": False,
        "scientific_audit_substituted": False,
        "ledger_mutated": False,
    }
