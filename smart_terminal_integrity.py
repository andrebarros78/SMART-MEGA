"""Terminal evidence integrity, filesystem confinement, and temporal provenance.

Pure terminal helpers are kept separate from the orchestrator's runtime state.
Behavior is intentionally unchanged; the engine retains compatible entrypoints.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json_object(path: Path) -> dict[str, Any]:
    obj = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON object required: {path}")
    return obj


def atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp = Path(temporary)
    try:
        temp.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()



def project_local_path(root: Path, value: str | Path, label: str) -> Path:
    path = (root / Path(value)).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} escapes canonical root") from exc
    return path


def validate_post_result_temporal_guard(
    active: dict[str, Any], freeze_doc: dict[str, Any], target: int,
) -> str:
    """Preserve an operator-only clock as UNVERIFIED, never as official pre-draw proof.

    The immutable pre-result freeze is valid for operational adjudication even
    when its source never claimed an independently known drawing timestamp.
    Such a result can never upgrade its original temporal provenance.
    """
    guard = active.get("temporal_guard")
    frozen_guard = freeze_doc.get("temporal_guard")
    schedule = active.get("target_schedule")
    frozen_schedule = freeze_doc.get("target_schedule")
    if not all(isinstance(x, dict) for x in
               (guard, frozen_guard, schedule, frozen_schedule)):
        raise ValueError("post-result recovery temporal evidence missing")
    if (int(guard.get("target_contest", -1)) != int(target)
            or int(frozen_guard.get("target_contest", -1)) != int(target)
            or guard.get("result_used") is not False
            or frozen_guard.get("result_used") is not False
            or int(freeze_doc.get("target_contest", -1)) != int(target)
            or int(freeze_doc.get("cutoff_contest", -1)) != int(target)-1
            or freeze_doc.get("frozen_before_result") is not True
            or freeze_doc.get("causal_cutoff") is not True):
        raise ValueError("post-result recovery temporal evidence is not causal")

    if guard.get("status") == "PASS":
        if (frozen_guard.get("status") != "PASS"
                or guard.get("before_scheduled_draw") is not True
                or frozen_guard.get("before_scheduled_draw") is not True):
            raise ValueError("post-result recovery verified temporal guard invalid")
        return "VERIFIED_PRE_DRAW_WINDOW"

    if guard.get("status") != "OPERATOR_UNVERIFIED_DRAW_TIME":
        raise ValueError("post-result recovery temporal status unsupported")
    if (frozen_guard.get("status") != "OPERATOR_UNVERIFIED_DRAW_TIME"
            or guard.get("before_scheduled_draw") is not False
            or frozen_guard.get("before_scheduled_draw") is not False
            or guard.get("operator_selected") is not True
            or frozen_guard.get("operator_selected") is not True
            or active.get("operator_selected_target") is not True):
        raise ValueError("post-result operator temporal provenance mismatch")
    for item in (schedule, frozen_schedule):
        if (item.get("authority") != "OPERATOR_SELECTED_TARGET"
                or item.get("operator_selected_target") is not True
                or int(item.get("target_contest", -1)) != int(target)
                or item.get("target_date") is not None
                or item.get("draw_time_independently_verified") is not False
                or item.get("result_used") is not False):
            raise ValueError("post-result operator temporal schedule mismatch")
    return "OPERATOR_TIME_UNVERIFIED_AUDIT_ONLY"
