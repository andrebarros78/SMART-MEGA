from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from smart_canonical_identity import canonical_root
from smart_learning_epoch_reset import ACTIVE_PATH, verify_active_epoch
from smart_operational_lifecycle import _atomic_write, lifecycle_path, load_lifecycle


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve(root: Path, relative: str) -> Path:
    p = Path(relative)
    if not p.is_absolute():
        p = (root / p).resolve()
    else:
        p = p.resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"epoch path escapes project root: {relative}") from exc
    return p


def _rel(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")


def recover_interrupted_freeze_operation(root: str | Path, target: int, *, reason: str="operator_recovery") -> dict[str, Any]:
    root=Path(canonical_root(root)).resolve()
    from smart_operational_lifecycle import load_lifecycle,lifecycle_path,_atomic_write
    cur=load_lifecycle(root); st=str(cur.get("state") or "")
    if st=="FROZEN" and int(cur.get("target_contest",-1))==int(target): return {"status":"ALREADY_FROZEN","target_contest":int(target),"lifecycle_sha256":cur.get("sha256")}
    if st!="FREEZING" or int(cur.get("target_contest",-1))!=int(target): return {"status":"NOOP","target_contest":int(target),"lifecycle_state":st,"lifecycle_sha256":cur.get("sha256")}
    active=verify_active_epoch(root / ACTIVE_PATH)
    if active.get("status")!="RESET_READY" or int(active.get("target_contest",-1))!=int(target): raise RuntimeError("cannot recover interrupted freeze: active epoch is not RESET_READY")
    paths=active.get("state_paths") or {}; ledger=_resolve(root,paths["ledger"]); epoch=ledger.parent
    guarded=[_resolve(root,paths[k]) for k in ("state","activation_authority","expansion_registry","freeze")]+[epoch/f"SMART_{int(target)}_FRONTIER_SHADOW_FREEZE.json",epoch/"SMART_PROBABILITY_PROSPECTIVE_LEDGER.json",epoch/"POST_FREEZE_TOTAL_INTEGRATION.json"]
    existing=[_rel(root,x) for x in guarded if x.exists()]
    if existing: raise RuntimeError(f"cannot recover interrupted freeze: material artifacts exist: {existing}")
    if not ledger.is_file() or sha256_file(ledger)!=active.get("canonical_ledger_seed_sha256"): raise RuntimeError("cannot recover interrupted freeze: ledger seed mismatch")
    ev={**(cur.get("evidence") or {}),"interrupted_freeze_recovery":{"reason":str(reason),"target_contest":int(target),"active_epoch_sha256":active.get("sha256"),"ledger_sha256":sha256_file(ledger),"material_artifacts_absent":True}}
    nxt={"schema":cur.get("schema","SMART_OPERATIONAL_LIFECYCLE_1"),"state":"PREPARED","revision":int(cur["revision"])+1,"project":cur.get("project","SMART-MEGA"),"effective_version":cur.get("effective_version","6.3.2"),"target_contest":int(target),"completed_contest":cur.get("completed_contest"),"previous_state":st,"transition":"FREEZING_TO_PREPARED_RECOVERY","transition_actor":"interrupted_freeze_recovery","transition_utc":datetime.now(timezone.utc).isoformat(),"previous_lifecycle_sha256":cur["sha256"],"authority":"SINGLE_OPERATIONAL_LIFECYCLE","legacy_documents_are_evidence_not_authority":True,"migration_mode":cur.get("migration_mode"),"evidence":ev}
    out=_atomic_write(lifecycle_path(root),nxt,expected_revision=int(cur["revision"]),expected_sha256=cur["sha256"])
    return {"status":"RECOVERED_INTERRUPTED_FREEZE","target_contest":int(target),"lifecycle_sha256":out["sha256"],"result_used":False}
