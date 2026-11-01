"""Frozen active-epoch binding for the terminal executor.

Read-only validation of file hashes, the ledger, freeze authority and
post-result adjudication before selecting the terminal execution mode.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def active_epoch_binding(
    root: Path, *, target: int, cutoff: int, learned_state: str,
    verify_active_epoch: Callable, project_local: Callable,
    sha256_file: Callable, read_json: Callable, load_ledger: Callable,
    active_freeze: Callable, target_events: Callable,
    resolve_current_epoch: Callable, validate_temporal_guard: Callable,
) -> dict[str, Any] | None:
    root = Path(root).resolve()
    active_path = root / "SMART_ACTIVE_EPOCH.json"
    if not active_path.is_file():
        return None
    active = verify_active_epoch(active_path)
    if int(active.get("target_contest", -1)) != int(target):
        return None
    if int(active.get("cutoff_contest", -1)) != int(cutoff) or cutoff != target - 1:
        raise ValueError("active epoch target/cutoff mismatch")
    if active.get("status") != "FROZEN" or active.get("result_used") is not False:
        raise ValueError("active epoch is not a frozen authority")
    state_paths = active.get("state_paths")
    if not isinstance(state_paths, dict):
        raise ValueError("active epoch state paths missing")
    freeze = project_local(root, str(state_paths.get("freeze", "")), "active freeze")
    ledger = project_local(root, str(state_paths.get("ledger", "")), "active ledger")
    state = project_local(root, str(state_paths.get("state", "")), "active state")
    data = project_local(root, str(active.get("data_file", "")), "active cutoff data")
    for path, label in ((freeze, "freeze"), (ledger, "ledger"), (state, "state"), (data, "cutoff data")):
        if not path.is_file():
            raise ValueError(f"active epoch {label} missing")
    freeze_auth = active.get("freeze_authority") if isinstance(active.get("freeze_authority"), dict) else {}
    expected_freeze = str(freeze_auth.get("sha256") or "")
    if len(expected_freeze) != 64 or sha256_file(freeze) != expected_freeze:
        raise ValueError("active epoch freeze hash mismatch")
    if int(freeze_auth.get("target_contest", -1)) != target or int(freeze_auth.get("cutoff_contest", -1)) != cutoff:
        raise ValueError("active epoch freeze authority target/cutoff mismatch")
    if str(active.get("data_sha256", "")) != sha256_file(data):
        raise ValueError("active epoch cutoff data hash mismatch")
    state_auth = active.get("learning_state_authority") if isinstance(active.get("learning_state_authority"), dict) else {}
    if state_auth.get("sha256") and str(state_auth.get("sha256")) != sha256_file(state):
        raise ValueError("active epoch learning state hash mismatch")
    freeze_doc = read_json(freeze)
    if int(freeze_doc.get("target_contest", -1)) != target or int(freeze_doc.get("cutoff_contest", -1)) != cutoff:
        raise ValueError("active epoch freeze document target/cutoff mismatch")
    if freeze_doc.get("frozen_before_result") is not True or freeze_doc.get("causal_cutoff") is not True:
        raise ValueError("active epoch freeze is not causally pre-result")
    ledger_doc = load_ledger(ledger)
    freeze_event = active_freeze(ledger_doc, target)
    if freeze_event is None or freeze_event.get("freeze_sha256") != expected_freeze:
        raise ValueError("active epoch ledger does not preserve the authoritative freeze")
    adjudications = target_events(ledger_doc, "ADJUDICATION")
    if len(adjudications) > 1:
        raise ValueError("multiple target adjudications are forbidden")
    if not adjudications:
        current = resolve_current_epoch(root)
        if current.get("status") != "FROZEN" or int(current.get("target_contest", -1)) != int(target):
            raise ValueError("current epoch contract does not match terminal target")
        if current.get("freeze_authority_present") is not True or current.get("generation_proof_valid") is not True:
            raise ValueError("current epoch lacks frozen generation authority")
        if str(current.get("freeze_sha256") or "") != expected_freeze:
            raise ValueError("current epoch freeze differs from active authority")
        expected_ledger = str(active.get("ledger_sha256") or "")
        if len(expected_ledger) == 64 and sha256_file(ledger) != expected_ledger:
            raise ValueError("unadjudicated active ledger hash changed")
        mode = "ACTIVE_EPOCH"
    else:
        adjudication = adjudications[0]
        if adjudication.get("freeze_sha256") != expected_freeze:
            raise ValueError("post-result adjudication is not bound to the authoritative freeze")
        actual = [int(x) for x in adjudication.get("actual_numbers", [])]
        if len(actual) != 6 or len(set(actual)) != 6 or any(x < 1 or x > 60 for x in actual):
            raise ValueError("post-result adjudication numbers are invalid")
        if adjudication.get("retroactive_rewrite") is not False:
            raise ValueError("post-result adjudication permits retroactive rewrite")
        validate_temporal_guard(active, freeze_doc, target)
        current = {
            "status": "POST_RESULT_RECOVERY",
            "target_contest": target,
            "freeze_authority_present": True,
            "generation_proof_valid": False,
            "historical_pre_result_authority_preserved": True,
            "freeze_sha256": expected_freeze,
        }
        mode = "ACTIVE_EPOCH_POST_ADJUDICATION_RECOVERY"
    return {
        "mode": mode,
        "freeze": freeze,
        "freeze_sha256": expected_freeze,
        "ledger": ledger,
        "state": state,
        "data": data,
        "learned": ledger.parent / learned_state,
        "active": active,
        "current": current,
    }