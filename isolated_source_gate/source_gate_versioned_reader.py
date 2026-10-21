"""Fail-closed isolated reader adapter. Never changes production source gate."""
from pathlib import Path
from source_gate_storage import IsolatedGate

def read_effective_gate(queue_root, ledger_path, legacy_reader, authority_registry_verified=False):
    root=Path(queue_root)
    if root.is_symlink(): raise ValueError("QUEUE_ROOT_SYMLINK")
    legacy=legacy_reader(root)
    if legacy.get("state")=="BLOCKED":
        return {"state":"BLOCKED","reason":legacy.get("reason"),"source":"LEGACY"}
    if legacy.get("state")!="UNBLOCKED": raise ValueError("UNKNOWN_LEGACY_STATE")
    if not authority_registry_verified:
        return {"state":"BLOCKED","reason":"AUTHORITY_NOT_VERIFIED","source":"ISOLATED"}
    db=IsolatedGate(ledger_path)
    try: state=db.read()
    finally: db.close()
    if state.state!="RELEASED":
        return {"state":"BLOCKED","reason":"ADMIN_GATE_BLOCKED","source":"ISOLATED"}
    return {"state":"RELEASED","reason":None,"generation":state.generation,"head":state.head,"source":"ISOLATED"}
