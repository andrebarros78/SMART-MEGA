from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import smart_champion_challenger as cc
from smart_bounded_online_learning import BoundedOnlineLearningGuard, SCHEMA
from smart_signal_agent import SmartSignalAgent


def _draws(seed=10010,n=75):
    rng=np.random.default_rng(seed)
    return np.array([np.sort(rng.choice(np.arange(1,61),6,replace=False)) for _ in range(n)],dtype=int)


def test_guard_rejects_invalid_configuration_and_inputs():
    with pytest.raises(ValueError): BoundedOnlineLearningGuard(eta=0)
    with pytest.raises(ValueError): BoundedOnlineLearningGuard(eta=1,max_abs_step=0)
    with pytest.raises(ValueError): BoundedOnlineLearningGuard(eta=1,warmup_full_after=0)
    with pytest.raises(ValueError): BoundedOnlineLearningGuard(eta=1,min_warmup_scale=0)
    with pytest.raises(ValueError): BoundedOnlineLearningGuard(eta=1,max_abs_centered_logit=0)
    g=BoundedOnlineLearningGuard(eta=1)
    with pytest.raises(ValueError): g.update({}, {})
    with pytest.raises(ValueError): g.update({'a':0.0},{'b':1})
    with pytest.raises(ValueError): g.update({'a':float('nan')},{'a':1})
    with pytest.raises(ValueError): g.update({'a':0.0},{'a':7})
    with pytest.raises(ValueError): g.update({'a':0.0},{'a':1.5})


def test_single_result_shock_is_bounded_and_warmup_reduces_early_step():
    g=BoundedOnlineLearningGuard(eta=1.0,max_abs_step=1.0,warmup_full_after=5,min_warmup_scale=.5)
    out,a=g.update({'a':0.0,'b':0.0},{'a':6,'b':0})
    assert a['evidence_scale'] < 1.0
    assert max(abs(x) for x in a['applied_delta'].values()) <= 1.0
    assert 'a' in a['clipped_ids']
    assert g.clipped_update_count >= 1 and g.warmup_update_count==1
    assert abs(sum(out.values())) < 1e-12


def test_full_strength_after_warmup_and_spread_regularization():
    g=BoundedOnlineLearningGuard(eta=1,max_abs_step=1,warmup_full_after=2,min_warmup_scale=.5,max_abs_centered_logit=2)
    w={'a':0.0,'b':0.0}
    for _ in range(20): w,_=g.update(w,{'a':6,'b':0})
    assert g.evidence_scale()==1.0
    assert max(abs(x) for x in w.values()) <= 2.0+1e-12
    assert g.spread_clip_count>0
    st=g.state(); assert st['schema']==SCHEMA and st['updates']==20
    assert st['downstream_recovery_prior_mix']==0.05


def test_reversal_can_recover_previously_penalized_arm():
    g=BoundedOnlineLearningGuard(eta=.7,max_abs_step=1,max_abs_centered_logit=4)
    w={'good':0.0,'recover':0.0}
    for _ in range(30): w,_=g.update(w,{'good':2,'recover':0})
    low=w['recover']
    for _ in range(30): w,_=g.update(w,{'good':0,'recover':2})
    assert w['recover'] > low
    assert w['recover'] >= w['good']-1e-12


def test_agent_uses_guard_only_after_each_oos_result_and_state_is_auditable():
    draws=_draws(); contests=np.arange(1,len(draws)+1)
    agent=SmartSignalAgent(start=35)
    pred,back=agent.predict_next(draws,contests,target_contest=76)
    assert len(back['rows'])==40
    first=back['rows'][0]
    assert first['bounded_expert_learning_after_result']['update_index']==1
    assert first['bounded_expert_learning_after_result']['update_after_result_only'] is True
    assert first['bounded_family_learning_after_result']['update_index']==1
    assert pred.bounded_online_learning['expert']['updates']==40
    state=agent.state_document(); assert state['schema']=='SMART_SIGNAL_STATE_9'
    assert state['bounded_online_learning']['expert']['updates']==40
    assert state['bounded_online_learning']['family']['updates']==40


def test_agent_p10_replay_is_deterministic():
    draws=_draws(seed=10011,n=65); contests=np.arange(1,66)
    pa,ba=SmartSignalAgent(start=30).predict_next(draws,contests,target_contest=66)
    pb,bb=SmartSignalAgent(start=30).predict_next(draws,contests,target_contest=66)
    assert pa.top6==pb.top6 and pa.weights==pb.weights
    assert pa.bounded_online_learning==pb.bounded_online_learning
    assert [r['bounded_expert_learning_after_result'] for r in ba['rows']]==[r['bounded_expert_learning_after_result'] for r in bb['rows']]


def test_future_freeze_hashes_and_snapshots_p10(tmp_path: Path):
    draws=_draws(seed=10012,n=85); rows=[]
    for i,d in enumerate(draws,start=1):
        row={'Concurso':i,'Data do Sorteio':pd.Timestamp('2022-01-01')+pd.Timedelta(days=i)}
        row.update({f'Bola{j}':int(d[j-1]) for j in range(1,7)}); rows.append(row)
    data=tmp_path/'m.xlsx'; pd.DataFrame(rows).to_excel(data,index=False)
    out=tmp_path/'f.json'; ledger=tmp_path/'l.json'; state=tmp_path/'s.json'
    res=cc.freeze_champion_challenger(data,86,out,ledger,state,start=35)
    assert res['status']=='FROZEN'
    obj=json.loads(out.read_text(encoding='utf-8'))
    assert len(obj['bounded_online_learning_sha256'])==64
    assert obj['challenger']['bounded_online_learning']['update_after_result_only'] is True
    fr=json.loads(ledger.read_text(encoding='utf-8'))['events'][0]
    assert len(fr['hashes']['bounded_online_learning'])==64
    assert fr['snapshot']['bounded_online_learning']['expert']['updates']==50
    assert obj['champion_remains_active'] is True
