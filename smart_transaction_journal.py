from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "SMART_TRANSACTION_JOURNAL_1"
JOURNAL_PATH = Path("runtime") / "transactions" / "SMART_TRANSACTION_JOURNAL.jsonl"
PHASES = ("BEGIN","PREPARED","COMMITTING","COMMITTED","ROLLED_BACK")
ALLOWED = {
    "BEGIN":{"PREPARED","ROLLED_BACK"},
    "PREPARED":{"COMMITTING","ROLLED_BACK"},
    "COMMITTING":{"COMMITTED"},
    "COMMITTED":set(),
    "ROLLED_BACK":set(),
}

class TransactionJournalError(RuntimeError):
    pass

def _canonical(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")

def _entry_hash(obj: dict[str, Any]) -> str:
    body=dict(obj); body.pop("entry_sha256",None)
    return hashlib.sha256(_canonical(body)).hexdigest()

def journal_path(root: str | Path) -> Path:
    return Path(root).resolve()/JOURNAL_PATH

def read_entries(root: str | Path) -> list[dict[str, Any]]:
    path=journal_path(root)
    if not path.exists():
        return []
    entries=[]
    previous=None
    for lineno,line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(),1):
        if not line.strip():
            continue
        obj=json.loads(line)
        if obj.get("schema") != SCHEMA:
            raise TransactionJournalError(f"invalid journal schema at line {lineno}")
        if obj.get("phase") not in PHASES:
            raise TransactionJournalError(f"invalid journal phase at line {lineno}")
        if obj.get("previous_entry_sha256") != previous:
            raise TransactionJournalError(f"journal hash-chain break at line {lineno}")
        if obj.get("entry_sha256") != _entry_hash(obj):
            raise TransactionJournalError(f"journal entry hash mismatch at line {lineno}")
        entries.append(obj)
        previous=obj["entry_sha256"]
    return entries

def transaction_entries(root: str | Path, transaction_id: str) -> list[dict[str, Any]]:
    return [e for e in read_entries(root) if e.get("transaction_id")==transaction_id]

def current_phase(root: str | Path, transaction_id: str) -> str | None:
    entries=transaction_entries(root,transaction_id)
    return None if not entries else str(entries[-1]["phase"])



def append_phase(root: str | Path, transaction_id: str, operation: str, phase: str, *, target_contest: int | None=None, metadata: dict[str, Any] | None=None) -> dict[str, Any]:
    if phase not in PHASES:
        raise TransactionJournalError(f"unsupported journal phase: {phase}")
    root=Path(root).resolve()
    path=journal_path(root)
    path.parent.mkdir(parents=True,exist_ok=True)
    entries=read_entries(root)
    tx=[e for e in entries if e.get("transaction_id")==transaction_id]
    prior_phase=None if not tx else str(tx[-1]["phase"])
    if phase=="BEGIN":
        if tx:
            raise TransactionJournalError(f"transaction already exists: {transaction_id}")
    else:
        if not tx:
            raise TransactionJournalError(f"transaction does not exist: {transaction_id}")
        if phase not in ALLOWED.get(prior_phase,set()):
            raise TransactionJournalError(f"forbidden journal transition: {prior_phase} -> {phase}")
    entry={
        "schema":SCHEMA,
        "sequence":len(entries)+1,
        "transaction_sequence":len(tx)+1,
        "transaction_id":str(transaction_id),
        "operation":str(operation),
        "target_contest":None if target_contest is None else int(target_contest),
        "phase":phase,
        "previous_transaction_phase":prior_phase,
        "previous_entry_sha256":None if not entries else entries[-1]["entry_sha256"],
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "metadata":dict(metadata or {}),
    }
    entry["entry_sha256"]=_entry_hash(entry)
    raw=(json.dumps(entry,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode("utf-8")
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    try:
        os.write(fd,raw)
        os.fsync(fd)
    finally:
        os.close(fd)
    verified=read_entries(root)
    if not verified or verified[-1].get("entry_sha256") != entry["entry_sha256"]:
        raise TransactionJournalError("journal append verification failed")
    return entry

def begin(root: str | Path, transaction_id: str, operation: str, *, target_contest: int | None=None, metadata: dict[str, Any] | None=None) -> dict[str, Any]:
    return append_phase(root,transaction_id,operation,"BEGIN",target_contest=target_contest,metadata=metadata)

def prepared(root: str | Path, transaction_id: str, operation: str, *, target_contest: int | None=None, metadata: dict[str, Any] | None=None) -> dict[str, Any]:
    return append_phase(root,transaction_id,operation,"PREPARED",target_contest=target_contest,metadata=metadata)

def committing(root: str | Path, transaction_id: str, operation: str, *, target_contest: int | None=None, metadata: dict[str, Any] | None=None) -> dict[str, Any]:
    return append_phase(root,transaction_id,operation,"COMMITTING",target_contest=target_contest,metadata=metadata)

def committed(root: str | Path, transaction_id: str, operation: str, *, target_contest: int | None=None, metadata: dict[str, Any] | None=None) -> dict[str, Any]:
    return append_phase(root,transaction_id,operation,"COMMITTED",target_contest=target_contest,metadata=metadata)

def rolled_back(root: str | Path, transaction_id: str, operation: str, *, target_contest: int | None=None, metadata: dict[str, Any] | None=None) -> dict[str, Any]:
    return append_phase(root,transaction_id,operation,"ROLLED_BACK",target_contest=target_contest,metadata=metadata)

def open_transactions(root: str | Path) -> dict[str, dict[str, Any]]:
    latest={}
    for entry in read_entries(root):
        latest[str(entry["transaction_id"])]=entry
    return {k:v for k,v in latest.items() if v.get("phase") not in {"COMMITTED","ROLLED_BACK"}}
