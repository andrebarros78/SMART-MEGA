from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from smart_critical_code_manifest import build as build_critical_code_manifest
from smart_material_deficiency_registry import load_registry
from smart_product_certification import verify_product_certification

SCHEMA = "SMART_AUTHORITY_FRESHNESS_AUDIT_1"

def _sha_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def _read_self_hashed(path: Path) -> dict[str, Any]:
    obj=json.loads(path.read_text(encoding="utf-8-sig"))
    observed=obj.get("sha256"); body=dict(obj); body.pop("sha256",None)
    if observed != _sha_json(body):
        raise ValueError(f"self-hash invalid: {path.name}")
    return obj

def verify_governance(root: str | Path, path: str | Path="SMART_AGENT_ECOSYSTEM_GOVERNANCE.json") -> dict[str, Any]:
    root=Path(root).resolve(); p=Path(path)
    if not p.is_absolute(): p=root/p
    doc=_read_self_hashed(p)
    if doc.get("status") != "PASS" or not all(doc.get("checks",{}).values()):
        raise ValueError("governance is not live PASS")
    if doc.get("critical_code_manifest") != build_critical_code_manifest(root):
        raise ValueError("governance critical code manifest is stale")
    verify_product_certification(root/"SMART_PRODUCT_CERTIFICATION.json",root=root,require_current_code=True)
    return doc

def audit(root: str | Path) -> dict[str, Any]:
    root=Path(root).resolve()
    manifest=build_critical_code_manifest(root)
    registry=load_registry(root/"SMART_MATERIAL_DEFICIENCY_REGISTRY.json",root=root)
    result={"schema":SCHEMA,"critical_code_manifest":manifest,"material_open_count":registry.get("open_count"),"authorities":{}}
    try:
        verify_product_certification(root/"SMART_PRODUCT_CERTIFICATION.json",root=root,require_current_code=True)
        result["authorities"]["product_certification"]={"current":True}
    except Exception as exc:
        result["authorities"]["product_certification"]={"current":False,"reason":f"{type(exc).__name__}: {exc}"}
    try:
        verify_governance(root)
        result["authorities"]["governance"]={"current":True}
    except Exception as exc:
        result["authorities"]["governance"]={"current":False,"reason":f"{type(exc).__name__}: {exc}"}
    try:
        from smart_global_integrity import verify_global_integrity
        verify_global_integrity(root,root/"SMART_3052_IMPLEMENTATION_GATE.json",root/"SMART_GLOBAL_INTEGRITY_PROOF.json")
        result["authorities"]["global_integrity"]={"current":True}
    except Exception as exc:
        result["authorities"]["global_integrity"]={"current":False,"reason":f"{type(exc).__name__}: {exc}"}
    result["terminal_compatible"] = registry.get("open_count")==0 and all(v.get("current") is True for v in result["authorities"].values())
    result["status"]="PASS" if result["terminal_compatible"] else "STALE_OR_BLOCKED"
    result["sha256"]=_sha_json(result)
    return result
