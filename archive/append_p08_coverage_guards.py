from pathlib import Path
p=Path(__file__).resolve().parents[1]/'test_smart_meta_governor.py'
s=p.read_text(encoding='utf-8')
add=r'''

def test_p08_private_guard_coverage_complete(tmp_path: Path):
    import math
    import smart_meta_governor as mg
    # _softmax id and finiteness guards.
    with pytest.raises(ValueError, match='ids'):
        mg._softmax({'quality_dynamic': 0.0})
    bad_logs={pid:0.0 for pid in POLICY_IDS}; bad_logs['quality_dynamic']=float('nan')
    with pytest.raises(ValueError, match='finite'):
        mg._softmax(bad_logs)
    with pytest.raises(ValueError, match='prior_mix'):
        mg._regularized({pid:0.0 for pid in POLICY_IDS}, -0.1)
    # P07 payload guards: policies mismatch and invalid top6.
    good=_multi()
    bad=json.loads(json.dumps(good)); bad['policies'].pop('conservative')
    with pytest.raises(ValueError, match='policies mismatch'):
        mg._validate_multi(bad)
    bad=json.loads(json.dumps(good)); bad['policies']['quality_dynamic']['top6']=[1,1,2,3,4,5]
    with pytest.raises(ValueError, match='invalid top6'):
        mg._validate_multi(bad)
    # State-id guard.
    with pytest.raises(ValueError, match='state ids'):
        MetaGovernor(log_weights={'quality_dynamic':0.0})

    # Adjudication guard: P08 without P07 is invalid.
    fr={'snapshot':{'meta_governor':MetaGovernor().select(good)},'freeze_sha256':'x'}
    with pytest.raises(ValueError, match='requires P07'):
        adj._build_meta_governor_event(fr,[1,2,3,4,5,6],1)
    # P07 policy set incomplete is invalid.
    bad_multi=json.loads(json.dumps(good)); bad_multi['policies'].pop('conservative')
    fr={'snapshot':{'meta_governor':MetaGovernor().select(good),'multi_challengers':bad_multi},'freeze_sha256':'x'}
    with pytest.raises(ValueError, match='complete frozen P07 policies'):
        adj._build_meta_governor_event(fr,[1,2,3,4,5,6],1)

    # META_GOVERNOR event cannot predate adjudication.
    freeze=tmp_path/'pre_meta_f.json'; freeze.write_text('{}'); fh=cc.sha256(freeze)
    fr={'event_type':'FREEZE','target_contest':96,'freeze_file':str(freeze),'freeze_sha256':fh,
        'frozen_before_result':True,'causal_cutoff':True,'snapshot':{},
        'champion_top6':[1,2,3,4,5,6],'challenger_top6':[1,2,3,4,5,7]}
    pre={'event_type':'META_GOVERNOR','target_contest':96,'freeze_sha256':fh}
    ledger=tmp_path/'pre_meta_l.json'; cc.write_ledger(ledger,{'schema':cc.LEDGER_SCHEMA,'events':[fr,pre]})
    row={'Concurso':96}; row.update({f'Bola{i}':i for i in range(1,7)})
    result=tmp_path/'pre_meta_r.xlsx'; pd.DataFrame([row]).to_excel(result,index=False)
    with pytest.raises(ValueError, match='meta-governor evaluation cannot predate'):
        adj.adjudicate(result,96,ledger)
'''
if 'test_p08_private_guard_coverage_complete' not in s:
    p.write_text(s+add,encoding='utf-8')
print('ok')
