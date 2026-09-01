from __future__ import annotations
from smart_test_helpers import make_valid_freeze_fixture, bind_valid_freeze_fixture



import json

from pathlib import Path



import numpy as np

import pandas as pd

import pytest



import adjudicate_signal_challenger as adj

import smart_champion_challenger as cc

import smart_v2_engine as e

from smart_signal_agent import SIGNAL_NAMES, SmartSignalAgent

from smart_signal_marginal_utility import (

    MarginalUtilityState,

    analyze_marginal_utility_snapshot,

    evaluate_incremental_utility,

    update_marginal_states,

)





def _binary_score(nums):

    a=np.zeros(60,float)

    for n in nums: a[int(n)-1]=1.0

    return a





def _draws(seed=700,n=80):

    rng=np.random.default_rng(seed)

    return np.array([np.sort(rng.choice(e.NUMBERS,6,replace=False)) for _ in range(n)],dtype=int)





def _snapshot(scores, weights):

    raw={}

    for name,arr in scores.items():

        raw[name]={'values':{str(i+1):float(arr[i]) for i in range(60)}}

    return {'raw_signals':raw,'weights':weights,

            'quality_metrics':{name:{'quality':1.0} for name in scores}}





def test_incremental_utility_detects_positive_and_negative_signal_effect():

    actual=[1,2,3,4,5,6]

    good=_binary_score(actual); bad=_binary_score([7,8,9,10,11,12])

    pos=evaluate_incremental_utility({'good':good,'bad':bad},{'good':0.6,'bad':0.4},actual)

    assert pos['full_ensemble']['hits']==6

    assert pos['per_signal']['good']['delta_hits']==6

    assert pos['per_signal']['bad']['delta_hits']==0

    neg=evaluate_incremental_utility({'good':good,'bad':bad},{'good':0.4,'bad':0.6},actual)

    assert neg['full_ensemble']['hits']==0

    assert neg['per_signal']['bad']['delta_hits']==-6

    assert neg['per_signal']['bad']['harmed_actual_out_of_top6']==actual

    assert len(pos['marginal_utility_sha256'])==64





def test_state_accumulates_mean_ewma_confidence_and_signs():

    s=MarginalUtilityState('x')

    assert s.metrics()['confidence']==0.0

    s.update(1,0.2); s.update(0,0.0); s.update(-1,-0.1)

    m=s.metrics()

    assert m['observations']==3 and m['cumulative_delta_hits']==0.0

    assert m['positive_updates']==1 and m['zero_updates']==1 and m['negative_updates']==1

    assert 0 < m['confidence'] < 1

    assert m['weight_effect_enabled'] is False

    with pytest.raises(ValueError,match='finite'): s.update(float('nan'),0)





def test_validation_single_signal_and_state_id_guards():

    actual=[1,2,3,4,5,6]; a=_binary_score(actual)

    one=evaluate_incremental_utility({'only':a},{'only':1.0},actual)

    assert one['per_signal']['only']['available'] is False

    with pytest.raises(ValueError,match='six unique'): evaluate_incremental_utility({'a':a,'b':a},{'a':.5,'b':.5},[1,1,2,3,4,5])

    with pytest.raises(ValueError,match='identical'): evaluate_incremental_utility({'a':a},{'b':1.0},actual)

    with pytest.raises(ValueError,match='60 finite'): evaluate_incremental_utility({'a':np.zeros(59)},{'a':1.0},actual)

    with pytest.raises(ValueError,match='invalid weight'): evaluate_incremental_utility({'a':a},{'a':-1.0},actual)

    with pytest.raises(ValueError,match='positive total'): evaluate_incremental_utility({'a':a},{'a':0.0},actual)

    with pytest.raises(ValueError,match='states must match'):

        update_marginal_states({'x':MarginalUtilityState('x')},{'a':a,'b':a},{'a':.5,'b':.5},actual)





def test_snapshot_validation_and_hash_determinism():

    actual=[1,2,3,4,5,6]; a=_binary_score(actual); b=_binary_score([7,8,9,10,11,12])

    snap=_snapshot({'a':a,'b':b},{'a':.5,'b':.5})

    x=analyze_marginal_utility_snapshot(snap,actual)

    y=analyze_marginal_utility_snapshot(snap,actual)

    assert x['marginal_utility_sha256']==y['marginal_utility_sha256']

    with pytest.raises(ValueError,match='snapshot requires'): analyze_marginal_utility_snapshot({},actual)

    broken=_snapshot({'a':a,'b':b},{'a':.5,'b':.5}); broken['raw_signals']['a']['values'].pop('60')

    with pytest.raises(ValueError,match='exactly 60'): analyze_marginal_utility_snapshot(broken,actual)





def test_agent_learns_marginal_utility_strictly_after_each_oos_result():

    draws=_draws(n=70); contests=np.arange(1,71)

    agent=SmartSignalAgent(start=30)

    pred,back=agent.predict_next(draws,contests,target_contest=71)

    assert len(back['rows'])==40

    for name in SIGNAL_NAMES:

        mu=pred.quality_metrics[name]['marginal_utility']

        assert mu['observations']==40

        assert pred.quality_metrics[name]['marginal_utility_weight_effect_enabled'] is False

        assert back['rows'][0]['marginal_delta_hits_after_result'][name] is not None

    state=agent.state_document()

    assert state['schema']=='SMART_SIGNAL_STATE_9'

    assert set(state['marginal_utility'])==set(SIGNAL_NAMES)





def test_marginal_utility_event_is_append_only_and_future_adjudication_generates_it(tmp_path:Path):

    a=_binary_score([1,2,3,4,5,6]); b=_binary_score([7,8,9,10,11,12])

    snap=_snapshot({'a':a,'b':b},{'a':.6,'b':.4})

    freeze=tmp_path/'freeze.json'; freeze.write_text(json.dumps({'x':1}),encoding='utf-8')

    fh=cc.sha256(freeze)

    fr={'event_type':'FREEZE','target_contest':10,'freeze_file':str(freeze),'freeze_sha256':fh,

        'frozen_before_result':True,'causal_cutoff':True,'champion_top6':[1,2,3,4,5,6],

        'challenger_top6':[1,2,3,4,5,6],'snapshot':snap}
    fr=bind_valid_freeze_fixture(cc, freeze, fr)

    ledger={'schema':cc.LEDGER_SCHEMA,'events':[fr]}; lp=tmp_path/'ledger.json'; cc.write_ledger(lp,ledger)

    row={'Concurso':10}; row.update({f'Bola{i}':i for i in range(1,7)})

    result=tmp_path/'result.xlsx'; pd.DataFrame([row]).to_excel(result,index=False)

    out=adj.adjudicate(result,10,lp)

    assert len(out['marginal_utility_sha256'])==64

    led=json.loads(lp.read_text(encoding='utf-8'))

    types=[x['event_type'] for x in led['events']]

    assert types==['FREEZE','ADJUDICATION','ATTRIBUTION','MARGINAL_UTILITY','INTERACTIONS']

    preserved=adj.append_marginal_utility_for_existing(lp,10)

    assert preserved['status']=='ALREADY_MARGINAL_UTILITY_EVENT_PRESERVED'

    marg=[x for x in led['events'] if x.get('event_type')=='MARGINAL_UTILITY'][0]; led['events'].append(dict(marg)); cc.write_ledger(lp,led)

    with pytest.raises(ValueError,match='at most one marginal'):

        adj.append_marginal_utility_for_existing(lp,10)





def test_existing_adjudication_backfill_requires_valid_pair(tmp_path:Path):

    lp=tmp_path/'ledger.json'; cc.write_ledger(lp,{'schema':cc.LEDGER_SCHEMA,'events':[]})

    with pytest.raises(ValueError,match='exactly one adjudication'):

        adj.append_marginal_utility_for_existing(lp,10)





def test_private_guards_cover_required_empty_removed_and_zero_mass_paths():

    import smart_signal_marginal_utility as mu

    actual=[1,2,3,4,5,6]; a=_binary_score(actual); b=_binary_score([7,8,9,10,11,12])

    with pytest.raises(ValueError,match='scores and weights are required'):

        mu.evaluate_incremental_utility({}, {}, actual)

    with pytest.raises(ValueError,match='at least one remaining'):

        mu._aggregate({'a':a},{'a':1.0},removed='a')

    with pytest.raises(ValueError,match='zero weight mass'):

        mu._aggregate({'a':a,'b':b},{'a':1.0,'b':0.0},removed='a')

    state=MarginalUtilityState('only')

    analysis=update_marginal_states({'only':state},{'only':a},{'only':1.0},actual)

    assert analysis['per_signal']['only']['available'] is False

    assert state.observations==0





def test_existing_adjudication_success_backfill_and_pair_guards(tmp_path:Path):

    a=_binary_score([1,2,3,4,5,6]); b=_binary_score([7,8,9,10,11,12])

    snap=_snapshot({'a':a,'b':b},{'a':.6,'b':.4})

    freeze=tmp_path/'f.json'; freeze.write_text('{}',encoding='utf-8'); fh=cc.sha256(freeze)

    fr={'event_type':'FREEZE','target_contest':20,'freeze_file':str(freeze),'freeze_sha256':fh,

        'frozen_before_result':True,'causal_cutoff':True,'champion_top6':[1,2,3,4,5,6],

        'challenger_top6':[1,2,3,4,5,6],'snapshot':snap}

    ad={'event_type':'ADJUDICATION','target_contest':20,'freeze_sha256':fh,'actual_numbers':[1,2,3,4,5,6],

        'challenger_hits':6,'champion_hits':6,'e_value_after':1.0}

    lp=tmp_path/'ledger.json'; cc.write_ledger(lp,{'schema':cc.LEDGER_SCHEMA,'events':[fr,ad]})

    out=adj.append_marginal_utility_for_existing(lp,20)

    assert out['status']=='MARGINAL_UTILITY_APPENDED'

    led=json.loads(lp.read_text(encoding='utf-8'))

    assert [x['event_type'] for x in led['events']][-1]=='MARGINAL_UTILITY'

    # Wrong freeze hash pairing is rejected.

    bad=tmp_path/'bad.json'; bad_ad=dict(ad); bad_ad['freeze_sha256']='x'*64

    cc.write_ledger(bad,{'schema':cc.LEDGER_SCHEMA,'events':[fr,bad_ad]})

    with pytest.raises(ValueError,match='adjudication must reference active freeze hash'):

        adj.append_marginal_utility_for_existing(bad,20)

    # Duplicate attribution guard is explicit.

    dup=tmp_path/'dup.json'; at={'event_type':'ATTRIBUTION','target_contest':20,'freeze_sha256':fh,'attribution_sha256':'a'*64}

    cc.write_ledger(dup,{'schema':cc.LEDGER_SCHEMA,'events':[fr,ad,at,dict(at)]})

    with pytest.raises(ValueError,match='at most one attribution'):

        adj.append_marginal_utility_for_existing(dup,20)





def test_adjudication_rejects_marginal_utility_predating_result(tmp_path:Path):

    a=_binary_score([1,2,3,4,5,6]); b=_binary_score([7,8,9,10,11,12]); snap=_snapshot({'a':a,'b':b},{'a':.6,'b':.4})

    freeze=tmp_path/'f.json'; freeze.write_text('{}',encoding='utf-8'); fh=cc.sha256(freeze)

    fr={'event_type':'FREEZE','target_contest':30,'freeze_file':str(freeze),'freeze_sha256':fh,

        'frozen_before_result':True,'causal_cutoff':True,'champion_top6':[1,2,3,4,5,6],

        'challenger_top6':[1,2,3,4,5,6],'snapshot':snap}

    mu={'event_type':'MARGINAL_UTILITY','target_contest':30,'freeze_sha256':fh,'marginal_utility_sha256':'a'*64}

    lp=tmp_path/'ledger.json'; cc.write_ledger(lp,{'schema':cc.LEDGER_SCHEMA,'events':[fr,mu]})

    row={'Concurso':30}; row.update({f'Bola{i}':i for i in range(1,7)}); result=tmp_path/'r.xlsx'; pd.DataFrame([row]).to_excel(result,index=False)

    with pytest.raises(ValueError,match='post-result sequence event exists without adjudication'):

        adj.adjudicate(result,30,lp)






