from pathlib import Path
import smart_operator as op

ROOT = Path(__file__).resolve().parent

def test_preflight_hold_returns_operator_authorization_status(tmp_path, monkeypatch):
    monkeypatch.setattr(op,"canonical_root",lambda root=None: Path(root).resolve())
    monkeypatch.setattr(op,"reconcile_startup",lambda *a,**k:{"status":"OK","checks":{}})
    monkeypatch.setattr(op,"audit_state_boundaries",lambda root:{"status":"PASS"})
    monkeypatch.setattr(op,"_require_next_cycle_authority",lambda *a,**k: (_ for _ in ()).throw(RuntimeError("not authorized")))
    import smart_product_certification, smart_operational_lifecycle as lc
    monkeypatch.setattr(smart_product_certification,"verify_product_certification",lambda *a,**k:{"sha256":"c"*64})
    monkeypatch.setattr(lc,"load_lifecycle",lambda root:{"state":"HOLD","target_contest":3062,"sha256":"l"*64})
    out=op.preflight_operation(tmp_path,3062)
    assert out["status"]=="AWAITING_OPERATOR_AUTHORIZATION"
    assert out["mutated_state"] is False

def test_freeze_operation_recovers_before_retry(tmp_path, monkeypatch):
    calls=[]
    monkeypatch.setattr(op,"canonical_root",lambda root=None: Path(root).resolve())
    monkeypatch.setattr(op,"recover_interrupted_freeze_operation",lambda root,target,reason="": calls.append((target,reason)) or {"status":"RECOVERED_INTERRUPTED_FREEZE"})
    monkeypatch.setattr(op,"assert_lifecycle_state",lambda *a,**k:{})
    monkeypatch.setattr(op,"verify_active_epoch",lambda path:{"operator_selected_target":True,"target_contest":3062})
    monkeypatch.setattr(op,"run_full_process",lambda *a,**k:{"status":"PASS"})
    assert op.freeze_operation(tmp_path,3062)["status"]=="PASS"
    assert calls==[(3062,"freeze_operation_entry")]

def test_freeze_operation_is_idempotent_when_already_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(op,"canonical_root",lambda root=None: Path(root).resolve())
    monkeypatch.setattr(op,"recover_interrupted_freeze_operation",lambda *a,**k:{"status":"ALREADY_FROZEN"})
    monkeypatch.setattr(op,"_existing_frozen_freeze_summary",lambda root,target:{"status":"FROZEN","idempotent_replay":True,"target_contest":target})
    assert op.freeze_operation(tmp_path,3062)["idempotent_replay"] is True

def test_run_full_process_contains_exception_rollback():
    assert 'recover_interrupted_freeze_operation(root, target, reason="run_full_process_exception_rollback")' in (ROOT / 'smart_full_process_pipeline.py').read_text(encoding="utf-8")
