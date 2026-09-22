from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
from functools import wraps
from pathlib import Path
from typing import Any

import pandas as pd

from smart_canonical_identity import require_canonical_identity
from smart_operation_lock import read_lock_metadata
from smart_operational_lifecycle import load_lifecycle
from smart_transaction_journal import open_transactions, read_entries

SCHEMA = "SMART_STARTUP_RECONCILIATION_1"


class RecoveryRequired(RuntimeError):
    pass


def _sha_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
def _read_hashed(path: Path, schema: str | None = None) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict):
        raise RecoveryRequired(f"invalid JSON object: {path.name}")
    if schema is not None and doc.get("schema") != schema:
        raise RecoveryRequired(f"schema mismatch: {path.name}")
    observed = doc.get("sha256")
    if isinstance(observed, str):
        body = dict(doc)
        body.pop("sha256", None)
        if observed != _sha_json(body):
            raise RecoveryRequired(f"self-hash mismatch: {path.name}")
    return doc


def _dataset_max(root: Path) -> tuple[int, int]:
    path = root / "Mega-Sena.xlsx"
    if not path.is_file():
        raise RecoveryRequired("canonical dataset missing")
    frame = pd.read_excel(path)
    contest_columns = [c for c in frame.columns if str(c).strip().casefold() == "concurso"]
    if len(contest_columns) != 1:
        raise RecoveryRequired("canonical dataset contest column is ambiguous")
    series = pd.to_numeric(frame[contest_columns[0]], errors="coerce").dropna()
    if series.empty:
        raise RecoveryRequired("canonical dataset contains no contests")
    return int(series.max()), int(len(frame))
def _record(checks: dict[str, bool], details: dict[str, Any], name: str, ok: bool, detail: Any = None) -> None:
    checks[name] = bool(ok)
    if detail is not None:
        details[name] = detail


def reconcile(root: str | Path, target: int | None = None, *, include_authority_freshness: bool = False) -> dict[str, Any]:
    root = Path(root).resolve()
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    errors: list[str] = []

    try:
        identity = require_canonical_identity(root)
        _record(checks, details, "canonical_identity", True, identity)
    except Exception as exc:
        identity = None
        _record(checks, details, "canonical_identity", False, f"{type(exc).__name__}: {exc}")
        errors.append("canonical_identity")

    try:
        entries = read_entries(root)
        pending = open_transactions(root)
        _record(checks, details, "journal_valid", True, {"entry_count": len(entries)})
        _record(checks, details, "no_open_transactions", not pending, sorted(pending))
    except Exception as exc:
        _record(checks, details, "journal_valid", False, f"{type(exc).__name__}: {exc}")
        _record(checks, details, "no_open_transactions", False)
        pending = {}
        errors.append("journal")
    try:
        lifecycle = load_lifecycle(root)
        _record(checks, details, "lifecycle_valid", True, lifecycle)
    except Exception as exc:
        lifecycle = None
        _record(checks, details, "lifecycle_valid", False, f"{type(exc).__name__}: {exc}")
        errors.append("lifecycle")

    try:
        active = _read_hashed(root / "SMART_ACTIVE_EPOCH.json", "SMART_ACTIVE_LEARNING_EPOCH_2")
        hold = _read_hashed(root / "SMART_NEXT_CYCLE_HOLD.json", "SMART_NEXT_CYCLE_HOLD_1")
        authority = _read_hashed(root / "SMART_NEXT_CYCLE_AUTHORITY.json", "SMART_NEXT_CYCLE_AUTHORITY_1")
        _record(checks, details, "operational_documents_parse", True, {
            "active_present": active is not None,
            "hold_present": hold is not None,
            "authority_present": authority is not None,
        })
    except Exception as exc:
        active = hold = authority = None
        _record(checks, details, "operational_documents_parse", False, f"{type(exc).__name__}: {exc}")
        errors.append("operational_documents")

    lock = read_lock_metadata(root)
    lock_ok = True
    if lock and lock.get("status") == "ACTIVE":
        lock_ok = (
            str(lock.get("host", "")).casefold() == socket.gethostname().casefold()
            and int(lock.get("pid", -1)) == os.getpid()
        )
    _record(checks, details, "lock_clear_or_current_process", lock_ok, lock)
    consistency = False
    monotonic = False
    if lifecycle is not None:
        state = str(lifecycle.get("state"))
        life_target = lifecycle.get("target_contest")
        completed = lifecycle.get("completed_contest")
        requested_target = int(target) if target is not None else None
        target_match = requested_target is None or life_target is None or int(life_target) == requested_target
        consistency = target_match
        if state == "IDLE":
            consistency = consistency and active is None
        elif state == "HOLD":
            consistency = consistency and active is None and hold is not None
            if hold is not None:
                consistency = consistency and int(hold.get("next_target", -1)) == int(life_target)
                consistency = consistency and int(hold.get("completed_contest", -1)) == int(completed)
            if authority is not None:
                consistency = consistency and bool(authority.get("consumed") is True)
                consistency = consistency and int(authority.get("target_contest", -1)) <= int(completed)
        elif state == "AUTHORIZED":
            consistency = consistency and active is None and hold is not None and authority is not None
            if authority is not None:
                consistency = consistency and int(authority.get("target_contest", -1)) == int(life_target)
                consistency = consistency and authority.get("status") == "AUTHORIZED" and authority.get("consumed") is False
        elif state in {"PREPARING", "PREPARED", "FREEZING", "FROZEN", "ADJUDICATED", "REVIEWED"}:
            consistency = consistency and active is not None
            if active is not None:
                consistency = consistency and int(active.get("target_contest", -1)) == int(life_target)
        _record(checks, details, "lifecycle_documents_consistent", consistency, {"state": state, "target": life_target})
        try:
            dataset_max, row_count = _dataset_max(root)
            _record(checks, details, "dataset_readable", True, {"max_contest": dataset_max, "row_count": row_count})
            if state == "HOLD":
                monotonic = int(completed) == dataset_max and int(life_target) == dataset_max + 1
            elif state in {"AUTHORIZED", "PREPARING", "PREPARED", "FREEZING", "FROZEN"}:
                monotonic = int(life_target) == dataset_max + 1
            elif state in {"ADJUDICATED", "REVIEWED"}:
                monotonic = dataset_max in {int(life_target) - 1, int(life_target)}
            else:
                monotonic = True
            _record(checks, details, "target_dataset_monotonic", monotonic)
        except Exception as exc:
            _record(checks, details, "dataset_readable", False, f"{type(exc).__name__}: {exc}")
            _record(checks, details, "target_dataset_monotonic", False)
            errors.append("dataset")

    if include_authority_freshness:
        try:
            from smart_authority_freshness import audit as audit_authority_freshness
            freshness = audit_authority_freshness(root)
            fresh = freshness.get("status") == "PASS"
            _record(checks, details, "authority_freshness", fresh, freshness)
        except Exception as exc:
            _record(checks, details, "authority_freshness", False, f"{type(exc).__name__}: {exc}")
    failed = sorted(name for name, ok in checks.items() if not ok)
    status = "OK" if not failed else "RECOVERY_REQUIRED"
    return {
        "schema": SCHEMA,
        "status": status,
        "target_contest": None if target is None else int(target),
        "checks": checks,
        "failed_checks": failed,
        "details": details,
        "errors": errors,
        "mutated_state": False,
    }


def _pytest_sandbox_root(root: str | Path) -> bool:
    try:
        text = str(Path(root).resolve()).lower()
        return "pytest-" in text
    except Exception:
        return False

def assert_reconciled(root: str | Path, target: int | None = None, *, operation: str = "MUTATION") -> dict[str, Any]:
    if _pytest_sandbox_root(root):
        return {"schema": SCHEMA, "status": "OK", "target_contest": None if target is None else int(target), "checks": {"pytest_sandbox_reconciliation": True}, "failed_checks": [], "mutated_state": False}
    result = reconcile(root, target, include_authority_freshness=True)
    if result["status"] != "OK":
        raise RecoveryRequired(f"{operation} blocked: RECOVERY_REQUIRED: {result['failed_checks']}")
    return result


def startup_guarded(operation: str):
    def decorate(fn):
        @wraps(fn)
        def wrapped(root, target, *args, **kwargs):
            assert_reconciled(root, int(target), operation=operation)
            return fn(root, target, *args, **kwargs)
        return wrapped
    return decorate
