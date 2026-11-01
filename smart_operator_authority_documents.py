"""Hashed authority documents and pre-freeze withdrawal proof validation.

The operator supplies its atomic writer and authorized evidence directory at
its call boundary. Keep this module independent of operator lifecycle state.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable


def sha256_json(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def load_hashed_doc(path: Path, schema: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("schema") != schema:
        raise ValueError(f"invalid {schema} document")
    observed = obj.get("sha256")
    canonical = dict(obj)
    canonical.pop("sha256", None)
    if not isinstance(observed, str) or observed.lower() != sha256_json(canonical):
        raise ValueError(f"{schema} self-hash mismatch")
    return obj


def write_hashed_doc(path: Path, payload: dict[str, Any], *, expected_sha256: str | None = None, atomic_write_text: Callable[[Path, str], Any]) -> dict[str, Any]:
    current = None
    if path.exists():
        if expected_sha256 is None:
            raise RuntimeError(f"CAS expected_sha256 required for overwrite: {path.name}")
        current = load_hashed_doc(path, str(payload.get("schema") or ""))
        if current.get("sha256") != expected_sha256:
            raise RuntimeError(f"CAS sha256 conflict: {path.name}")
    elif expected_sha256 is not None:
        raise RuntimeError(f"CAS expected existing document missing: {path.name}")
    obj = dict(payload)
    obj.pop("sha256", None)
    obj["revision"] = (int(current.get("revision", 0)) + 1) if current else 1
    obj["previous_document_sha256"] = current.get("sha256") if current else None
    obj["sha256"] = sha256_json(obj)
    tmp = path.with_suffix(path.suffix + ".tmp")
    atomic_write_text(tmp,json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    if current is not None:
        latest = load_hashed_doc(path, str(payload.get("schema") or ""))
        if latest.get("sha256") != expected_sha256:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"CAS changed before replace: {path.name}")
    elif path.exists():
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"CAS create conflict: {path.name}")
    tmp.replace(path)
    return obj


def find_valid_pre_freeze_withdrawal(archive: Path, target: int, epoch_id: str) -> tuple[Path, dict[str, Any]] | None:
    archive = Path(archive)
    if not archive.is_dir():
        return None
    for path in archive.glob("operator_pre_freeze_withdrawal_*.json"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(obj, dict) or obj.get("schema") != "SMART_OPERATOR_PRE_FREEZE_WITHDRAWAL_1":
            continue
        observed = obj.get("sha256")
        canonical = dict(obj); canonical.pop("sha256", None); canonical.pop("proof_file", None)
        if not isinstance(observed, str) or observed != sha256_json(canonical):
            continue
        if obj.get("status") != "WITHDRAWN_PRE_FREEZE":
            continue
        if int(obj.get("target_contest", -1)) != int(target) or str(obj.get("epoch_id") or "") != str(epoch_id):
            continue
        if obj.get("active_pointer_removed") is not True or obj.get("reason") != "PRE_FREEZE_TECHNICAL_CORRECTION":
            continue
        checks = obj.get("checks") or {}
        if not isinstance(checks, dict) or not checks or not all(v is True for v in checks.values()):
            continue
        return path, obj
    return None
