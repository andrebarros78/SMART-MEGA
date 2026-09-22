from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "SMART_CRITICAL_CODE_MANIFEST_1"
DEFAULT_PATH = Path("SMART_CRITICAL_CODE_MANIFEST.json")

EXPLICIT_NON_SMART = (
    "adjudicate_signal_challenger.py",
)

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def critical_code_files(root: str | Path) -> list[Path]:
    root=Path(root).resolve()
    rows=[p for p in root.glob("smart_*.py") if p.is_file() and not p.name.startswith("test_")]
    for name in EXPLICIT_NON_SMART:
        p=root/name
        if p.is_file(): rows.append(p)
    unique={p.resolve():p for p in rows}
    return sorted(unique.values(), key=lambda p:p.name.casefold())

def build(root: str | Path) -> dict[str, Any]:
    root=Path(root).resolve()
    files={p.name:sha256_file(p) for p in critical_code_files(root)}
    basis={"schema":SCHEMA,"files":files}
    fingerprint=hashlib.sha256(json.dumps(basis,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {"schema":SCHEMA,"file_count":len(files),"files":files,"fingerprint_sha256":fingerprint}

def verify_document_binding(doc: dict[str, Any], root: str | Path, field: str="critical_code_manifest") -> dict[str, Any]:
    current=build(root)
    observed=doc.get(field)
    if observed != current:
        raise ValueError(f"{field} is stale for current critical code")
    return current

def write(root: str | Path, out: str | Path=DEFAULT_PATH) -> dict[str, Any]:
    root=Path(root).resolve(); path=Path(out)
    if not path.is_absolute(): path=root/path
    doc=build(root)
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return doc
