"""Read-only integrity checks and status policy for an active operator epoch.

The caller retains canonical root selection, certification verification,
pre-draw schedule authority and all mutations. This module observes artifacts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def active_epoch_integrity_checks(
    root: Path,
    active: dict[str, Any],
    target: int,
    *,
    sha256_file: Callable[[Path], str],
    load_ledger: Callable[[Path], dict[str, Any]],
) -> dict[str, bool]:
    root = Path(root)
    paths = active.get("state_paths") or {}
    data_path = root / str(active.get("data_file") or "")
    ledger_path = root / str(paths.get("ledger") or "")
    freeze_path = root / str(paths.get("freeze") or "")
    canonical_path = root / str(active.get("canonical_source_file") or "Mega-Sena.xlsx")
    ledger_valid = False
    events = []
    if ledger_path.is_file():
        try:
            ledger_doc = load_ledger(ledger_path)
            events = ledger_doc.get("events", [])
            ledger_valid = isinstance(events, list)
        except Exception:
            ledger_valid = False
            events = []
    target_events_absent = not any(
        isinstance(ev, dict) and int(ev.get("target_contest", -1)) == target
        for ev in events
    )
    integrity_checks = {
        "immutable_history_snapshot_declared": active.get("immutable_history_snapshot") is True,
        "cutoff_matches_target_minus_one": int(active.get("cutoff_contest", -1)) == target - 1,
        "result_not_used": active.get("result_used") is False,
        "data_snapshot_present": data_path.is_file(),
        "data_snapshot_hash_match": data_path.is_file() and sha256_file(data_path) == active.get("data_sha256"),
        "canonical_source_present": canonical_path.is_file(),
        "canonical_source_unchanged_since_prepare": canonical_path.is_file() and sha256_file(canonical_path) == active.get("canonical_source_sha256_at_prepare"),
        "ledger_present": ledger_path.is_file(),
        "ledger_valid": ledger_valid,
        "ledger_seed_hash_match": ledger_path.is_file() and sha256_file(ledger_path) == active.get("canonical_ledger_seed_sha256"),
        "target_events_absent": target_events_absent,
        "freeze_artifact_absent": not freeze_path.is_file(),
        "freeze_authority_absent": active.get("freeze_authority") is None,
    }
    return integrity_checks


def classify_active_epoch(
    active: dict[str, Any],
    current_certification_sha256: str,
    integrity_checks: dict[str, bool],
) -> tuple[str, str | None, bool, bool]:
    active_certification_sha256 = str(active.get("product_certification_sha256") or "")
    certification_matches = active_certification_sha256 == str(current_certification_sha256)
    integrity_ok = all(integrity_checks.values())
    if not certification_matches:
        status = "REPREPARE_REQUIRED"
        reason = "ACTIVE_EPOCH_PRODUCT_CERTIFICATION_STALE"
    elif not integrity_ok:
        status = "BLOCKED_INTEGRITY"
        reason = "ACTIVE_EPOCH_INTEGRITY_CHECK_FAILED"
    else:
        status = "READY_TO_FREEZE" if active.get("status") == "RESET_READY" else str(active.get("status") or "ACTIVE")
        reason = None
    return status, reason, certification_matches, integrity_ok
