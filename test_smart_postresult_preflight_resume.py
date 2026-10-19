"""Read-only recovery is admissible only when backed by an existing adjudication."""
from pathlib import Path
import pytest
import smart_operator as op

@pytest.fixture
def scenario(tmp_path, monkeypatch):
    from test_smart_result_consumption_readiness import _setup, _observation
    _setup(monkeypatch,tmp_path)
    ledger_path=tmp_path/'runtime'/'learning_epochs'/'operator-test'/'SMART_SIGNAL_LEDGER.json'
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text('{}')
    active={
        'status':'FROZEN','target_contest':3068,
        'target_schedule':{'authority':'OPERATOR_SELECTED_TARGET','target_contest':3068,'target_date':None},
        'state_paths':{'ledger':str(ledger_path.relative_to(tmp_path))},
    }
    monkeypatch.setattr(op,'verify_active_epoch',lambda *a,**k: active)
    values={'event_type':'ADJUDICATION','target_contest':3068,
            'actual_numbers':[1,7,13,25,41,59],'freeze_sha256':'b'*64,'retroactive_rewrite':False}
    frozen={'event_type':'FREEZE','target_contest':3068,'freeze_sha256':'b'*64}
    ledger={'events':[frozen,values]}
    monkeypatch.setattr(op,'load_ledger',lambda *a,**kw:ledger)
    monkeypatch.setattr(op,'active_freeze',lambda *a,**kw:frozen)
    monkeypatch.setattr(op.terminal_executor,'probe',
        lambda *a,**kw:_observation(preflight_status='POST_RESULT_SEQUENCE_IN_PROGRESS_OR_COMPLETE',
                                   result_input_authority='OPERATOR',
                                   terminal_source_corroboration_authorized=False))
    return tmp_path,ledger,values

def test_adjudicated_operator_sequence_can_resume_readonly(scenario):
    root,ledger,record=scenario
    before=[(p,p.read_bytes()) for p in root.rglob('*') if p.is_file()]
    result=op.result_preflight_operation(root,3068)
    assert result['status']=='READY_TO_CONSUME'
    assert result['mutation_requires_explicit_dispatch'] is True
    assert result['result_input_authority']=='OPERATOR'
    assert result['primary_official_channel_validated'] is False
    assert result['dual_channel_corroborated'] is False
    assert before==[(p,p.read_bytes()) for p in root.rglob('*') if p.is_file()]

@pytest.mark.parametrize('change',[
    {'freeze_sha256':'0'*64},{'actual_numbers':[2,7,13,25,41,59]},
    {'target_contest':3067},{'retroactive_rewrite':True}
])
def test_recovery_rejects_inconsistent_adjudication(scenario,change):
    root,ledger,record=scenario
    record.update(change)
    pre=op.result_preflight_operation(root,3068)
    assert pre['status']=='BLOCKED_INTEGRITY'

def test_recovery_rejects_missing_target_adjudication(scenario):
    root,ledger,_=scenario
    ledger['events']=ledger['events'][:1]
    assert op.result_preflight_operation(root,3068)['status']=='BLOCKED_INTEGRITY'

def test_recovery_rejects_duplicate_adjudications(scenario):
    root,ledger,record=scenario
    ledger['events'].append(dict(record))
    assert op.result_preflight_operation(root,3068)['status']=='BLOCKED_INTEGRITY'
