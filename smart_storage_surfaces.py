from __future__ import annotations

from pathlib import Path
from smart_scientific_state_guard import classify as classify_state_surface

SURFACES = {
    "code": (".",),
    "runtime": ("runtime",),
    "evidence": ("SMART_STATE_ARCHIVE", "artifacts"),
}

class StorageSurfaceError(RuntimeError):
    pass

def _inside(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False

def root_path(root: str | Path) -> Path:
    return Path(root).resolve()

def runtime_path(root: str | Path, *parts: str) -> Path:
    base=root_path(root)/"runtime"
    p=(base.joinpath(*parts)).resolve()
    if not _inside(p,base.resolve()): raise StorageSurfaceError("runtime path escapes runtime surface")
    return p

def evidence_path(root: str | Path, surface: str, *parts: str) -> Path:
    if surface not in {"SMART_STATE_ARCHIVE","artifacts"}: raise StorageSurfaceError("unsupported evidence surface")
    base=(root_path(root)/surface).resolve(); p=base.joinpath(*parts).resolve()
    if not _inside(p,base): raise StorageSurfaceError("evidence path escapes evidence surface")
    return p

def require_within(path: str | Path, base: str | Path, *, label: str) -> Path:
    p=Path(path).resolve(); b=Path(base).resolve()
    if not _inside(p,b): raise StorageSurfaceError(f"{label} escapes authorized surface: {p}")
    return p

def classify(root: str | Path, path: str | Path) -> str:
    r=root_path(root); p=Path(path).resolve()
    governed_state = classify_state_surface(r, p)
    if governed_state != "other": return governed_state
    if _inside(p,(r/"runtime").resolve()): return "runtime"
    if _inside(p,(r/"SMART_STATE_ARCHIVE").resolve()) or _inside(p,(r/"artifacts").resolve()): return "evidence"
    if p.parent==r and p.suffix in {".py",".toml",".md",".json",".xlsx"}: return "code_or_governed_root"
    raise StorageSurfaceError(f"unclassified production path: {p}")
