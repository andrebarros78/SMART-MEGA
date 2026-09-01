from __future__ import annotations
from smart_test_helpers import make_valid_freeze_fixture, bind_valid_freeze_fixture
import json
from pathlib import Path
import numpy as np
import pytest

from smart_signal_interactions import InteractionTracker, analyze_interactions, analyze_snapshot
import adjudicate_signal_challenger as adj
import smart_champion_challenger as cc


def scores():
    base=np.linspace(0,1,60)
    return {'a':base.copy(),'b':base[::-1].copy(),'c':np.roll(base,7)}


def test_pair_and_triple_interactions_complete_and_hashed():
    s=scores(); s['d']=np.roll(np.linspace(0,1,60),13); w={'a':.30,'b':.25,'c':.25,'d':.20}; actual=[55,56,57,58,59,60]
    r=analyze_interactions(s,w,actual,3)
    assert len(r['pair_interactions'])==6 and len(r['triple_interactions'])==4
    assert len(r['interaction_sha256'])==64 and r['weight_effect_enabled'] is False
    assert r==analyze_interactions(s,w,actual,3)


def test_tracker_updates_every_pair_and_keeps_measurement_only():
    s=scores(); t=InteractionTracker(tuple(s))
    for _ in range(20): t.update(s,{'a':.4,'b':.35,'c':.25},[55,56,57,58,59,60])
    m=t.metrics(); assert m['pair_count']==3 and not m['weight_effect_enabled']
    assert all(v['observations']==20 for v in m['pairs'].values())


def test_guards():
    s=scores()
    with pytest.raises(ValueError): analyze_interactions(s,{'a':1},[1,2,3,4,5,6])
    with pytest.raises(ValueError): analyze_interactions(s,{'a':.4,'b':.35,'c':.25},[1,1,2,3,4,5])
    with pytest.raises(ValueError): analyze_interactions(s,{'a':.4,'b':.35,'c':.25},[1,2,3,4,5,6],1)
    with pytest.raises(ValueError): InteractionTracker(('a','a'))
    t=InteractionTracker(('a','b'))
    with pytest.raises(ValueError): t.pairs['a|b'].update(float('nan'))


def make_snapshot():
    s=scores(); raw={}
    for n,a in s.items(): raw[n]={'values':{str(i+1):float(a[i]) for i in range(60)}}
    weights={'a':.4,'b':.35,'c':.25}
    quality={n:{'quality':1.0,'confidence':1.0} for n in raw}
    return {'raw_signals':raw,'weights':weights,'quality_metrics':quality}


def test_snapshot_adapter_and_bad_values():
    r=analyze_snapshot(make_snapshot(),[55,56,57,58,59,60]); assert len(r['pair_interactions'])==3
    x=make_snapshot(); x['raw_signals']['a']['values'].pop('60')
    with pytest.raises(ValueError): analyze_snapshot(x,[1,2,3,4,5,6])


def test_append_interaction_for_existing_idempotent(tmp_path: Path):
    freeze=tmp_path/'f.json'; freeze.write_text('{}'); fh=cc.sha256(freeze)
    fr={'event_type':'FREEZE','target_contest':9,'freeze_file':str(freeze),'freeze_sha256':fh,'frozen_before_result':True,'causal_cutoff':True,'snapshot':make_snapshot(),'champion_top6':[1,2,3,4,5,6],'challenger_top6':[1,2,3,4,5,7]}
    fr=bind_valid_freeze_fixture(cc, freeze, fr)
    ad={'event_type':'ADJUDICATION','target_contest':9,'freeze_sha256':fr['freeze_sha256'],'actual_numbers':[1,2,3,4,5,6],'challenger_hits':5,'champion_hits':6,'e_value_after':1.0}
    lp=tmp_path/'l.json'; cc.write_ledger(lp,{'schema':cc.LEDGER_SCHEMA,'events':[fr,ad]})
    r=adj.append_interactions_for_existing(lp,9); assert r['status']=='INTERACTIONS_APPENDED'
    r2=adj.append_interactions_for_existing(lp,9); assert r2['status']=='ALREADY_INTERACTIONS_EVENT_PRESERVED'
    L=json.loads(lp.read_text()); ev=[x for x in L['events'] if x.get('event_type')=='INTERACTIONS']; assert len(ev)==1


def test_two_signal_pair_is_explicitly_unavailable_not_error():
    a=np.linspace(0,1,60); b=a[::-1]
    r=analyze_interactions({'a':a,'b':b},{'a':.6,'b':.4},[1,2,3,4,5,6],3)
    assert list(r['pair_interactions'])==['a|b']
    assert r['pair_interactions']['a|b']['available'] is False
    assert r['triple_interactions']=={}


def test_future_adjudication_appends_interactions_automatically(tmp_path: Path):
    import pandas as pd
    freeze=tmp_path/'f2.json'; freeze.write_text('{}'); fh=cc.sha256(freeze)
    fr={'event_type':'FREEZE','target_contest':11,'freeze_file':str(freeze),'freeze_sha256':fh,
        'frozen_before_result':True,'causal_cutoff':True,'snapshot':make_snapshot(),
        'champion_top6':[1,2,3,4,5,6],'challenger_top6':[1,2,3,4,5,7]}
    fr=bind_valid_freeze_fixture(cc, freeze, fr)
    lp=tmp_path/'l2.json'; cc.write_ledger(lp,{'schema':cc.LEDGER_SCHEMA,'events':[fr]})
    row={'Concurso':11}; row.update({f'Bola{i}':i for i in range(1,7)})
    result=tmp_path/'r.xlsx'; pd.DataFrame([row]).to_excel(result,index=False)
    out=adj.adjudicate(result,11,lp)
    assert len(out['interaction_sha256'])==64
    L=json.loads(lp.read_text()); types=[x['event_type'] for x in L['events']]
    assert types==['FREEZE','ADJUDICATION','ATTRIBUTION','MARGINAL_UTILITY','INTERACTIONS']
    ev=[x for x in L['events'] if x['event_type']=='INTERACTIONS'][0]
    assert len(ev['analysis']['pair_interactions'])==3
    assert ev['analysis']['weight_effect_enabled'] is False


def test_interaction_private_guard_paths_for_coverage():
    import smart_signal_interactions as si
    good=np.linspace(0,1,60)
    with pytest.raises(ValueError,match='60 finite'):
        si._inputs({'a':np.zeros(59)},{'a':1.0})
    with pytest.raises(ValueError,match='invalid weight'):
        si._inputs({'a':good},{'a':float('nan')})
    with pytest.raises(ValueError,match='positive mass'):
        si._inputs({'a':good},{'a':0.0})
    arrays={'a':good,'b':good[::-1]}
    with pytest.raises(ValueError,match='remove all'):
        si._aggregate(arrays,{'a':.5,'b':.5},('a','b'))
    with pytest.raises(ValueError,match='zero weight'):
        si._aggregate(arrays,{'a':1.0,'b':0.0},('a',))
    with pytest.raises(ValueError,match='snapshot requires'):
        si.analyze_snapshot({},[1,2,3,4,5,6])


def test_tracker_mismatch_and_unavailable_pair_branch():
    from smart_signal_interactions import InteractionTracker
    a=np.linspace(0,1,60); b=a[::-1]; c=np.roll(a,3)
    t=InteractionTracker(('a','b'))
    r=t.update({'a':a,'b':b},{'a':.6,'b':.4},[1,2,3,4,5,6])
    assert r['pair_interactions']['a|b']['available'] is False
    assert t.metrics()['pairs']['a|b']['observations']==0
    with pytest.raises(ValueError,match='interaction ids'):
        t.update({'a':a,'b':b,'c':c},{'a':.4,'b':.3,'c':.3},[1,2,3,4,5,6])


def test_interaction_ledger_error_guards_and_predate_adjudication(tmp_path: Path):
    # Missing adjudication.
    freeze=tmp_path/'f3.json'; freeze.write_text('{}'); fh=cc.sha256(freeze)
    fr={'event_type':'FREEZE','target_contest':12,'freeze_file':str(freeze),'freeze_sha256':fh,
        'frozen_before_result':True,'causal_cutoff':True,'snapshot':make_snapshot(),
        'champion_top6':[1,2,3,4,5,6],'challenger_top6':[1,2,3,4,5,7]}
    lp=tmp_path/'l3.json'; cc.write_ledger(lp,{'schema':cc.LEDGER_SCHEMA,'events':[fr]})
    with pytest.raises(ValueError,match='exactly one adjudication'):
        adj.append_interactions_for_existing(lp,12)
    # Adjudication references different freeze.
    badad={'event_type':'ADJUDICATION','target_contest':12,'freeze_sha256':'x'*64,'actual_numbers':[1,2,3,4,5,6],
           'challenger_hits':5,'champion_hits':6,'e_value_after':1.0}
    cc.write_ledger(lp,{'schema':cc.LEDGER_SCHEMA,'events':[fr,badad]})
    with pytest.raises(ValueError,match='active freeze'):
        adj.append_interactions_for_existing(lp,12)
    # Duplicate interaction events are rejected.
    ie={'event_type':'INTERACTIONS','target_contest':12,'interaction_sha256':'a'*64}
    cc.write_ledger(lp,{'schema':cc.LEDGER_SCHEMA,'events':[fr,badad,ie,dict(ie)]})
    with pytest.raises(ValueError,match='at most one interaction'):
        adj.append_interactions_for_existing(lp,12)
    # Interaction cannot exist before adjudication.
    pre={'schema':cc.LEDGER_SCHEMA,'events':[fr,ie]}; cc.write_ledger(lp,pre)
    import pandas as pd
    row={'Concurso':12}; row.update({f'Bola{i}':i for i in range(1,7)})
    result=tmp_path/'r12.xlsx'; pd.DataFrame([row]).to_excel(result,index=False)
    with pytest.raises(ValueError,match='post-result sequence event exists without adjudication'):
        adj.adjudicate(result,12,lp)




