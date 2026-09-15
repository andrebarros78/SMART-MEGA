from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

FILE = "SMART_MANUAL_GENERATION_AUTHORITY.json"
SCHEMA = "SMART_MANUAL_GENERATION_AUTHORITY_V1"
WHY = "USER_EXPLICIT_GENERATION_COMMAND"

def _sha(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def path(root, active):
    return (Path(root).resolve() / active["state_paths"]["ledger"]).parent / FILE

def authorize(root, active, target):
    if active.get("status") != "RESET_READY" or active.get("operator_selected_target") is not True or int(active.get("target_contest", -1)) != int(target):
        raise ValueError("manual generation authorization requires matching RESET_READY operator epoch")
    p = path(root, active)
    if p.exists():
        x = json.loads(p.read_text(encoding="utf-8"))
        if x.get("status") == "AUTHORIZED" and x.get("consumed") is False:
            return x
        raise ValueError("manual generation authority is not reusable")
    x = {"schema": SCHEMA, "status": "AUTHORIZED", "authorized_by": WHY, "target_contest": int(target), "epoch_id": active["epoch_id"], "data_sha256": active["data_sha256"], "authorized_utc": datetime.now(timezone.utc).isoformat(), "consumed": False, "consumed_utc": None, "freeze_sha256": None}
    x["sha256"] = _sha(x)
    p.write_text(json.dumps(x, indent=2) + "\n", encoding="utf-8")
    return x

def validate(root, active, target):
    p = path(root, active)
    if not p.is_file():
        raise PermissionError("MANUAL_GENERATION_AUTHORITY_REQUIRED")
    x = json.loads(p.read_text(encoding="utf-8"))
    s = x.pop("sha256", None)
    checks = {
        "schema": x.get("schema") == SCHEMA,
        "status": x.get("status") == "AUTHORIZED",
        "reason": x.get("authorized_by") == WHY,
        "target": int(x.get("target_contest", -1)) == int(target) == int(active.get("target_contest", -2)),
        "epoch": x.get("epoch_id") == active.get("epoch_id"),
        "data": x.get("data_sha256") == active.get("data_sha256"),
        "unconsumed": x.get("consumed") is False,
        "integrity": s == _sha(x),
    }
    x["sha256"] = s
    if not all(checks.values()):
        raise PermissionError("MANUAL_GENERATION_AUTHORITY_INVALID:" + str(checks))
    return x

def consume(root, active, target, freeze_sha256):
    x = validate(root, active, target)
    p = path(root, active)
    x.pop("sha256", None)
    x.update(status="CONSUMED", consumed=True, consumed_utc=datetime.now(timezone.utc).isoformat(), freeze_sha256=str(freeze_sha256))
    x["sha256"] = _sha(x)
    p.write_text(json.dumps(x, indent=2) + "\n", encoding="utf-8")
    return x
