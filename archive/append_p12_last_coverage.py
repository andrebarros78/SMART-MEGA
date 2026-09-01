from pathlib import Path
p=Path(__file__).resolve().parents[1]/'test_smart_sequential_prospective_proof.py'
s=p.read_text(encoding='utf-8-sig')
add=r'''

def test_p12_freeze_only_is_valid_pre_result_but_learning_is_blocked(tmp_path: Path):
    L={'events':[_minimal_freeze()]}
    out=sp.validate_target_sequence(L,10)
    assert out['adjudicated'] is False and out['learning_recorded'] is False
    ledger=tmp_path/'ledger.json'; state=tmp_path/'state.json'
    ledger.write_text(json.dumps({'schema':cc.LEDGER_SCHEMA,'events':[_minimal_freeze()]}))
    state.write_text(json.dumps({'schema':'SMART_SIGNAL_STATE_9','last_contest':10}))
    with pytest.raises(ValueError): sp.append_learning_update(ledger,10,state)
'''
if 'test_p12_freeze_only_is_valid_pre_result_but_learning_is_blocked' not in s: s+=add
p.write_text(s,encoding='utf-8')
print('last p12 coverage test appended')
