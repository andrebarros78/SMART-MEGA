from smart_learning_activation_gate import evaluate

def test_rejects_validation_regression():
    r=evaluate(calibration_gain=3,validation_gain=-1,holdout_gain=0,global_gain=2,preregistered=True,prospective_evidence=False,leakage_free=True)
    assert r.status=='REJECT_NON_REGRESSION' and not r.predictive_weight_authorized

def test_retrospective_non_regressive_stays_prospective_challenger_only():
    r=evaluate(calibration_gain=0,validation_gain=1,holdout_gain=0,global_gain=0,preregistered=True,prospective_evidence=False,leakage_free=True)
    assert r.status=='PROSPECTIVE_CHALLENGER_ONLY'
    assert r.prospective_challenger_authorized and not r.predictive_weight_authorized

def test_prospective_clean_non_regressive_can_be_bounded_promoted():
    r=evaluate(calibration_gain=1,validation_gain=1,holdout_gain=1,global_gain=1,preregistered=True,prospective_evidence=True,leakage_free=True)
    assert r.status=='ELIGIBLE_FOR_BOUNDED_PROMOTION' and r.predictive_weight_authorized

def test_leakage_always_rejected():
    r=evaluate(calibration_gain=10,validation_gain=10,holdout_gain=10,global_gain=10,preregistered=True,prospective_evidence=True,leakage_free=False)
    assert r.status=='REJECT'


def test_rejects_nonfinite_gains():
    import math
    import pytest
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match='finite'):
            evaluate(calibration_gain=bad, validation_gain=0, holdout_gain=0, global_gain=0, preregistered=True, prospective_evidence=True, leakage_free=True)


def test_no_gain_and_unregistered_shadow_paths():
    no_gain=evaluate(calibration_gain=0,validation_gain=0,holdout_gain=0,global_gain=0,preregistered=True,prospective_evidence=True,leakage_free=True)
    assert no_gain.status=='NO_PROVEN_GAIN'
    shadow=evaluate(calibration_gain=1,validation_gain=0,holdout_gain=0,global_gain=0,preregistered=False,prospective_evidence=True,leakage_free=True)
    assert shadow.status=='SHADOW_ONLY' and not shadow.predictive_weight_authorized


def test_activation_decision_serialization():
    r=evaluate(calibration_gain=1,validation_gain=1,holdout_gain=1,global_gain=1,preregistered=True,prospective_evidence=True,leakage_free=True)
    d=r.to_dict()
    assert d['status']=='ELIGIBLE_FOR_BOUNDED_PROMOTION'
    assert d['predictive_weight_authorized'] is True
    assert d['prospective_challenger_authorized'] is True
