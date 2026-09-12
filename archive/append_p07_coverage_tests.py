from pathlib import Path
p=Path(r'C:\New Projet\SMART-MEGA\test_smart_multi_challengers.py')
s=p.read_text(encoding='utf-8-sig')
append=r'''

def test_private_weight_guard_and_cap_paths_for_coverage():
    import smart_multi_challengers as sm
    with pytest.raises(ValueError): sm._normalize({})
    with pytest.raises(ValueError): sm._normalize({'a':0.0,'b':0.0})
    with pytest.raises(ValueError): sm._normalize({'a':float('nan')})
    with pytest.raises(ValueError): sm._cap_expert({'a':.5,'b':.5},0.0)
    with pytest.raises(ValueError): sm._cap_expert({'a':.5,'b':.5},0.4)
    # Feasible cap with zero free mass exercises defensive redistribution branch.
    got=sm._cap_expert({'a':1.0,'b':0.0,'c':0.0},0.5)
    assert abs(sum(got.values())-1.0)<1e-12
    with pytest.raises(ValueError): sm._cap_family({'a':.5,'b':.5},{'a':'x'},.7)
    assert sm._cap_family({'a':.5,'b':.5},{'a':'x','b':'x'},.7)=={'a':.5,'b':.5}
    with pytest.raises(ValueError): sm._cap_family({'a':.5,'b':.5},{'a':'x','b':'y'},.4)
    got=sm._cap_family({'a':1.0,'b':0.0},{'a':'x','b':'y'},.7)
    assert abs(got['a']-.7)<1e-12 and abs(got['b']-.3)<1e-12
    with pytest.raises(ValueError): sm._equal_family_weights([], {})


def test_invalid_factor_and_redundancy_type_guards():
    scores,w,m,f,r=_inputs()
    badm={k:dict(v) for k,v in m.items()}; badm['freq25']['regime_context']=0.0
    with pytest.raises(ValueError): build_multi_challengers(scores,w,badm,f,r,{'active':True})
    with pytest.raises(ValueError): build_multi_challengers(scores,w,m,f,None,{'active':True})


def test_adjudication_multi_snapshot_guards_and_predate_guard(tmp_path: Path):
    scores,w,m,f,r=_inputs(); multi=build_multi_challengers(scores,w,m,f,r,{'active':True})
    bad={'snapshot':{'multi_challengers':dict(multi)}}
    bad['snapshot']['multi_challengers']['schema']='BAD'
    with pytest.raises(ValueError): adj._build_multi_challenger_event(bad,[1,2,3,4,5,6],1)
    bad2={'snapshot':{'multi_challengers':json.loads(json.dumps(multi))}}
    bad2['snapshot']['multi_challengers']['policies'].pop('conservative')
    with pytest.raises(ValueError): adj._build_multi_challenger_event(bad2,[1,2,3,4,5,6],1)
    bad3={'snapshot':{'multi_challengers':json.loads(json.dumps(multi))}}
    bad3['snapshot']['multi_challengers']['policies']['quality_dynamic']['top6']=[1,1,2,3,4,5]
    with pytest.raises(ValueError): adj._build_multi_challenger_event(bad3,[1,2,3,4,5,6],1)

    freeze=tmp_path/'pre_f.json'; freeze.write_text('{}'); fh=cc.sha256(freeze)
    fr={'event_type':'FREEZE','target_contest':92,'freeze_file':str(freeze),'freeze_sha256':fh,'frozen_before_result':True,'causal_cutoff':True,
        'snapshot':{},'champion_top6':[1,2,3,4,5,6],'challenger_top6':[1,2,3,4,5,7]}
    pre={'event_type':'MULTI_CHALLENGERS','target_contest':92,'freeze_sha256':fh}
    ledger=tmp_path/'pre_l.json'; cc.write_ledger(ledger,{'schema':cc.LEDGER_SCHEMA,'events':[fr,pre]})
    row={'Concurso':92}; row.update({f'Bola{i}':i for i in range(1,7)})
    result=tmp_path/'pre_r.xlsx'; pd.DataFrame([row]).to_excel(result,index=False)
    with pytest.raises(ValueError,match='multi-challenger evaluation cannot predate'):
        adj.adjudicate(result,92,ledger)


def test_agent_guard_detects_primary_policy_mismatch(monkeypatch):
    import smart_signal_agent as sa
    draws=_draws(seed=702,n=55); contests=np.arange(1,56)
    original=sa.build_multi_challengers
    def bad(*args,**kwargs):
        out=original(*args,**kwargs)
        out['policies']['quality_dynamic']['top6']=list(reversed(out['policies']['quality_dynamic']['top6']))
        return out
    monkeypatch.setattr(sa,'build_multi_challengers',bad)
    with pytest.raises(RuntimeError,match='must reproduce primary'):
        sa.SmartSignalAgent(start=30).predict_next(draws,contests,target_contest=56)
'''
if 'test_private_weight_guard_and_cap_paths_for_coverage' not in s:
    s += append
p.write_text(s,encoding='utf-8')
print('appended')