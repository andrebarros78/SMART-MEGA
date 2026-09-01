from __future__ import annotations

import math
import numpy as np
import pytest

from smart_contextual_meta_weights import contextual_meta_factors, MAX_META_STRENGTH


def base_case():
    x=np.linspace(0,1,60)
    scores={'a':x,'b':x[::-1],'c':np.roll(x,5),'d':np.roll(x,15)}
    metrics={n:{'stability':0.7,'recent_excess_vs_uniform':0.0,'quality':0.7,'drift_active':False,'regime_context':1.0} for n in scores}
    families={'a':'f1','b':'f1','c':'f2','d':'f2'}
    context={'active':False,'l1_score':0.01,'l1_threshold':0.05}
    return scores,metrics,families,context


def test_zero_strength_is_exactly_neutral_and_deterministic():
    s,m,f,c=base_case()
    factors,audit=contextual_meta_factors(s,m,f,c,None,0.0)
    assert all(v==1.0 for v in factors.values())
    factors2,audit2=contextual_meta_factors(s,m,f,c,None,0.0)
    assert factors==factors2 and audit['sha256']==audit2['sha256']
    assert audit['weight_effect_enabled'] is False


def test_factors_are_strictly_bounded_by_strength():
    s,m,f,c=base_case()
    m['a']['stability']=1.0; m['b']['stability']=0.1
    factors,audit=contextual_meta_factors(s,m,f,c,None,MAX_META_STRENGTH)
    assert min(factors.values()) >= math.exp(-MAX_META_STRENGTH)-1e-12
    assert max(factors.values()) <= math.exp(MAX_META_STRENGTH)+1e-12
    assert audit['weight_effect_enabled'] is True


def test_positive_interaction_can_raise_signal_and_negative_can_lower_it():
    s,m,f,c=base_case()
    interaction={'pairs':{
        'a|c':{'signals':['a','c'],'shrunk_interaction':1.0},
        'a|d':{'signals':['a','d'],'shrunk_interaction':1.0},
        'b|c':{'signals':['b','c'],'shrunk_interaction':-1.0},
        'b|d':{'signals':['b','d'],'shrunk_interaction':-1.0},
    }}
    factors,audit=contextual_meta_factors(s,m,f,c,interaction,0.10)
    assert factors['a'] > factors['b']
    assert audit['signals']['a']['features']['interaction'] > audit['signals']['b']['features']['interaction']


def test_active_regime_uses_precomputed_regime_alignment():
    s,m,f,c=base_case(); c={'active':True,'l1_score':0.06,'l1_threshold':0.05}
    m['a']['regime_context']=1.0; m['b']['regime_context']=0.35
    factors,audit=contextual_meta_factors(s,m,f,c,None,0.10)
    assert audit['regime_intensity']==1.0
    assert audit['signals']['a']['features']['regime_alignment'] > audit['signals']['b']['features']['regime_alignment']
    assert factors['a'] > factors['b']


def test_drift_active_is_a_penalty_not_a_reward():
    s,m,f,c=base_case(); m['a']['drift_active']=True
    factors,audit=contextual_meta_factors(s,m,f,c,None,0.10)
    assert audit['signals']['a']['features']['drift_health']==-1.0
    m['a']['drift_active']=False
    factors2,_=contextual_meta_factors(s,m,f,c,None,0.10)
    assert factors['a'] < factors2['a']


def test_family_divergence_and_signal_dispersion_are_audited():
    s,m,f,c=base_case()
    _,audit=contextual_meta_factors(s,m,f,c,None,0.08)
    assert audit['family_divergence'] >= 0.0
    assert all(audit['signals'][n]['raw']['dispersion'] >= 0 for n in s)


def test_invalid_inputs_are_rejected():
    s,m,f,c=base_case()
    with pytest.raises(ValueError,match='strength'):
        contextual_meta_factors(s,m,f,c,None,0.2)
    bad=dict(m); bad['a']=dict(m['a']); bad['a'].pop('stability')
    with pytest.raises(ValueError,match='missing meta metrics'):
        contextual_meta_factors(s,bad,f,c,None,0.08)
    badc={'active':True,'l1_score':0.1,'l1_threshold':0.0}
    with pytest.raises(ValueError,match='invalid context'):
        contextual_meta_factors(s,m,f,badc,None,0.08)
    bads=dict(s); bads['a']=np.arange(10)
    with pytest.raises(ValueError,match='expected 60'):
        contextual_meta_factors(bads,m,f,c,None,0.08)


def test_agent_default_p05_is_active_bounded_and_zero_strength_is_available():
    import smart_v2_engine as e
    from smart_signal_agent import SmartSignalAgent
    rng=np.random.default_rng(905)
    draws=np.array([np.sort(rng.choice(e.NUMBERS,6,replace=False)) for _ in range(130)],dtype=int)
    contests=np.arange(1,131)
    active,_=SmartSignalAgent(start=50).predict_next(draws,contests,target_contest=131)
    shadow,_=SmartSignalAgent(start=50,meta_strength=0.0).predict_next(draws,contests,target_contest=131)
    assert active.contextual_meta_weights['strength']==0.06
    assert active.contextual_meta_weights['weight_effect_enabled'] is True
    assert shadow.contextual_meta_weights['weight_effect_enabled'] is False
    assert all(v==1.0 for v in [row['factor'] for row in shadow.contextual_meta_weights['signals'].values()])
    assert max(abs(active.weights[n]-shadow.weights[n]) for n in active.weights)>0.0
    assert max(active.weights.values())<=0.4200000001
    fam={}
    for n,w in active.weights.items(): fam[e.family_of(n)]=fam.get(e.family_of(n),0.0)+w
    assert max(fam.values())<=0.7000000001


def test_internal_guard_and_edge_paths_are_covered():
    import smart_contextual_meta_weights as cm
    assert cm._normalize_feature({})=={}
    with pytest.raises(ValueError,match='non-finite'):
        cm._normalize_feature({'a':float('nan')})
    with pytest.raises(ValueError,match='scores cannot be empty'):
        cm.contextual_meta_factors({}, {}, {}, {'active':False,'l1_score':0.0,'l1_threshold':1.0}, None, 0.06)
    s,m,f,c=base_case()
    badf=dict(f); badf.pop('a')
    with pytest.raises(ValueError,match='identical ids'):
        cm.contextual_meta_factors(s,m,badf,c,None,0.06)
    one_scores={'a':s['a'],'b':s['b']}; one_metrics={'a':m['a'],'b':m['b']}; one_fams={'a':'only','b':'only'}
    _,audit=cm.contextual_meta_factors(one_scores,one_metrics,one_fams,c,None,0.06)
    assert audit['family_divergence']==0.0
    with pytest.raises(ValueError,match='pairs must be a dict'):
        cm.contextual_meta_factors(s,m,f,c,{'pairs':[]},0.06)
    weird={'pairs':{
        'badshape':{'signals':['a'],'shrunk_interaction':1.0},
        'unknown':{'signals':['x','y'],'shrunk_interaction':1.0},
        'valid':{'signals':['a','b'],'shrunk_interaction':0.2},
    }}
    factors,audit=cm.contextual_meta_factors(s,m,f,c,weird,0.06)
    assert set(factors)==set(s) and audit['signals']['a']['raw']['interaction']!=0.0
    with pytest.raises(ValueError,match='interaction feature must be finite'):
        cm.contextual_meta_factors(s,m,f,c,{'pairs':{'x':{'signals':['a','b'],'shrunk_interaction':float('inf')}}},0.06)
    badm=dict(m); badm.pop('a')
    with pytest.raises(ValueError,match='identical ids'):
        cm.contextual_meta_factors(s,badm,f,c,None,0.06)


def test_family_helper_rejects_mismatched_ids_directly():
    import smart_contextual_meta_weights as cm
    x=np.linspace(0,1,60)
    with pytest.raises(ValueError,match='family ids'):
        cm._family_features({'a':x,'b':x[::-1]},{'a':'f1'})
