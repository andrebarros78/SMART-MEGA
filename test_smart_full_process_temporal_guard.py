from pathlib import Path

import numpy as np
import pytest

import smart_full_process_pipeline as fp


def _active(tmp_path: Path):
    data=tmp_path/'data.xlsx'
    data.write_bytes(b'causal-snapshot')
    ledger=tmp_path/'ledger.json'
    ledger.write_text('{"schema":"SMART_SIGNAL_LEDGER_1","events":[]}',encoding='utf-8')
    return {
        "status":"RESET_READY",
        "engineering_activation_file":"activation.json",
        "engineering_activation_sha256":"activation-sha",
        "state_paths":{
            "ledger":"ledger.json",
            "state":"state.json",
            "activation_authority":"activation.json.auth",
            "expansion_registry":"expansion.json",
            "freeze":"freeze.json",
        },
        "data_file":"data.xlsx",
        "data_sha256":fp.sha256_file(data),
        "immutable_history_snapshot":True,
        "target_contest":3054,
        "cutoff_contest":3053,
    }


def _wire(monkeypatch,tmp_path,schedule):
    active=_active(tmp_path)
    monkeypatch.setattr(fp,'verify_active_epoch',lambda _p:active)
    monkeypatch.setattr(fp,'verify_activation',lambda *_a,**_k:{"sha256":"activation-sha"})
    monkeypatch.setattr(fp,'load_ledger',lambda _p:{"schema":"SMART_SIGNAL_LEDGER_1","events":[]})
    monkeypatch.setattr(fp.engine,'load_draws',lambda _p:(np.zeros((1,6),dtype=int),np.asarray([3053],dtype=int)))
    monkeypatch.setattr(fp,'resolve_target_schedule',lambda *_a,**_k:schedule)
    monkeypatch.setattr(fp,'validate_manual_generation',lambda *_a,**_k:{'schema':'TEST','target_contest':4,'epoch_id':'test','data_sha256':'x'})
    return active


def test_full_process_blocks_after_deadline_before_any_freeze(monkeypatch,tmp_path):
    schedule={"scheduled_datetime":"2020-01-01T11:00:00-03:00","result_used":False,"target_date":"01/01/2020"}
    _wire(monkeypatch,tmp_path,schedule)
    called={"freeze":False,"integration":False}
    def forbidden_freeze(*a,**k):
        called["freeze"]=True
        raise AssertionError('freeze must not be called after deadline')
    def forbidden_integration(*a,**k):
        called["integration"]=True
        raise AssertionError('integration must not be reached when preconditions fail')
    monkeypatch.setattr(fp,'freeze_champion_challenger',forbidden_freeze)
    monkeypatch.setattr(fp,'write_total_integration',forbidden_integration)
    with pytest.raises(RuntimeError,match='full process preconditions failed') as exc:
        fp.run_full_process(tmp_path, manual_generation_authorized=True)
    assert "'freeze_window_open': False" in str(exc.value)
    assert called=={"freeze":False,"integration":False}


def test_full_process_before_deadline_crosses_temporal_guard(monkeypatch,tmp_path):
    schedule={"scheduled_datetime":"2099-01-01T11:00:00-03:00","result_used":False,"target_date":"01/01/2099"}
    _wire(monkeypatch,tmp_path,schedule)
    class ReachedPreGate(RuntimeError): pass
    monkeypatch.setattr(fp,'write_total_integration',lambda *_a,**_k:(_ for _ in ()).throw(ReachedPreGate('reached pre-freeze integration')))
    monkeypatch.setattr(fp,'freeze_champion_challenger',lambda *_a,**_k:(_ for _ in ()).throw(AssertionError('freeze should not be reached in this test')))
    with pytest.raises(ReachedPreGate,match='reached pre-freeze integration'):
        fp.run_full_process(tmp_path, manual_generation_authorized=True)



def test_operator_target_without_caixa_draw_time_reaches_generation_gate(monkeypatch,tmp_path):
    schedule={"authority":"OPERATOR_SELECTED_TARGET", "scheduled_datetime":None,
              "result_used":False, "target_date":None,
              "target_contest":3054}
    _wire(monkeypatch,tmp_path,schedule)
    class ReachedPreGate(RuntimeError): pass
    monkeypatch.setattr(fp,'write_total_integration',lambda *_a,**_k:
                        (_ for _ in ()).throw(ReachedPreGate('operator target authorized')))
    with pytest.raises(ReachedPreGate,match='operator target authorized'):
        fp.run_full_process(tmp_path, manual_generation_authorized=True)
