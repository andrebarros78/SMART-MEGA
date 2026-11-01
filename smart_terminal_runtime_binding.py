"""Read-only terminal authority dispatch and legacy compatibility.

Selects among frozen active epoch, verified preflight, and preserved lock.
Predictions, weights, and frozen outcomes are never mutated in this module.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def resolve_runtime_binding(
    root: Path, *, expected_freeze_sha256: str | None,
    pre_result_data: str, learned_state: str,
    active_epoch_binding: Callable, current_paths: Callable,
    load_ledger: Callable, target_events: Callable,
    preserved_lock_binding: Callable,
) -> dict[str, Any]:
    root = Path(root).resolve()
    if isinstance(expected_freeze_sha256, str) and len(expected_freeze_sha256) == 64:
        return {
            "mode": "EXPLICIT_LEGACY_TEST_OVERRIDE",
            "freeze": root / "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json",
            "freeze_sha256": expected_freeze_sha256,
            "ledger": root / "SMART_SIGNAL_LEDGER.json",
            "state": root / "SMART_SIGNAL_STATE_3054_V2.json",
            "data": root / pre_result_data,
            "learned": root / learned_state,
        }
    active_binding = active_epoch_binding(root)
    if active_binding is not None:
        return active_binding
    try:
        paths = current_paths(root)
    except Exception:
        ledger_path = root / "SMART_SIGNAL_LEDGER.json"
        if ledger_path.is_file():
            ledger = load_ledger(ledger_path)
            if len(target_events(ledger, "ADJUDICATION")) == 1:
                return preserved_lock_binding(root)
        raise
    freeze_sha = str(paths.get("authority_freeze_sha256", ""))
    if len(freeze_sha) != 64:
        raise ValueError("terminal executor freeze authority hash missing")
    mode = "ACTIVE_EPOCH" if paths.get("adjudication_authority_mode") == "ACTIVE_EPOCH_FROZEN" else "LOCKED_PROSPECTIVE_AUTHORITY"
    return {
        "mode": mode,
        "freeze": paths["freeze"],
        "freeze_sha256": freeze_sha,
        "ledger": paths["ledger"],
        "state": paths["state"],
        "data": paths["data"],
        "learned": paths["ledger"].parent / learned_state if mode == "ACTIVE_EPOCH" else root / learned_state,
    }