from pathlib import Path
p=Path(__file__).resolve().parents[1]/'test_smart_independent_audit.py'
s=p.read_text(encoding='utf-8')
add=r'''


def test_p14_remaining_coverage_binding_guards(tmp_path: Path):
    binding = _coverage_binding(tmp_path, 'missing_source.py')
    (tmp_path/'missing_source.py').unlink()
    with pytest.raises(ValueError): ia.audit_coverage_binding(tmp_path, binding)

    binding = _coverage_binding(tmp_path, 'report_tamper.py')
    b=json.loads(binding.read_text()); report=tmp_path/b['coverage_report_file']
    report.write_text(report.read_text()+' ')
    with pytest.raises(ValueError): ia.audit_coverage_binding(tmp_path, binding)

    binding = _coverage_binding(tmp_path, 'line_incomplete.py')
    b=json.loads(binding.read_text()); report=tmp_path/b['coverage_report_file']; r=json.loads(report.read_text())
    sm=r['files']['line_incomplete.py']['summary']; sm['covered_lines']=0; sm['num_statements']=1; sm['missing_lines']=0; sm['missing_branches']=0
    report.write_text(json.dumps(r)); b['coverage_report_sha256']=_sha(report); binding.write_text(json.dumps(b))
    with pytest.raises(ValueError): ia.audit_coverage_binding(tmp_path, binding)


def test_p14_contest_number_guards():
    with pytest.raises(ValueError): ia._contest_numbers(pd.DataFrame([{'x':1}]), 1)
    row={'Concurso':1}; row.update({f'Bola{i}':i for i in range(1,7)})
    with pytest.raises(ValueError): ia._contest_numbers(pd.DataFrame([row,row]), 1)


def test_p14_ledger_event_hash_and_supersede_guards(tmp_path: Path):
    ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path)
    dup=copy.deepcopy(fr)
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,dup,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)

    ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path)
    badsup={'event_type':'SUPERSEDE','target_contest':ad['target_contest'],'old_freeze_sha256':'bad','new_freeze_sha256':fr['freeze_sha256']}
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,badsup,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)


def _rewrite_frozen_case(tmp_path: Path, mutate):
    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path)
    frozen=json.loads(freeze.read_text())
    mutate(frozen, fr, ad, pre, result, state, actual)
    freeze.write_text(json.dumps(frozen),encoding='utf-8')
    fr['freeze_sha256']=_sha(freeze); ad['freeze_sha256']=fr['freeze_sha256']
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}),encoding='utf-8')
    return ledger


def test_p14_frozen_artifact_semantic_guards(tmp_path: Path):
    ledger=_rewrite_frozen_case(tmp_path, lambda f,fr,ad,pre,result,state,actual: f.__setitem__('target_contest',999))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path,ledger)

    def flags(f,*_): f['causal_cutoff']=False
    ledger=_rewrite_frozen_case(tmp_path,flags)
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path,ledger)

    def data_disagree(f,fr,*_): f['data_sha256']='c'*64
    ledger=_rewrite_frozen_case(tmp_path,data_disagree)
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path,ledger)

    def champ(f,*_): f['champion']['top6']=[7,8,9,10,11,12]
    ledger=_rewrite_frozen_case(tmp_path,champ)
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path,ledger)

    def chall(f,*_): f['challenger']['top6']=[13,14,15,16,17,18]
    ledger=_rewrite_frozen_case(tmp_path,chall)
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path,ledger)

    ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path)
    fr['hashes']={}; ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path,ledger)


def test_p14_leakage_and_cutoff_classification_guards(tmp_path: Path):
    ledger, pre, result, freeze, state, fr, ad, _ = _pair_fixture(tmp_path)
    future=pd.read_excel(result).iloc[-1:]
    df=pd.read_excel(pre); pd.concat([df,future],ignore_index=True).to_excel(pre,index=False)
    frozen=json.loads(freeze.read_text()); frozen['data_sha256']=_sha(pre); freeze.write_text(json.dumps(frozen))
    fr['data_sha256']=_sha(pre); fr['freeze_sha256']=_sha(freeze); ad['freeze_sha256']=fr['freeze_sha256']
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError, match='future result leaked'): ia.audit_prospective_ledger(tmp_path,ledger)

    ledger, pre, result, freeze, state, fr, ad, _ = _pair_fixture(tmp_path)
    df=pd.read_excel(pre).iloc[:-1].copy(); df.to_excel(pre,index=False)
    frozen=json.loads(freeze.read_text()); frozen['data_sha256']=_sha(pre); freeze.write_text(json.dumps(frozen))
    fr['data_sha256']=_sha(pre); fr['freeze_sha256']=_sha(freeze); ad['freeze_sha256']=fr['freeze_sha256']
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError, match='does not end'): ia.audit_prospective_ledger(tmp_path,ledger)


def test_p14_ledger_ignores_unrelated_events_but_scans_post_adjudication_events(tmp_path: Path):
    ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path)
    other={'event_type':'TELEMETRY','target_contest':9999}
    derived={'event_type':'ATTRIBUTION','target_contest':ad['target_contest']}
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[other,fr,ad,derived]}))
    assert ia.audit_prospective_ledger(tmp_path,ledger)['status']=='PASS'


def test_p14_replay_detects_champion_nondeterminism(monkeypatch, tmp_path: Path):
    data=tmp_path/'d.xlsx'; _dataset(12).to_excel(data,index=False)
    calls={'n':0}
    def fake(draws,start):
        calls['n']+=1
        return {'top6':[1,2,3,4,5,6], 'nonce':calls['n']}
    monkeypatch.setattr(ia.champion_engine,'current_policy',fake)
    with pytest.raises(ValueError, match='Champion replay'): ia.audit_deterministic_replay(tmp_path,data,13,start=5)


def test_p14_replay_detects_challenger_nondeterminism_and_bad_cutoff(monkeypatch, tmp_path: Path):
    data=tmp_path/'d.xlsx'; _dataset(12).to_excel(data,index=False)
    class Pred:
        def __init__(self, nonce=0, cutoff=12):
            self.nonce=nonce; self.cutoff_contest=cutoff; self.target_contest=13; self.top6=[1,2,3,4,5,6]
        def as_dict(self): return {'generated_utc':'x','nonce':self.nonce,'top6':self.top6}
    class AgentND:
        calls=0
        def __init__(self,start): pass
        def predict_next(self,*args,**kwargs):
            type(self).calls+=1; return Pred(type(self).calls), {'rows':[]}
    monkeypatch.setattr(ia,'SmartSignalAgent',AgentND)
    with pytest.raises(ValueError, match='Challenger replay'): ia.audit_deterministic_replay(tmp_path,data,13,start=5)

    class AgentBad:
        def __init__(self,start): pass
        def predict_next(self,*args,**kwargs): return Pred(0,cutoff=11), {'rows':[]}
    monkeypatch.setattr(ia,'SmartSignalAgent',AgentBad)
    with pytest.raises(ValueError, match='causal target/cutoff'): ia.audit_deterministic_replay(tmp_path,data,13,start=5)
'''
if 'test_p14_remaining_coverage_binding_guards' not in s:
    s += add
p.write_text(s,encoding='utf-8')
print('P14 coverage tests appended')
