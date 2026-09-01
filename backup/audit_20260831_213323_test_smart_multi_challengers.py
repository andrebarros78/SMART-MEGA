from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import adjudicate_signal_challenger as adj
import smart_champion_challenger as cc
from smart_multi_challengers import POLICY_IDS, SCHEMA, build_multi_challengers
from smart_signal_agent import SmartSignalAgent


def _inputs():
    names=['freq25','freq100','freq1000','freq_global','ewma10','ewma250']
    x=np.linspace(0.0,1.0,60)
    scores={
        'freq25':x.copy(),
        'freq100':np.roll(x,3),
        'freq1000':np.roll(x,8),
        'freq_global':np.roll(x,13),
        'ewma10':x[::-1].copy(),
        'ewma250':np.roll(x[::-1],5),
    }
    weights={'freq25':.08,'freq100':.12,'freq1000':.30,'freq_global':.20,'ewma10':.12,'ewma250':.18}
    families={n:('freq' if n.startswith('freq') else 'ewma') for n in names}
    metrics={n:{'regime_context':1.0} for n in names}
    metrics['freq1000']['regime_context']=0.40
    metrics['freq_global']['regime_context']=0.35
    metrics['ewma250']['regime_context']=0.50
    penalties={n:1.0 for n in names}
    penalties['freq100']=0.25; penalties['freq1000']=0.30
    redundancy={'penalties':penalties}
    return scores,weights,metrics,families,redundancy


def test_five_specialized_policies_are_complete_hashed_shadow_only():
    scores,w,m,f,r=_inputs()
    out=build_multi_challengers(scores,w,m,f,r,{'active':True})
    assert out['schema']==SCHEMA
    assert out['policy_ids']==list(POLICY_IDS)
    assert set(out['policies'])==set(POLICY_IDS)
    assert out['policy_count']==5 and out['shadow_only'] is True
    assert out['selection_deferred_to_p08'] is True
    assert out['distinct_weight_pairs']>=4
    assert len(out['sha256'])==64
    for row in out['policies'].values():
        assert len(row['top6'])==6 and len(row['ranking60'])==60
        assert abs(sum(row['weights'].values())-1.0)<1e-12
        assert row['max_weight']<=0.4200000001
        assert max(row['family_totals'].values())<=0.7000000001
        assert row['selection_authority'] is False
        assert len(row['sha256'])==64


def test_quality_dynamic_reproduces_primary_weights_and_is_deterministic():
    scores,w,m,f,r=_inputs()
    a=build_multi_challengers(scores,w,m,f,r,{'active':False})
    b=build_multi_challengers(scores,w,m,f,r,{'active':False})
    q=a['policies']['quality_dynamic']
    assert all(abs(q['weights'][n]-w[n])<1e-12 for n in w)
    assert a==b


def test_diversity_max_balances_families_and_signals_within_family():
    scores,w,m,f,r=_inputs(); out=build_multi_challengers(scores,w,m,f,r,{'active':False})
    d=out['policies']['diversity_max']
    assert abs(d['family_totals']['freq']-.5)<1e-12
    assert abs(d['family_totals']['ewma']-.5)<1e-12
    freq=[d['weights'][n] for n in d['weights'] if f[n]=='freq']
    ewma=[d['weights'][n] for n in d['weights'] if f[n]=='ewma']
    assert max(freq)-min(freq)<1e-12 and max(ewma)-min(ewma)<1e-12


def test_low_redundancy_suppresses_redundant_signals():
    scores,w,m,f,r=_inputs(); out=build_multi_challengers(scores,w,m,f,r,{'active':False})
    q=out['policies']['quality_dynamic']['weights']; low=out['policies']['low_redundancy']['weights']
    assert low['freq100']<q['freq100']
    assert low['freq1000']<q['freq1000']


def test_regime_policy_acts_only_when_context_active():
    scores,w,m,f,r=_inputs()
    quiet=build_multi_challengers(scores,w,m,f,r,{'active':False})['policies']
    active=build_multi_challengers(scores,w,m,f,r,{'active':True})['policies']
    assert quiet['regime_context']['weights']==quiet['quality_dynamic']['weights']
    assert active['regime_context']['weights']['freq1000'] < active['quality_dynamic']['weights']['freq1000']


def test_conservative_policy_has_tighter_caps_and_shrinks_concentration():
    scores,w,m,f,r=_inputs(); out=build_multi_challengers(scores,w,m,f,r,{'active':False})['policies']
    c=out['conservative']; q=out['quality_dynamic']
    assert c['max_weight']<=0.2500000001
    assert max(c['family_totals'].values())<=0.6000000001
    assert c['max_weight'] < q['max_weight']


def test_input_guards():
    scores,w,m,f,r=_inputs()
    with pytest.raises(ValueError): build_multi_challengers({},w,m,f,r,{'active':False})
    bad=dict(scores); bad['freq25']=np.zeros(59)
    with pytest.raises(ValueError): build_multi_challengers(bad,w,m,f,r,{'active':False})
    badw=dict(w); badw.pop('freq25')
    with pytest.raises(ValueError): build_multi_challengers(scores,badw,m,f,r,{'active':False})
    badm={k:dict(v) for k,v in m.items()}; badm['freq25'].pop('regime_context')
    with pytest.raises(ValueError): build_multi_challengers(scores,w,badm,f,r,{'active':False})
    badr={'penalties':dict(r['penalties'])}; badr['penalties'].pop('freq25')
    with pytest.raises(ValueError): build_multi_challengers(scores,w,m,f,badr,{'active':False})
    with pytest.raises(ValueError): build_multi_challengers(scores,w,m,f,r,{})


def _draws(seed=701,n=85):
    rng=np.random.default_rng(seed)
    return np.array([np.sort(rng.choice(np.arange(1,61),6,replace=False)) for _ in range(n)],dtype=int)


def test_agent_exposes_five_policies_without_replacing_primary_challenger():
    draws=_draws(); contests=np.arange(1,len(draws)+1)
    pred,back=SmartSignalAgent(start=40).predict_next(draws,contests,target_contest=86)
    assert pred.multi_challengers['policy_ids']==list(POLICY_IDS)
    assert pred.multi_challengers['policies']['quality_dynamic']['top6']==pred.top6
    assert set(back['rows'][-1]['multi_challenger_hits_after_result'])==set(POLICY_IDS)
    state=SmartSignalAgent(start=40)
    state.predict_next(draws,contests,target_contest=86)
    assert state.state_document()['schema']=='SMART_SIGNAL_STATE_9'


def test_future_adjudication_appends_multi_event_only_when_frozen(tmp_path: Path):
    scores,w,m,f,r=_inputs(); multi=build_multi_challengers(scores,w,m,f,r,{'active':True})
    freeze=tmp_path/'f.json'; freeze.write_text('{}'); fh=cc.sha256(freeze)
    # Attribution/marginal/interactions require raw signals/weights/quality.
    raw={n:{'values':{str(i+1):float(np.asarray(scores[n])[i]) for i in range(60)}} for n in scores}
    snapshot={'raw_signals':raw,'weights':w,'quality_metrics':{n:{'quality':1.0,'confidence':1.0} for n in scores},
              'multi_challengers':multi}
    fr={'event_type':'FREEZE','target_contest':91,'freeze_file':str(freeze),'freeze_sha256':fh,'frozen_before_result':True,
        'causal_cutoff':True,'snapshot':snapshot,'champion_top6':[1,2,3,4,5,6],
        'challenger_top6':multi['policies']['quality_dynamic']['top6']}
    ledger=tmp_path/'l.json'; cc.write_ledger(ledger,{'schema':cc.LEDGER_SCHEMA,'events':[fr]})
    row={'Concurso':91}; row.update({f'Bola{i}':i for i in range(1,7)})
    result=tmp_path/'r.xlsx'; pd.DataFrame([row]).to_excel(result,index=False)
    out=adj.adjudicate(result,91,ledger)
    assert len(out['multi_challenger_sha256'])==64
    L=json.loads(ledger.read_text())
    ev=[x for x in L['events'] if x.get('event_type')=='MULTI_CHALLENGERS']
    assert len(ev)==1 and ev[0]['analysis']['selection_performed'] is False
    assert set(ev[0]['analysis']['policy_hits'])==set(POLICY_IDS)


def test_old_freeze_without_p07_does_not_get_backfill_event():
    fr={'snapshot':{}}
    assert adj._build_multi_challenger_event(fr,[1,2,3,4,5,6],1) is None


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


def test_compact_replay_mode_preserves_decisions_without_full_audit_payload():
    scores,w,m,f,r=_inputs()
    full=build_multi_challengers(scores,w,m,f,r,{'active':True},audit_detail=True)
    compact=build_multi_challengers(scores,w,m,f,r,{'active':True},audit_detail=False)
    for pid in POLICY_IDS:
        assert compact['policies'][pid]['top6']==full['policies'][pid]['top6']
        assert compact['policies'][pid]['weights']==full['policies'][pid]['weights']
        assert compact['policies'][pid]['ranking60']==[]
        assert compact['policies'][pid]['aggregate_scores']=={}
        assert compact['policies'][pid]['audit_detail'] is False
        assert full['policies'][pid]['audit_detail'] is True


def test_freeze_persists_all_five_multi_challengers_and_component_hash(tmp_path: Path):
    draws=_draws(seed=703,n=120)
    rows=[]
    for i,d in enumerate(draws,start=1):
        row={'Concurso':i,'Data do Sorteio':pd.Timestamp('2020-01-01')+pd.Timedelta(days=i)}
        row.update({f'Bola{j}':int(d[j-1]) for j in range(1,7)})
        rows.append(row)
    data=tmp_path/'mega.xlsx'; pd.DataFrame(rows).to_excel(data,index=False)
    out=tmp_path/'freeze.json'; ledger=tmp_path/'ledger.json'; state=tmp_path/'state.json'
    r=cc.freeze_champion_challenger(data,121,out,ledger,state,start=40)
    assert r['status']=='FROZEN'
    obj=json.loads(out.read_text(encoding='utf-8'))
    frozen=obj['challenger']['multi_challengers']
    assert frozen['policy_ids']==list(POLICY_IDS)
    assert frozen['policy_count']==5 and frozen['shadow_only'] is True
    assert all(row['selection_authority'] is False for row in frozen['policies'].values())
    assert len(obj['multi_challengers_sha256'])==64
    led=json.loads(ledger.read_text(encoding='utf-8'))
    ev=led['events'][0]
    assert ev['snapshot']['multi_challengers']['policy_ids']==list(POLICY_IDS)
    assert len(ev['hashes']['multi_challengers'])==64

