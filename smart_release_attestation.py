from __future__ import annotations

import hashlib
import json
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "SMART_RELEASE_ATTESTATION_1"
REQUIRED = (
    "SMART_AUDIT_JUNIT_CURRENT.xml",
    "SMART_CANONICAL_ROOT.json",
    "SMART_PRODUCT_CERTIFICATION.json",
    "SMART_GLOBAL_INTEGRITY_PROOF.json",
    "SMART_AGENT_ECOSYSTEM_GOVERNANCE.json",
    "SMART_MATERIAL_DEFICIENCY_REGISTRY.json",
    "SMART_MISSION_STATUS.json",
)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(root: Path, *args: str) -> str:
    git = Path(r"C:\Progra~1\Git\cmd\git.exe")
    return subprocess.check_output([str(git), *args], cwd=root, text=True).strip()


def build(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    if missing:
        raise RuntimeError(f"release attestation inputs missing: {missing}")
    files = {name: _sha(root / name) for name in REQUIRED}
    version = (root / "VERSION").read_text(encoding="utf-8-sig").strip()
    dataset = root / "Mega-Sena.xlsx"
    manifest = root / "SMART_CRITICAL_CODE_MANIFEST.json"
    doc = {
        "schema": SCHEMA,
        "status": "CANDIDATE_NOT_FINAL",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "root": str(root),
        "version": version,
        "git_head": _git(root, "rev-parse", "HEAD"),
        "git_branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "git_status_porcelain": _git(root, "status", "--porcelain=v1"),
        "dataset_sha256": _sha(dataset),
        "critical_code_manifest_sha256": _sha(manifest) if manifest.is_file() else None,
        "authority_hashes": files,
    }
    raw = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    doc["sha256"] = hashlib.sha256(raw).hexdigest()
    return doc


def verify(root: str | Path, doc: dict[str, Any]) -> dict[str, Any]:
    current = build(root)
    comparable = dict(doc)
    observed = comparable.pop("sha256", None)
    raw = json.dumps(comparable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if observed != hashlib.sha256(raw).hexdigest():
        raise RuntimeError("release attestation self-hash mismatch")
    for field in ("host", "root", "version", "git_head", "dataset_sha256", "critical_code_manifest_sha256", "authority_hashes"):
        if doc.get(field) != current.get(field):
            raise RuntimeError(f"release attestation stale: {field}")
    return doc
