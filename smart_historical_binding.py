from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from smart_crash_safe_io import atomic_write_json

SCHEMA = "SMART_IMMUTABLE_HISTORY_BINDING_1"
REQUIRED_EPOCH_FILES = (
    "SMART_3060_CHAMPION_CHALLENGER_FREEZE.json",
    "SMART_3060_CHAMPION_CHALLENGER_FREEZE_PORTFOLIO.json",
    "SMART_SIGNAL_LEDGER.json",
    "SMART_OFFICIAL_RESULT_INGEST_3060.json",
    "SMART_TERMINAL_EXECUTOR_STATUS_3060.json",
)


class HistoricalBindingError(RuntimeError):
    pass


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
def _sha_json(doc: dict[str, Any]) -> str:
    body = dict(doc)
    body.pop("sha256", None)
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _archive_manifest(root: Path, target: int) -> tuple[Path, dict[str, Any]]:
    base = root / "SMART_STATE_ARCHIVE" / "adjudicated-epochs" / str(int(target))
    matches = []
    for path in sorted(base.glob("*/ARCHIVE_MANIFEST.json")):
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        if doc.get("status") == "ARCHIVED_IMMUTABLE" and int(doc.get("target_contest", -1)) == int(target):
            if doc.get("sha256") != _sha_json(doc):
                raise HistoricalBindingError(f"archive manifest self-hash mismatch: {path}")
            matches.append((path, doc))
    if len(matches) != 1:
        raise HistoricalBindingError(f"expected one immutable archive for {target}, observed {len(matches)}")
    return matches[0]


def build(root: str | Path, target: int = 3060) -> dict[str, Any]:
    root = Path(root).resolve()
    manifest_path, manifest = _archive_manifest(root, int(target))
    epoch = manifest_path.parent / "epoch"
    source_files = manifest.get("source_files") or {}
    bound: dict[str, Any] = {}
    for name in REQUIRED_EPOCH_FILES:
        declared = source_files.get(name)
        path = epoch / name
        if not isinstance(declared, dict) or not path.is_file():
            raise HistoricalBindingError(f"required historical artifact missing: {name}")
        observed = _sha_file(path)
        if observed != declared.get("sha256"):
            raise HistoricalBindingError(f"historical artifact hash mismatch: {name}")
        bound[name] = {"sha256": observed, "bytes": path.stat().st_size}

    if int(manifest.get("freeze_event_count", 0)) != 1 or int(manifest.get("adjudication_event_count", 0)) != 1:
        raise HistoricalBindingError("3060 archive does not prove one freeze and one adjudication")

    review_path = root / f"SMART_POST_RESULT_REVIEW_{int(target)}.json"
    history_path = root / f"SMART_CANONICAL_HISTORY_ADVANCE_{int(target)}.json"
    ledger_reconcile_path = root / f"SMART_CANONICAL_SIGNAL_LEDGER_RECONCILIATION_{int(target)}.json"
    for path in (review_path, history_path, ledger_reconcile_path):
        if not path.is_file():
            raise HistoricalBindingError(f"historical metadata missing: {path.name}")

    binding = {
        "schema": SCHEMA,
        "status": "BOUND_IMMUTABLE_NO_RETROACTIVITY",
        "target_contest": int(target),
        "epoch_id": manifest.get("epoch_id"),
        "archive_manifest": {
            "file": str(manifest_path.relative_to(root)).replace("\\", "/"),
            "self_sha256": manifest.get("sha256"),
            "file_sha256": _sha_file(manifest_path),
        },
        "frozen_historical_artifacts": bound,
        "post_result_review": {"file": review_path.name, "sha256": _sha_file(review_path)},
        "canonical_history_advance": {"file": history_path.name, "sha256": _sha_file(history_path)},
        "canonical_ledger_reconciliation": {"file": ledger_reconcile_path.name, "sha256": _sha_file(ledger_reconcile_path)},
        "freeze_event_count": 1,
        "adjudication_event_count": 1,
        "historical_bytes_rewritten": False,
        "metadata_only_binding": True,
        "retroactive_recalibration_allowed": False,
    }
    binding["sha256"] = _sha_json(binding)
    return binding


def write_binding(root: str | Path, target: int = 3060) -> dict[str, Any]:
    root = Path(root).resolve()
    binding = build(root, int(target))
    path = root / f"SMART_{int(target)}_IMMUTABLE_HISTORY_BINDING.json"
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8-sig"))
        if current != binding:
            raise HistoricalBindingError(f"refusing to rewrite divergent historical binding: {path.name}")
        return current
    atomic_write_json(path, binding)
    return binding
