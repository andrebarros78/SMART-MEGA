"""Atomic, byte-preserving materialization of operator-adjudicated results.

No authority or prediction is created here. The caller provides ledger
reading and hashing so existing operator boundaries remain authoritative.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable


def materialize_adjudicated_result_dataset(
    root: Path, active: dict[str, Any], target: int,
    *, load_ledger: Callable, sha256_file: Callable,
) -> dict[str, Any]:
    """Copy the independently adjudicated result to the epoch without changing its bytes."""
    paths = active.get("state_paths") or {}
    ledger_value = paths.get("ledger") if isinstance(paths, dict) else None
    if not isinstance(ledger_value, str) or not ledger_value:
        raise ValueError("adjudicated epoch ledger path missing")
    ledger_path = (root / ledger_value).resolve()
    ledger_path.relative_to(root)
    ledger = load_ledger(ledger_path)
    rows = [event for event in ledger.get("events", [])
            if event.get("event_type") == "ADJUDICATION" and int(event.get("target_contest", -1)) == int(target)]
    if len(rows) != 1:
        raise ValueError("exactly one adjudication required for result materialization")
    record = rows[0]
    source_value = record.get("result_data_file")
    expected = record.get("result_data_sha256")
    if not isinstance(source_value, str) or not source_value or not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("adjudication result path/hash missing")
    source = (root / source_value).resolve()
    source.relative_to(root)
    if not source.is_file() or sha256_file(source) != expected:
        raise ValueError("adjudicated result file integrity mismatch")
    destination = (ledger_path.parent / f"Mega-Sena_through_{int(target)}.xlsx").resolve()
    destination.relative_to(root)
    if not destination.exists():
        fd, name = tempfile.mkstemp(prefix=f".result-{target}-", suffix=".xlsx", dir=destination.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            shutil.copyfile(source, temporary)
            if sha256_file(temporary) != expected or destination.exists():
                raise ValueError("adjudicated result copy failed integrity or exclusivity")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    if not destination.is_file() or sha256_file(destination) != expected:
        raise ValueError("epoch result dataset differs from adjudication")
    return {"status": "PASS", "target_contest": int(target),
            "file": str(destination.relative_to(root)).replace("\\", "/"), "sha256": expected}