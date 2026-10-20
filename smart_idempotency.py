from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from functools import wraps

from smart_crash_safe_io import atomic_write_json

SCHEMA = "SMART_IDEMPOTENCY_1"


def make_key(operation: str, target: int, payload: Any = None, *, epoch_id: str | None = None, transaction_id: str | None = None) -> str:
    basis = {"operation": operation, "target": int(target), "payload": payload}
    if epoch_id is not None:
        basis["epoch_id"] = str(epoch_id)
    if transaction_id is not None:
        basis["transaction_id"] = str(transaction_id)
    raw = json.dumps(basis, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def record_path(root: str | Path, operation: str, key: str) -> Path:
    return Path(root) / "runtime" / "idempotency" / operation / (key + ".json")


def load(root: str | Path, operation: str, key: str) -> dict | None:
    path = record_path(root, operation, key)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
def commit(root: str | Path, operation: str, key: str, target: int, result: Any, *, epoch_id: str | None = None, transaction_id: str | None = None) -> dict:
    path = record_path(root, operation, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    prior = load(root, operation, key)
    body = {"schema": SCHEMA, "operation": operation, "idempotency_key": key, "target": int(target), "result": result}
    if epoch_id is not None:
        body["epoch_id"] = str(epoch_id)
    if transaction_id is not None:
        body["transaction_id"] = str(transaction_id)
    if prior is not None:
        if prior != body:
            raise RuntimeError("idempotency key conflict")
        return prior
    atomic_write_json(path, body)
    return body


def resolve_key(operation: str, target: int, supplied: str | None = None, payload: Any = None, *, epoch_id: str | None = None, transaction_id: str | None = None) -> str:
    expected = make_key(operation, target, payload, epoch_id=epoch_id, transaction_id=transaction_id)
    if supplied is not None and supplied != expected:
        raise RuntimeError("idempotency key does not match operation payload")
    return supplied or expected


def replay(root: str | Path, operation: str, key: str, target: int) -> Any | None:
    prior = load(root, operation, key)
    if prior is None:
        return None
    if int(prior.get("target", -1)) != int(target):
        raise RuntimeError("idempotency target conflict")
    return prior.get("result")
def idempotent_operation(operation: str, payload_builder=None, *, commit_if=None):
    def decorate(fn):
        @wraps(fn)
        def wrapped(root, target, *args, idempotency_key=None, **kwargs):
            payload = payload_builder(root, target, args, kwargs) if payload_builder else {
                "args": [str(x) for x in args],
                "kwargs": {k: str(v) for k, v in sorted(kwargs.items())},
            }
            epoch_id = kwargs.get("epoch_id")
            transaction_id = kwargs.get("transaction_id")
            key = resolve_key(
                operation,
                int(target),
                idempotency_key,
                payload,
                epoch_id=epoch_id,
                transaction_id=transaction_id,
            )
            prior = replay(root, operation, key, int(target))
            if prior is not None:
                return prior
            result = fn(root, target, *args, **kwargs)
            # A transient WAITING/RECOVERY_REQUIRED outcome must remain
            # retryable when a later observation or repair changes the state.
            if commit_if is None or commit_if(result):
                commit(
                    root,
                    operation,
                    key,
                    int(target),
                    result,
                    epoch_id=epoch_id,
                    transaction_id=transaction_id,
                )
            return result
        return wrapped
    return decorate
