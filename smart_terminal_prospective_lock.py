"""Preserved pre-draw authority lock binding for terminal recovery.

Only reads/validates evidence supplied by the canonical engine; it does not
change freeze, predictive weights, or adjudication events.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def preserved_lock_binding(
    root: Path, *, target: int, cutoff: int, learned_state: str,
    verify_lock: Callable, sha256_file: Callable, load_ledger: Callable,
    active_freeze: Callable, target_events: Callable,
) -> dict[str, Any]:
    root = Path(root).resolve()
    lock_path = root / "SMART_PROSPECTIVE_AUTHORITY_LOCK.json"
    lock = verify_lock(lock_path)
    auth = lock.get("experiment_authority", {})
    if int(auth.get("target_contest", -1)) != target or int(auth.get("cutoff_contest", -1)) != cutoff:
        raise ValueError("preserved prospective lock target/cutoff mismatch")
    if auth.get("eligible_for_scientific_adjudication") is not True:
        raise ValueError("preserved prospective lock lacks scientific adjudication authority")
    if auth.get("eligible_to_prove_post_freeze_engineering_version") is not False:
        raise ValueError("preserved prospective lock could falsely credit post-freeze engineering")
    if auth.get("immutable_until_adjudication") is not True:
        raise ValueError("preserved prospective lock is not immutable until adjudication")

    freeze = root / str(auth.get("freeze_file", ""))
    data = root / str(auth.get("data_file", ""))
    state = root / str(auth.get("signal_state_file", ""))
    ledger_path = root / str(auth.get("ledger_file", ""))
    for path, expected in (
        (freeze, str(auth.get("freeze_sha256", ""))),
        (data, str(auth.get("data_sha256", ""))),
        (state, str(auth.get("signal_state_sha256", ""))),
    ):
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"preserved prospective lock dependency mismatch: {path.name}")
    if not ledger_path.is_file():
        raise ValueError("preserved prospective signal ledger missing")
    ledger = load_ledger(ledger_path)
    active = active_freeze(ledger, target)
    if active is None or active.get("freeze_sha256") != auth.get("freeze_sha256"):
        raise ValueError("preserved prospective lock no longer resolves to the active frozen attempt")
    adjudications = target_events(ledger, "ADJUDICATION")
    if len(adjudications) > 1:
        raise ValueError("multiple 3054 adjudications are forbidden")
    if not adjudications:
        if sha256_file(ledger_path) != auth.get("ledger_sha256"):
            raise ValueError("unadjudicated preserved signal ledger hash changed")
    else:
        adjudication = adjudications[0]
        if adjudication.get("freeze_sha256") != auth.get("freeze_sha256"):
            raise ValueError("stored adjudication is not bound to the preserved freeze")
        actual = [int(x) for x in adjudication.get("actual_numbers", [])]
        if len(actual) != 6 or len(set(actual)) != 6 or any(x < 1 or x > 60 for x in actual):
            raise ValueError("stored adjudication actual numbers are invalid")

    return {
        "mode": "LOCKED_PROSPECTIVE_AUTHORITY",
        "freeze": freeze,
        "freeze_sha256": str(auth["freeze_sha256"]),
        "ledger": ledger_path,
        "state": state,
        "data": data,
        "learned": root / learned_state,
    }