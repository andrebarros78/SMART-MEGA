"""Previous completed epoch reconciliation used by operator preparation.

The operator remains responsible for authorization, certification, pre-draw
guards, transaction journaling, and epoch persistence. All collaborators are
bound from the live operator call so existing guards remain authoritative.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def reconcile_previous_epoch(
    root: Path,
    active_path: Path,
    *,
    verify_active_epoch: Callable,
    load_ledger: Callable,
    reconcile_completed_epoch_ledger: Callable,
    advance_completed_epoch: Callable,
    authorized_pytest_sandbox: Callable,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Reconcile only adjudicated history; never supersede an unresolved draw."""
    reconciliation = None
    result_store_reconciliation = None
    if active_path.exists():
        try:
            previous_active = verify_active_epoch(active_path)
        except Exception:
            if authorized_pytest_sandbox(root):
                raise FileExistsError("active epoch already exists")
            raise
        previous_ledger = root / previous_active["state_paths"]["ledger"]
        previous_target = int(previous_active["target_contest"])
        previous_events = load_ledger(previous_ledger).get("events", [])
        if not any(ev.get("event_type") == "ADJUDICATION" and int(ev.get("target_contest", -1)) == previous_target for ev in previous_events):
            raise ValueError("cannot supersede an unresolved prospective attempt; use the explicit pre-result withdrawal/unfreeze path")
        reconciliation = reconcile_completed_epoch_ledger(root / "SMART_SIGNAL_LEDGER.json", previous_ledger, previous_target, root=root)
        result_store_reconciliation = advance_completed_epoch(root, previous_active)
    return reconciliation, result_store_reconciliation
