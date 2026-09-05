import numpy as np

from smart_signal_agent import SmartSignalAgent, _apply_governor_decision
from smart_learning_activation_gate import evaluate as activation_evaluate


def _draws(seed=20260905, n=90):
    rng=np.random.default_rng(seed)
    return np.asarray([np.sort(rng.choice(np.arange(1,61), size=6, replace=False)) for _ in range(n)], dtype=int)


def test_marginal_utility_has_real_gated_path_to_weights():
    draws=_draws(); contests=np.arange(1,len(draws)+1)
    base=SmartSignalAgent(start=35, marginal_strength=0.0)
    active=SmartSignalAgent(start=35, marginal_strength=0.75, shadow_research_override=True)
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

def test_raw_decision_activation_is_rejected_without_gate_or_shadow_override():
    import pytest
    with pytest.raises(ValueError, match='activation-gate authorization'):
        SmartSignalAgent(marginal_strength=0.25)
    with pytest.raises(ValueError, match='activation-gate authorization'):
        SmartSignalAgent(allow_meta_alternate_selection=True)


def test_prospective_gate_decision_can_authorize_bounded_production_activation():
    decision=activation_evaluate(
        calibration_gain=1.0, validation_gain=1.0, holdout_gain=1.0, global_gain=1.0,
        preregistered=True, prospective_evidence=True, leakage_free=True,
    )
    a=SmartSignalAgent(marginal_strength=0.25, allow_meta_alternate_selection=True, activation_decision=decision)
    assert a.production_activation_authorized is True
    assert a.activation_mode=='PRODUCTION_GATE_AUTHORIZED'
    assert a.meta_governor.allow_alternate_selection is True


def test_retrospective_gate_decision_cannot_authorize_decision_change():
    import pytest
    decision=activation_evaluate(
        calibration_gain=1.0, validation_gain=1.0, holdout_gain=0.0, global_gain=0.0,
        preregistered=True, prospective_evidence=False, leakage_free=True,
    )
    with pytest.raises(ValueError, match='activation-gate authorization'):
        SmartSignalAgent(marginal_strength=0.25, activation_decision=decision)
