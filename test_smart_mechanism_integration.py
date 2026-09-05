import numpy as np

from smart_signal_agent import SmartSignalAgent, _apply_governor_decision


def _draws(seed=20260905, n=90):
    rng=np.random.default_rng(seed)
    return np.asarray([np.sort(rng.choice(np.arange(1,61), size=6, replace=False)) for _ in range(n)], dtype=int)


def test_marginal_utility_has_real_gated_path_to_weights():
    draws=_draws(); contests=np.arange(1,len(draws)+1)
    base=SmartSignalAgent(start=35, marginal_strength=0.0)
    active=SmartSignalAgent(start=35, marginal_strength=0.75)
    p0,_=base.predict_next(draws,contests,target_contest=91)
    p1,_=active.predict_next(draws,contests,target_contest=91)
    assert all(not p0.quality_metrics[n]['marginal_utility_weight_effect_enabled'] for n in p0.weights)
    assert all(p1.quality_metrics[n]['marginal_utility_weight_effect_enabled'] for n in p1.weights)
    assert any(abs(p1.weights[n]-p0.weights[n]) > 1e-12 for n in p0.weights)
    assert any(abs(p1.quality_metrics[n]['marginal_utility_factor']-1.0) > 1e-12 for n in p1.weights)


def test_meta_governor_has_real_gated_path_to_final_top6():
    base=[1,2,3,4,5,6]
    closed={'alternate_authorized':False,'selected_policy':'diversity_max','selected_top6':[7,8,9,10,11,12]}
    opened={'alternate_authorized':True,'selected_policy':'diversity_max','selected_top6':[7,8,9,10,11,12]}
    assert _apply_governor_decision(base, closed)==(base,'quality_dynamic_anchor')
    top6,source=_apply_governor_decision(base, opened)
    assert top6==[7,8,9,10,11,12]
    assert source=='meta_governor:diversity_max'


def test_default_integration_remains_fail_closed():
    a=SmartSignalAgent()
    assert a.marginal_strength==0.0
    assert a.meta_governor.allow_alternate_selection is False
