from pathlib import Path
p=Path(__file__).resolve().parents[1]/'test_smart_sequential_prospective_proof.py'
s=p.read_text(encoding='utf-8-sig')
add=r'''

def _learn_event(adj, target=10, state_file='state.json', state_sha='x'):
    return {'event_type':sp.LEARNING_EVENT,'target_contest':target,
            'source_adjudication_sha256':sp.canonical_event_hash(adj),'source_freeze_sha256':adj['freeze_sha256'],
            'state_file':state_file,'state_sha256':state_sha,'trained_through_contest':target,
            'learning_after_adjudication':True,'retroactive_rewrite':False}


def test_p12_all_sequence_guard_branches(tmp_path: Path):
    f=_minimal_freeze(); a=_minimal_adj()
    with pytest.raises(ValueError): sp.validate_target_sequence([],10)
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,copy.deepcopy(a)]},10)
    l=_learn_event(a)
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,l,copy.deepcopy(l)]},10)
    p1={'event_type':sp.PROOF_EVENT,'target_contest':10}; p2=copy.deepcopy(p1)
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,l,p1,p2]},10)
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a]},10,require_learning=True)
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,l]},10,require_proof=True)
    f2=_minimal_freeze(10,'b'*64); sup={'event_type':'SUPERSEDE','target_contest':10,'old_freeze_sha256':'b'*64,'new_freeze_sha256':'a'*64}
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,f2,sup]},10)
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,{'event_type':'ATTRIBUTION','target_contest':10},a]},10)
    early=_learn_event(a)
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,early,a]},10)
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,l,{'event_type':'ATTRIBUTION','target_contest':10}]},10)
    bad=copy.deepcopy(l); bad['source_adjudication_sha256']='0'*64
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,bad]},10)
    bad=copy.deepcopy(l); bad['trained_through_contest']=9
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,bad]},10)
    bad=copy.deepcopy(l); bad['learning_after_adjudication']=False
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,bad]},10)
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,{'event_type':sp.PROOF_EVENT,'target_contest':10}]},10)
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,{'event_type':sp.PROOF_EVENT,'target_contest':10},l]},10)
    wrong={'event_type':sp.PROOF_EVENT,'target_contest':10,'event_hashes':[],'sequence_sha256':'bad'}
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,l,wrong]},10)
    assert len(sp._event_chain([(0,f)],stop_before_proof=False)[0])==1


def test_p12_relative_file_verification_and_io_guards(tmp_path: Path):
    freeze=tmp_path/'f.json'; freeze.write_text('{}'); fsha=sp.sha256_file(freeze)
    state=tmp_path/'state.json'; state.write_text(json.dumps({'schema':'SMART_SIGNAL_STATE_9','last_contest':10})); ssha=sp.sha256_file(state)
    f=_minimal_freeze(10,fsha); f['freeze_file']='f.json'; a=_minimal_adj(10,fsha); l=_learn_event(a,state_file='state.json',state_sha=ssha)
    out=sp.validate_target_sequence({'events':[f,a,l]},10,verify_files=True,root=tmp_path)
    assert out['valid']
    bad=copy.deepcopy(l); bad['state_sha256']='0'*64
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[f,a,bad]},10,verify_files=True,root=tmp_path)
    badf=copy.deepcopy(f); badf['freeze_sha256']='0'*64; bada=_minimal_adj(10,'0'*64); badl=_learn_event(bada,state_file='state.json',state_sha=ssha)
    with pytest.raises(ValueError): sp.validate_target_sequence({'events':[badf,bada,badl]},10,verify_files=True,root=tmp_path)
    missing=tmp_path/'none.json'; assert sp._load_ledger(missing)['events']==[]
    invalid=tmp_path/'badledger.json'; invalid.write_text(json.dumps({'schema':'BAD','events':[]}))
    with pytest.raises(ValueError): sp._load_ledger(invalid)
    good=tmp_path/'goodledger.json'; assert len(sp._write_ledger(good,{'schema':sp.LEDGER_SCHEMA,'events':[]}))==64


def test_p12_append_input_guards_and_unreachable_prefix_defense(monkeypatch, tmp_path: Path):
    ledger=tmp_path/'ledger.json'; state=tmp_path/'state.json'
    ledger.write_text(json.dumps({'schema':cc.LEDGER_SCHEMA,'events':[_minimal_freeze(),_minimal_adj()]}))
    with pytest.raises(ValueError): sp.append_learning_update(ledger,10,tmp_path/'missing_state.json')
    state.write_text(json.dumps({'schema':'SMART_SIGNAL_STATE_9','last_contest':10}))
    with pytest.raises(ValueError): sp.append_learning_update(ledger,10,state,tmp_path/'missing.xlsx')

    class MutatingList(list):
        def append(self, item):
            if self: self[0]['mutated']=True
            super().append(item)
    base={'schema':sp.LEDGER_SCHEMA,'events':MutatingList([_minimal_freeze(),_minimal_adj()])}
    monkeypatch.setattr(sp,'_load_ledger',lambda path: base)
    with pytest.raises(RuntimeError): sp.append_learning_update(tmp_path/'x.json',10,state)

    a=_minimal_adj(); l=_learn_event(a,state_file=str(state),state_sha=sp.sha256_file(state))
    base2={'schema':sp.LEDGER_SCHEMA,'events':MutatingList([_minimal_freeze(),a,l])}
    monkeypatch.setattr(sp,'_load_ledger',lambda path: base2)
    with pytest.raises(RuntimeError): sp.append_sequence_proof(tmp_path/'y.json',10)
'''
if 'test_p12_all_sequence_guard_branches' not in s:
    s += add
p.write_text(s,encoding='utf-8')
print('p12 coverage guards appended')
