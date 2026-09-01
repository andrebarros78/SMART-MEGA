from pathlib import Path
p=Path(__file__).resolve().parents[1]/'test_smart_independent_audit.py'
s=p.read_text(encoding='utf-8-sig')
add=r'''


def _legacy_3051_fixture(base: Path):
    base.mkdir(parents=True, exist_ok=True)
    pre=base/'pre3050.xlsx'; result=base/'result3051.xlsx'; state=base/'state.json'; freeze=base/'freeze.json'; ledger=base/'ledger.json'
    cols=['Concurso','Data do Sorteio']+[f'Bola{i}' for i in range(1,7)]+['Observacao']
    pre_df=pd.DataFrame([{
        'Concurso':3050,'Data do Sorteio':pd.Timestamp('2026-08-27'),
        'Bola1':11,'Bola2':14,'Bola3':30,'Bola4':38,'Bola5':49,'Bola6':55,'Observacao':None,
    }],columns=cols)
    target_row={
        'Concurso':3051,'Data do Sorteio':pd.Timestamp('2026-08-30'),
        'Bola1':11,'Bola2':15,'Bola3':20,'Bola4':21,'Bola5':38,'Bola6':48,'Observacao':None,
    }
    result_df=pd.concat([pre_df,pd.DataFrame([target_row],columns=cols)],ignore_index=True)
    pre_df.to_excel(pre,index=False); result_df.to_excel(result,index=False)
    state.write_text('{"state":3050}',encoding='utf-8')
    champion=[11,27,10,30,53,46]; challenger=[11,27,10,30,53,43]
    frozen={
        'schema':'SMART_CHAMPION_CHALLENGER_FREEZE_2','target_contest':3051,'cutoff_contest':3050,
        'frozen_before_result':True,'causal_cutoff':True,'data_file':pre.name,'data_sha256':_sha(pre),
        'engine_sha256':'a'*64,'signal_state_file':state.name,'signal_state_sha256':_sha(state),
        'champion':{'top6':champion},'challenger':{'top6':challenger},
    }
    freeze.write_text(json.dumps(frozen),encoding='utf-8'); fsha=_sha(freeze)
    actual=[11,15,20,21,38,48]; ch=len(set(champion)&set(actual)); hh=len(set(challenger)&set(actual))
    original='8'*64
    fr={
        'event_type':'FREEZE','target_contest':3051,'cutoff_contest':3050,'created_utc':'2026-08-30T16:00:00+00:00',
        'frozen_before_result':True,'causal_cutoff':True,'freeze_file':freeze.name,'freeze_sha256':fsha,'data_sha256':_sha(pre),
        'champion_top6':champion,'challenger_top6':challenger,'hashes':{'engine':'a'*64,'state':_sha(state)},
    }
    ad={
        'event_type':'ADJUDICATION','target_contest':3051,'created_utc':'2026-08-30T16:30:00+00:00','freeze_sha256':fsha,
        'result_data_file':result.name,'result_data_sha256':original,'actual_numbers':actual,
        'champion_hits':ch,'challenger_hits':hh,'difference_hits':hh-ch,
        'e_value_after':1.0*(1.0+ia.E_BET_LAMBDA*((hh-ch)/6.0)),
    }
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}),encoding='utf-8')
    proof={
        'schema':ia.LEGACY_CONTINUITY_SCHEMA,'target_contest':3051,
        'original_adjudicated_result_sha256':original,'current_result_sha256':_sha(result),
        'frozen_prefix_sha256':_sha(pre),'prefix_semantic_sha256':ia.semantic_dataframe_sha256(pre_df),
        'current_semantic_sha256':ia.semantic_dataframe_sha256(result_df),'target_numbers':actual,
    }
    pp=base/'SMART_P14_LEGACY_RESULT_CONTINUITY_3051.json'; pp.write_text(json.dumps(proof),encoding='utf-8')
    return ledger,pre,result,freeze,state,fr,ad,proof,pp


def test_p14_legacy_3051_continuity_accepts_only_full_semantic_equivalence(tmp_path: Path):
    ledger,pre,result,freeze,state,fr,ad,proof,pp=_legacy_3051_fixture(tmp_path)
    out=ia.audit_prospective_ledger(tmp_path,ledger)
    assert out['status']=='PASS' and out['legacy_result_continuity_used'] is True
    row=out['pairs'][0]
    assert row['result_binary_hash_exact'] is False
    assert row['result_data_hash_verified'] is False
    assert row['legacy_result_continuity']['exact_prefix_semantic_equal'] is True
    assert row['legacy_result_continuity']['target_numbers']==[11,15,20,21,38,48]
    assert ia.policy_snapshot()['legacy_result_continuity_target']==3051


def test_p14_legacy_continuity_is_forbidden_outside_3051(tmp_path: Path):
    ledger,pre,result,freeze,state,fr,ad,proof,pp=_legacy_3051_fixture(tmp_path)
    frozen=json.loads(freeze.read_text())
    with pytest.raises(ValueError,match='only for contest 3051'):
        ia.audit_legacy_result_continuity(tmp_path,3050,ad,frozen,pre,result)


def _legacy_direct(base: Path):
    ledger,pre,result,freeze,state,fr,ad,proof,pp=_legacy_3051_fixture(base)
    return pre,result,json.loads(freeze.read_text()),ad,proof,pp


def test_p14_legacy_proof_metadata_guards(tmp_path: Path):
    cases=[
        ('schema',lambda p: p.__setitem__('schema','BAD'),'invalid legacy continuity proof'),
        ('original',lambda p: p.__setitem__('original_adjudicated_result_sha256','0'*64),'original adjudicated hash mismatch'),
        ('current',lambda p: p.__setitem__('current_result_sha256','0'*64),'current result hash mismatch'),
        ('prefix',lambda p: p.__setitem__('frozen_prefix_sha256','0'*64),'frozen prefix hash mismatch'),
        ('semantic',lambda p: p.__setitem__('prefix_semantic_sha256','0'*64),'proof semantic prefix hash mismatch'),
        ('targetnums',lambda p: p.__setitem__('target_numbers',[1,2,3,4,5,6]),'target result does not match'),
        ('currentsemantic',lambda p: p.__setitem__('current_semantic_sha256','0'*64),'current semantic hash mismatch'),
    ]
    for name,mut,msg in cases:
        base=tmp_path/name; pre,result,frozen,ad,proof,pp=_legacy_direct(base)
        mut(proof); pp.write_text(json.dumps(proof),encoding='utf-8')
        with pytest.raises(ValueError,match=msg):
            ia.audit_legacy_result_continuity(base,3051,ad,frozen,pre,result)


def test_p14_legacy_file_structure_and_semantic_guards(tmp_path: Path):
    # columns mismatch
    base=tmp_path/'columns'; pre,result,frozen,ad,proof,pp=_legacy_direct(base)
    df=pd.read_excel(result); df['Extra']=1; df.to_excel(result,index=False); proof['current_result_sha256']=_sha(result); pp.write_text(json.dumps(proof))
    with pytest.raises(ValueError,match='columns differ'): ia.audit_legacy_result_continuity(base,3051,ad,frozen,pre,result)
    # row count mismatch
    base=tmp_path/'rows'; pre,result,frozen,ad,proof,pp=_legacy_direct(base)
    df=pd.read_excel(result); pd.concat([df,df.iloc[-1:]],ignore_index=True).to_excel(result,index=False); proof['current_result_sha256']=_sha(result); pp.write_text(json.dumps(proof))
    with pytest.raises(ValueError,match='prefix plus one contest'): ia.audit_legacy_result_continuity(base,3051,ad,frozen,pre,result)
    # semantic prefix mismatch
    base=tmp_path/'prefixsem'; pre,result,frozen,ad,proof,pp=_legacy_direct(base)
    df=pd.read_excel(result); df.loc[0,'Bola1']=12; df.to_excel(result,index=False); proof['current_result_sha256']=_sha(result); pp.write_text(json.dumps(proof))
    with pytest.raises(ValueError,match='prefix differs semantically'): ia.audit_legacy_result_continuity(base,3051,ad,frozen,pre,result)
    # wrong final contest
    base=tmp_path/'final'; pre,result,frozen,ad,proof,pp=_legacy_direct(base)
    df=pd.read_excel(result); df.loc[len(df)-1,'Concurso']=3052; df.to_excel(result,index=False); proof['current_result_sha256']=_sha(result); pp.write_text(json.dumps(proof))
    with pytest.raises(ValueError,match='beyond target or wrong final contest'): ia.audit_legacy_result_continuity(base,3051,ad,frozen,pre,result)


def test_p14_legacy_frozen_hash_guard_and_exact_binary_path(tmp_path: Path):
    base=tmp_path/'fh'; pre,result,frozen,ad,proof,pp=_legacy_direct(base)
    frozen['data_sha256']='0'*64
    with pytest.raises(ValueError,match='frozen prefix hash mismatch'):
        ia.audit_legacy_result_continuity(base,3051,ad,frozen,pre,result)
    # Ordinary exact-binary audit remains on the strict path and does not use legacy continuity.
    strict=tmp_path/'strict'; strict.mkdir()
    ledger,*_= _pair_fixture(strict)
    out=ia.audit_prospective_ledger(strict,ledger)
    assert out['legacy_result_continuity_used'] is False
    assert out['pairs'][0]['result_binary_hash_exact'] is True
    assert out['pairs'][0]['result_data_hash_verified'] is True
'''
if '_legacy_3051_fixture' not in s:
    s+=add
p.write_text(s,encoding='utf-8')
print('P14 legacy continuity tests appended')
