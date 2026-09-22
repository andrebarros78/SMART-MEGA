from __future__ import annotations

from smart_crash_safe_io import atomic_write_text
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path
from typing import Any

from smart_champion_challenger import load_ledger, reconcile_completed_epoch_ledger
from smart_learning_epoch_reset import verify_active_epoch
from smart_operational_lifecycle import assert_state, transition
from smart_operation_lock import locked_operation, update_current_process_lock
from smart_startup_reconciler import assert_reconciled
from smart_storage_surfaces import evidence_path, require_within
from smart_transaction_journal import begin as journal_begin, prepared as journal_prepared, committing as journal_committing, committed as journal_committed, rolled_back as journal_rolled_back

ARCHIVE_ROOT = Path("SMART_STATE_ARCHIVE") / "adjudicated-epochs"

class RolloverError(RuntimeError):
    pass

def _sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _load_archive_manifest(path: Path) -> dict[str, Any]:
    obj=json.loads(path.read_text(encoding="utf-8-sig"))
    observed=obj.get("sha256")
    body=dict(obj); body.pop("sha256",None)
    expected=hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    if observed != expected:
        raise RolloverError("archive manifest self-hash mismatch")
    if obj.get("status") != "ARCHIVED_IMMUTABLE" or obj.get("byte_for_byte_verified") is not True:
        raise RolloverError("archive manifest is not immutable/verified")
    return obj

def archive_completed_epoch(root: str | Path, target: int) -> dict[str, Any]:
    root=Path(root).resolve()
    target=int(target)
    active_path=root/"SMART_ACTIVE_EPOCH.json"
    archive_parent=evidence_path(root,"SMART_STATE_ARCHIVE","adjudicated-epochs",str(target))
    if active_path.is_file():
        active=verify_active_epoch(active_path)
        if int(active.get("target_contest",-1)) != target:
            raise RolloverError("active epoch target mismatch")
        ledger_path=(root/active["state_paths"]["ledger"]).resolve()
        ledger=load_ledger(ledger_path)
        events=[e for e in ledger.get("events",[]) if isinstance(e,dict) and int(e.get("target_contest",-1))==target]
        if sum(1 for e in events if e.get("event_type")=="ADJUDICATION") != 1:
            raise RolloverError("completed epoch requires exactly one adjudication")
        reconcile=reconcile_completed_epoch_ledger(root/"SMART_SIGNAL_LEDGER.json",ledger_path,target,root=root)
        epoch_dir=require_within(ledger_path.parent, root/"runtime", label="rollover epoch")
        archive_root=archive_parent/str(active["epoch_id"])
        archive_epoch=archive_root/"epoch"
        source={p.relative_to(epoch_dir).as_posix():_sha(p) for p in sorted(epoch_dir.rglob("*")) if p.is_file()}
        if not archive_root.exists():
            archive_root.mkdir(parents=True,exist_ok=False)
            shutil.copytree(epoch_dir,archive_epoch)
            shutil.copy2(active_path,archive_root/"SMART_ACTIVE_EPOCH.json")
            manifest={"schema":"SMART_ADJUDICATED_EPOCH_ARCHIVE_1","status":"ARCHIVED_IMMUTABLE","target_contest":target,
                      "epoch_id":active["epoch_id"],"file_count":len(source),"source_files":source,
                      "source_active_pointer_sha256":_sha(active_path),"byte_for_byte_verified":True,
                      "immutability_policy":"CONTENT_ADDRESSED_READ_ONLY_ARCHIVE"}
            manifest["sha256"]=hashlib.sha256(json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
            atomic_write_text(archive_root/"ARCHIVE_MANIFEST.json",json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
            for item in archive_root.rglob("*"):
                if item.is_file(): os.chmod(item,stat.S_IREAD)
        manifest_path=archive_root/"ARCHIVE_MANIFEST.json"
        manifest=_load_archive_manifest(manifest_path)
        archived={p.relative_to(archive_epoch).as_posix():_sha(p) for p in sorted(archive_epoch.rglob("*")) if p.is_file()}
        if archived != source:
            raise RolloverError("archive files differ from source epoch")
        if _sha(archive_root/"SMART_ACTIVE_EPOCH.json") != _sha(active_path):
            raise RolloverError("archive pointer differs from live pointer")
        active_path.unlink()
        return {"status":"ARCHIVED","archive_manifest":str(manifest_path.relative_to(root)).replace("\\","/"),
                "archive_manifest_sha256":_sha(manifest_path),"reconciliation":reconcile}
    candidates=list(archive_parent.glob("*/ARCHIVE_MANIFEST.json")) if archive_parent.is_dir() else []
    if len(candidates)!=1:
        raise RolloverError("active pointer absent and unique immutable archive not found")
    manifest=_load_archive_manifest(candidates[0])
    if int(manifest.get("target_contest",-1)) != target:
        raise RolloverError("archived target mismatch")
    return {"status":"ALREADY_ARCHIVED","archive_manifest":str(candidates[0].relative_to(root)).replace("\\","/"),
            "archive_manifest_sha256":_sha(candidates[0]),"reconciliation":None}

def _read_self_hashed(path: Path, schema: str) -> dict[str, Any]:
    obj=json.loads(path.read_text(encoding="utf-8-sig"))
    if obj.get("schema") != schema:
        raise RolloverError(f"unexpected schema for {path}")
    observed=obj.get("sha256")
    body=dict(obj); body.pop("sha256",None)
    expected=hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    if observed != expected:
        raise RolloverError(f"self-hash mismatch: {path}")
    return obj

@locked_operation("ROLLOVER")
def canonical_rollover(root: str | Path, target: int, hold_file: str | Path="SMART_NEXT_CYCLE_HOLD.json") -> dict[str, Any]:
    root=Path(root).resolve()
    target=int(target)
    assert_reconciled(root,target,operation="ROLLOVER")
    lifecycle_before=assert_state(root,"REVIEWED",target_contest=target)
    transaction_id=f"ROLLOVER:{target}:{target+1}"
    update_current_process_lock(root, target_contest=target, transaction_id=transaction_id)
    journal_begin(root,transaction_id,"ROLLOVER",target_contest=target,metadata={"lifecycle_sha256":lifecycle_before["sha256"]})
    try:
        hold_path=Path(hold_file)
        if not hold_path.is_absolute():
            hold_path=root/hold_path
        hold_path=hold_path.resolve()
        hold_path.relative_to(root)
        hold=_read_self_hashed(hold_path,"SMART_NEXT_CYCLE_HOLD_1")
        if hold.get("status") != "AWAITING_OPERATOR_APPLY_OR_GENERATE":
            raise RolloverError("next-cycle hold is not active")
        if int(hold.get("completed_contest",-1)) != target or int(hold.get("next_target",-1)) != target+1:
            raise RolloverError("next-cycle hold target sequence mismatch")
        if hold.get("automatic_prepare_forbidden") is not True or hold.get("prepare_allowed") is not False:
            raise RolloverError("next-cycle hold must forbid automatic prepare")
        review_path=(root/str(hold.get("review_file") or "")).resolve()
        review_path.relative_to(root)
        if not review_path.is_file() or _sha(review_path) != hold.get("review_file_sha256"):
            raise RolloverError("hold review binding mismatch")
        canonical=root/"Mega-Sena.xlsx"
        if not canonical.is_file() or _sha(canonical) != hold.get("canonical_sha256_at_review"):
            raise RolloverError("hold canonical history binding mismatch")
    except Exception as exc:
        journal_rolled_back(root,transaction_id,"ROLLOVER",target_contest=target,metadata={"error_type":type(exc).__name__})
        raise
    journal_prepared(root,transaction_id,"ROLLOVER",target_contest=target,metadata={"hold_sha256":hold["sha256"]})
    journal_committing(root,transaction_id,"ROLLOVER",target_contest=target)
    archive=archive_completed_epoch(root,target)
    lifecycle=transition(root,"REVIEWED","HOLD",target_contest=target+1,completed_contest=target,
                         actor="smart_rollover.canonical_rollover",
                         evidence={"rollover_archive":{"manifest":archive["archive_manifest"],"sha256":archive["archive_manifest_sha256"]},
                                   "post_result_hold":{"file":str(hold_path.relative_to(root)).replace("\\","/"),"sha256":hold["sha256"]}})
    journal_committed(root,transaction_id,"ROLLOVER",target_contest=target,
                      metadata={"archive_manifest_sha256":archive["archive_manifest_sha256"],"lifecycle_sha256":lifecycle["sha256"]})
    return {"status":"ROLLOVER_COMMITTED","transaction_id":transaction_id,"completed_contest":target,"next_target":target+1,
            "archive":archive,"hold":hold,"operational_lifecycle":lifecycle}
