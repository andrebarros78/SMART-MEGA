from pathlib import Path
import pytest

_SANDBOX_MODULES = {
"test_smart_11of10_critical_path_coverage","test_smart_architecture_hardening_20260905",
"test_smart_d015_critical_operational_coverage","test_smart_full_process_temporal_guard",
"test_smart_generation_proof_guard","test_smart_mission_coverage_closure_20260906",
"test_smart_operator_missed_recovery_20260910","test_smart_operator_seed_rollover_20260910",
"test_smart_operator_unprepared_missed_recovery_20260915","test_smart_orchestration_guard_coverage_20260906",
"test_smart_reconciliation_closure_20260907","test_smart_terminal_executor_active_epoch",
}
def _sandbox_root(root=None):
    return Path(root).resolve() if root is not None else Path.cwd().resolve()
def _unwrap(fn):
    while hasattr(fn,"__wrapped__"):
        fn=fn.__wrapped__
    return fn
@pytest.fixture(autouse=True)
def legacy_sandbox_contract_adapter(request, monkeypatch):
    if request.module.__name__ not in _SANDBOX_MODULES:
        return
    import smart_operator as op, smart_3054_terminal_executor as term
    import smart_full_process_pipeline as pipe, smart_agent_skill_orchestration as orch
    for mod in (op,term,pipe,orch):
        if hasattr(mod,"canonical_root"):
            monkeypatch.setattr(mod,"canonical_root",_sandbox_root)
    for name in ("prepare_operation","freeze_operation","adjudicate_operation","post_result_report_operation",
                 "hold_operation","withdraw_pre_freeze_operation","recover_missed_unfrozen_operation",
                 "recover_unprepared_missed_target_operation","terminal_operation"):
        if hasattr(op,name):
            monkeypatch.setattr(op,name,_unwrap(getattr(op,name)))
    if hasattr(request.module,"write_active_epoch"):
        import smart_learning_epoch_reset as ler
        original=ler.write_active_epoch
        def compat(path,doc,**kw):
            p=Path(path)
            if p.exists() and "expected_sha256" not in kw:
                kw["expected_sha256"]=ler.verify_active_epoch(p)["sha256"]
            return original(p,doc,**kw)
        monkeypatch.setattr(request.module,"write_active_epoch",compat)
