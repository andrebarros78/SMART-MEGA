from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import adjudicate_signal_challenger as adj
import smart_champion_challenger as cc
from smart_meta_governor import META_ETA, PRIOR_MIX, MetaGovernor, SCHEMA
from smart_multi_challengers import POLICY_IDS, build_multi_challengers
from smart_signal_agent import SmartSignalAgent


def _multi(active=False):
    names=['freq25','freq100','freq1000','freq_global','ewma10','ewma250']
    x=np.linspace(0,1,60)
    scores={'freq25':x,'freq100':np.roll(x,3),'freq1000':np.roll(x,8),'freq_global':np.roll(x,13),
            'ewma10':x[::-1],'ewma250':np.roll(x[::-1],5)}
    w={'freq25':.08,'freq100':.12,'freq1000':.30,'freq_global':.20,'ewma10':.12,'ewma250':.18}
    fam={n:'freq' if n.startswith('freq') else 'ewma' for n in names}
    metrics={n:{'regime_context':1.0} for n in names}; metrics['freq1000']['regime_context']=.35
    red={'penalties':{n:1.0 for n in names}}; red['penalties']['freq1000']=.3
    return build_multi_challengers(scores,w,metrics,fam,red,{'active':active})


def _draws(seed=808,n=75):
    rng=np.random.default_rng(seed)
    return np.array([np.sort(rng.choice(np.arange(1,61),6,replace=False)) for _ in range(n)],dtype=int)


def test_initial_tie_break_is_quality_dynamic_and_shadow_only():
    g=MetaGovernor(); s=g.select(_multi())
    assert s['schema']==SCHEMA and s['selected_policy']=='quality_dynamic'
    assert s['selection_uses_current_result'] is False
    assert s['production_authority'] is False and s['champion_remains_active'] is True
    assert abs(sum(s['policy_weights_before_result'].values())-1.0)<1e-12
    assert min(s['policy_weights_before_result'].values())>=PRIOR_MIX/len(POLICY_IDS)-1e-12


def test_online_update_can_change_next_selection_only_after_result():
    g=MetaGovernor(); before=g.select(_multi())
    assert before['selected_policy']=='quality_dynamic'
    hits={p:0 for p in POLICY_IDS}; hits['low_redundancy']=6
    g.update(hits,before['selected_policy'])
    after=g.select(_multi())
    assert after['selected_policy']=='low_redundancy'
    assert after['observations_before_result']==1


def test_selected_policy_reward_is_frozen_not_posthoc_best():
    g=MetaGovernor(); sel=g.select(_multi())
    hits={p:0 for p in POLICY_IDS}; hits['diversity_max']=6
    upd=g.update(hits,sel['selected_policy'])
    assert upd['selected_policy_before_result']=='quality_dynamic'
    assert upd['selected_hits']==0 and upd['policy_hits']['diversity_max']==6
    assert g.selection_counts['quality_dynamic']==1


def test_governor_state_deterministic_and_regularized():
    a=MetaGovernor(); b=MetaGovernor()
    seq=[{'quality_dynamic':1,'diversity_max':0,'low_redundancy':2,'regime_context':1,'conservative':0},
         {'quality_dynamic':0,'diversity_max':1,'low_redundancy':0,'regime_context':0,'conservative':2}]
    for h in seq:
        sa=a.select(_multi()); sb=b.select(_multi()); assert sa==sb
        assert a.update(h,sa['selected_policy'])==b.update(h,sb['selected_policy'])
    assert a.state()==b.state()
    assert a.state()['observations']==2 and len(a.state()['sha256'])==64


def test_meta_governor_guards():
    with pytest.raises(ValueError): MetaGovernor(eta=0)
    with pytest.raises(ValueError): MetaGovernor(prior_mix=1)
    g=MetaGovernor()
    with pytest.raises(ValueError): g.select({})
    with pytest.raises(ValueError): g.update({'quality_dynamic':1},'quality_dynamic')
    bad={p:0 for p in POLICY_IDS}; bad['quality_dynamic']=7
    with pytest.raises(ValueError): g.update(bad,'quality_dynamic')
    with pytest.raises(ValueError): g.update({p:0 for p in POLICY_IDS},'bad')


def test_agent_replay_is_causal_and_exposes_meta_governor():
    draws=_draws(); contests=np.arange(1,len(draws)+1)
    agent=SmartSignalAgent(start=35)
    pred,back=agent.predict_next(draws,contests,target_contest=76)
    assert pred.meta_governor['selected_policy'] in POLICY_IDS
    assert pred.meta_governor['selected_top6']==pred.multi_challengers['policies'][pred.meta_governor['selected_policy']]['top6']
    assert pred.meta_governor['production_authority'] is False
    assert len(back['rows'])==40
    assert back['rows'][0]['meta_governor_before_result']['observations_before_result']==0
    assert back['rows'][0]['meta_governor_update_after_result']['observations_after_result']==1
    state=agent.state_document(); assert state['schema']=='SMART_SIGNAL_STATE_9'
    assert state['meta_governor']['observations']==40


def test_replay_deterministic_selection_sequence():
    draws=_draws(seed=809,n=65); contests=np.arange(1,66)
    _,a=SmartSignalAgent(start=30).predict_next(draws,contests,target_contest=66)
    _,b=SmartSignalAgent(start=30).predict_next(draws,contests,target_contest=66)
    sa=[r['meta_governor_before_result']['selected_policy'] for r in a['rows']]
    sb=[r['meta_governor_before_result']['selected_policy'] for r in b['rows']]
    assert sa==sb


def _snapshot_with_meta(selected='quality_dynamic'):
    multi=_multi(active=True); g=MetaGovernor(); sel=g.select(multi)
    if selected!='quality_dynamic':
        h={p:0 for p in POLICY_IDS}; h[selected]=6; g.update(h,sel['selected_policy']); sel=g.select(multi)
        assert sel['selected_policy']==selected
    # minimal raw for P01/P02/P04 adjudication
    raw={}
    for pid in ['a','b','c']:
        arr=np.roll(np.linspace(0,1,60),{'a':0,'b':7,'c':13}[pid])
        raw[pid]={'values':{str(i+1):float(arr[i]) for i in range(60)}}
    return {'raw_signals':raw,'weights':{'a':.4,'b':.35,'c':.25},'quality_metrics':{n:{'quality':1.0,'confidence':1.0} for n in raw},
            'multi_challengers':multi,'meta_governor':sel}


def test_adjudication_preserves_frozen_meta_selection_even_when_other_wins(tmp_path: Path):
    snap=_snapshot_with_meta('quality_dynamic')
    # actual chosen from diversity_max minus quality_dynamic when possible; selection must still remain quality_dynamic.
    q=set(snap['multi_challengers']['policies']['quality_dynamic']['top6']); d=list(snap['multi_challengers']['policies']['diversity_max']['top6'])
    actual=[]
    for n in d:
        if n not in actual: actual.append(n)
    for n in range(1,61):
        if len(actual)>=6: break
        if n not in actual: actual.append(n)
    freeze=tmp_path/'f.json'; freeze.write_text('{}'); fh=cc.sha256(freeze)
    fr={'event_type':'FREEZE','target_contest':95,'freeze_file':str(freeze),'freeze_sha256':fh,'frozen_before_result':True,'causal_cutoff':True,
        'snapshot':snap,'champion_top6':[1,2,3,4,5,6],'challenger_top6':snap['multi_challengers']['policies']['quality_dynamic']['top6'],
        'governed_challenger_top6':snap['meta_governor']['selected_top6'],'governed_challenger_policy':snap['meta_governor']['selected_policy']}
    lp=tmp_path/'l.json'; cc.write_ledger(lp,{'schema':cc.LEDGER_SCHEMA,'events':[fr]})
    row={'Concurso':95}; row.update({f'Bola{i}':actual[i-1] for i in range(1,7)})
    result=tmp_path/'r.xlsx'; pd.DataFrame([row]).to_excel(result,index=False)
    out=adj.adjudicate(result,95,lp); assert len(out['meta_governor_sha256'])==64
    L=json.loads(lp.read_text()); ev=[x for x in L['events'] if x.get('event_type')=='META_GOVERNOR']; assert len(ev)==1
    a=ev[0]['analysis']; assert a['selected_policy_before_result']=='quality_dynamic'
    assert a['post_result_reselection_performed'] is False and a['selection_preserved_from_freeze'] is True
    assert a['production_authority'] is False and a['champion_remains_active'] is True


def test_old_freeze_without_p08_has_no_meta_event():
    assert adj._build_meta_governor_event({'snapshot':{}},[1,2,3,4,5,6],1) is None


def test_meta_adjudication_guards():
    snap=_snapshot_with_meta(); fr={'snapshot':snap,'freeze_sha256':'x'}
    bad=json.loads(json.dumps(fr)); bad['snapshot']['meta_governor']['schema']='BAD'
    with pytest.raises(ValueError): adj._build_meta_governor_event(bad,[1,2,3,4,5,6],1)
    bad=json.loads(json.dumps(fr)); bad['snapshot']['meta_governor']['selected_policy']='bad'
    with pytest.raises(ValueError): adj._build_meta_governor_event(bad,[1,2,3,4,5,6],1)
    bad=json.loads(json.dumps(fr)); bad['snapshot']['meta_governor']['selected_top6']=[1,2,3,4,5,6]
    with pytest.raises(ValueError): adj._build_meta_governor_event(bad,[1,2,3,4,5,6],1)


def test_freeze_contains_meta_governor_hash_and_snapshot(tmp_path: Path):
    draws=_draws(seed=810,n=85); rows=[]
    for i,d in enumerate(draws,start=1):
        r={'Concurso':i,'Data do Sorteio':pd.Timestamp('2021-01-01')+pd.Timedelta(days=i)}; r.update({f'Bola{j}':int(d[j-1]) for j in range(1,7)}); rows.append(r)
    data=tmp_path/'m.xlsx'; pd.DataFrame(rows).to_excel(data,index=False)
    out=tmp_path/'f.json'; ledger=tmp_path/'l.json'; state=tmp_path/'s.json'
    res=cc.freeze_champion_challenger(data,86,out,ledger,state,start=35)
    assert res['status']=='FROZEN'
    obj=json.loads(out.read_text()); assert len(obj['meta_governor_sha256'])==64
    assert obj['governed_challenger_policy'] in POLICY_IDS
    L=json.loads(ledger.read_text()); fr=L['events'][0]
    assert len(fr['hashes']['meta_governor'])==64
    assert fr['snapshot']['meta_governor']['selected_policy']==obj['governed_challenger_policy']
    assert obj['champion_remains_active'] is True


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

