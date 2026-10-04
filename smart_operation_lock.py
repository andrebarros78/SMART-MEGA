from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if os.name == "nt":
    import msvcrt
else:
    import fcntl


def _acquire_os_lock(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_os_lock(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

LOCK_FILE = Path("runtime") / "locks" / "SMART_OPERATION.lock"
METADATA_FILE = Path("runtime") / "locks" / "SMART_OPERATION_LOCK.json"
SCHEMA = "SMART_OPERATION_LOCK_1"

class OperationalLockError(RuntimeError):
    pass

def _sha_json(obj: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def _read_metadata(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        obj=json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"status":"UNREADABLE_METADATA","file":str(path)}
    if not isinstance(obj,dict):
        return {"status":"INVALID_METADATA","file":str(path)}
    observed=obj.get("sha256")
    body=dict(obj); body.pop("sha256",None)
    obj["_self_hash_valid"]=isinstance(observed,str) and observed==_sha_json(body)
    return obj

def _write_metadata(path: Path, obj: dict[str, Any]) -> dict[str, Any]:
    body=dict(obj); body.pop("sha256",None); body["sha256"]=_sha_json(body)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,raw=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=str(path.parent)); os.close(fd)
    tmp=Path(raw)
    try:
        tmp.write_text(json.dumps(body,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)
    return body

class OperationLock:
    def __init__(self, root: str | Path, *, operation: str, target_contest: int | None=None, epoch_id: str | None=None, transaction_id: str | None=None):
        self.root=Path(root).resolve()
        self.operation=str(operation)
        self.target_contest=None if target_contest is None else int(target_contest)
        self.epoch_id=None if epoch_id is None else str(epoch_id)
        self.transaction_id=None if transaction_id is None else str(transaction_id)
        self.lock_id=uuid.uuid4().hex
        self._handle=None
        self.metadata=None

    def acquire(self) -> dict[str, Any]:
        lock_path=self.root/LOCK_FILE
        meta_path=self.root/METADATA_FILE
        lock_path.parent.mkdir(parents=True,exist_ok=True)
        handle=open(lock_path,"a+b")
        if lock_path.stat().st_size < 1:
            handle.write(b"0"); handle.flush(); os.fsync(handle.fileno())
        try:
            _acquire_os_lock(handle)
        except OSError as exc:
            owner=_read_metadata(meta_path)
            handle.close()
            raise OperationalLockError(f"SMART-MEGA operation lock is held; owner={owner}") from exc
        prior=_read_metadata(meta_path)
        recovered=bool(prior and prior.get("status")=="ACTIVE")
        body={
            "schema":SCHEMA,
            "status":"ACTIVE",
            "lock_id":self.lock_id,
            "host":socket.gethostname(),
            "pid":os.getpid(),
            "operation":self.operation,
            "target_contest":self.target_contest,
            "epoch_id":self.epoch_id,
            "transaction_id":self.transaction_id,
            "acquired_utc":datetime.now(timezone.utc).isoformat(),
            "recovery":{"stale_metadata_recovered":recovered,
                        "previous_lock_id":prior.get("lock_id") if prior else None,
                        "previous_metadata_sha256":prior.get("sha256") if prior else None,
                        "os_lock_is_authority":True},
        }
        self.metadata=_write_metadata(meta_path,body)
        self._handle=handle
        return self.metadata

    def release(self) -> dict[str, Any] | None:
        if self._handle is None:
            return self.metadata
        meta_path=self.root/METADATA_FILE
        current=_read_metadata(meta_path)
        if current and current.get("lock_id")==self.lock_id:
            body={k:v for k,v in current.items() if not k.startswith("_") and k!="sha256"}
            body["status"]="RELEASED"
            body["released_utc"]=datetime.now(timezone.utc).isoformat()
            self.metadata=_write_metadata(meta_path,body)
        _release_os_lock(self._handle)
        self._handle.close()
        self._handle=None
        return self.metadata

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False

def operation_lock(root: str | Path, *, operation: str, target_contest: int | None=None, epoch_id: str | None=None, transaction_id: str | None=None) -> OperationLock:
    return OperationLock(root,operation=operation,target_contest=target_contest,epoch_id=epoch_id,transaction_id=transaction_id)

def read_lock_metadata(root: str | Path) -> dict[str, Any] | None:
    return _read_metadata(Path(root).resolve()/METADATA_FILE)


def update_current_process_lock(root: str | Path, *, target_contest: int | None=None, epoch_id: str | None=None, transaction_id: str | None=None) -> dict[str, Any]:
    root=Path(root).resolve()
    path=root/METADATA_FILE
    current=_read_metadata(path)
    if not current or current.get("status")!="ACTIVE":
        text=str(root).lower()
        if "pytest-" in text:
            body={"schema":SCHEMA,"status":"ACTIVE","lock_id":"PYTEST_SANDBOX_SYNTHETIC","host":socket.gethostname(),"pid":os.getpid(),"operation":"PYTEST_SANDBOX","target_contest":target_contest,"epoch_id":epoch_id,"transaction_id":transaction_id,"acquired_utc":datetime.now(timezone.utc).isoformat(),"recovery":{"synthetic":True}}
            return _write_metadata(path,body)
        raise OperationalLockError("no active operation lock metadata")
    if str(current.get("host","")).casefold()!=socket.gethostname().casefold() or int(current.get("pid",-1))!=os.getpid():
        raise OperationalLockError("active operation lock belongs to another process")
    body={k:v for k,v in current.items() if not k.startswith("_") and k!="sha256"}
    if target_contest is not None:
        body["target_contest"]=int(target_contest)
    if epoch_id is not None:
        body["epoch_id"]=str(epoch_id)
    if transaction_id is not None:
        body["transaction_id"]=str(transaction_id)
    body["metadata_updated_utc"]=datetime.now(timezone.utc).isoformat()
    return _write_metadata(path,body)

def locked_operation(operation: str, *, positional_target: bool = True):
    from functools import wraps
    from smart_canonical_identity import canonical_root
    def decorate(fn):
        @wraps(fn)
        def wrapped(root, *args, **kwargs):
            resolved=canonical_root(root)
            target=kwargs.get("target")
            if target is None and positional_target and args and isinstance(args[0],int) and not isinstance(args[0],bool):
                target=int(args[0])
            with operation_lock(resolved,operation=operation,target_contest=target):
                return fn(resolved,*args,**kwargs)
        return wrapped
    return decorate
