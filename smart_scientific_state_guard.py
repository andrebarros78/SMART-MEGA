from __future__ import annotations

from pathlib import Path
from typing import Any

SCHEMA = "SMART_SCIENTIFIC_OPERATIONAL_SEPARATION_1"

SCIENTIFIC_ROOT_FILES = frozenset({
    "SMART_SIGNAL_LEDGER.json",
    "SMART_PROBABILITY_PROSPECTIVE_LEDGER.json",
    "SMART_SIGNAL_STATE.json",
})
OPERATIONAL_ROOT_FILES = frozenset({
    "SMART_OPERATIONAL_LIFECYCLE.json",
    "SMART_NEXT_CYCLE_HOLD.json",
    "SMART_NEXT_CYCLE_AUTHORITY.json",
    "SMART_ACTIVE_EPOCH.json",
})
SCIENTIFIC_WRITE_INTENTS = frozenset({
    "SCIENTIFIC_APPEND",
    "GOVERNED_LEARNING_UPDATE",
    "PROSPECTIVE_FREEZE",
    "ADJUDICATION",
})


class ScientificStateBoundaryError(RuntimeError):
    pass
def _inside(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def classify(root: str | Path, path: str | Path) -> str:
    root = Path(root).resolve()
    path = Path(path).resolve()
    if path.parent == root and path.name in SCIENTIFIC_ROOT_FILES:
        return "scientific_state"
    if path.parent == root and path.name in OPERATIONAL_ROOT_FILES:
        return "operational_state"
    if _inside(path, (root / "SMART_STATE_ARCHIVE" / "adjudicated-epochs").resolve()):
        return "immutable_scientific_history"
    if _inside(path, (root / "runtime" / "learning_epochs").resolve()):
        return "scientific_epoch_runtime"
    if _inside(path, (root / "runtime").resolve()):
        return "operational_runtime"
    return "other"
def assert_operational_write(root: str | Path, path: str | Path) -> Path:
    resolved = Path(path).resolve()
    category = classify(root, resolved)
    if category in {"scientific_state", "scientific_epoch_runtime", "immutable_scientific_history"}:
        raise ScientificStateBoundaryError(f"operational write forbidden on {category}: {resolved}")
    return resolved


def assert_scientific_write(root: str | Path, path: str | Path, *, intent: str) -> Path:
    if intent not in SCIENTIFIC_WRITE_INTENTS:
        raise ScientificStateBoundaryError(f"unsupported scientific write intent: {intent}")
    resolved = Path(path).resolve()
    category = classify(root, resolved)
    if category == "immutable_scientific_history":
        raise ScientificStateBoundaryError(f"immutable scientific history cannot be rewritten: {resolved}")
    if category not in {"scientific_state", "scientific_epoch_runtime"}:
        raise ScientificStateBoundaryError(f"scientific write outside scientific surface: {resolved}")
    return resolved
def audit_boundaries(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    scientific = sorted(name for name in SCIENTIFIC_ROOT_FILES if (root / name).exists())
    operational = sorted(name for name in OPERATIONAL_ROOT_FILES if (root / name).exists())
    archive = root / "SMART_STATE_ARCHIVE" / "adjudicated-epochs"
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "scientific_root_files_present": scientific,
        "operational_root_files_present": operational,
        "immutable_history_surface_present": archive.is_dir(),
        "operational_may_rewrite_scientific_state": False,
        "immutable_history_rewrite_allowed": False,
    }
