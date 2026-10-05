import math

import numpy as np
import pytest

import smart_v2_engine as engine
from smart_independent_oracle import recompute_dynamic_weights
from smart_signal_agent import SIGNAL_NAMES
from smart_signal_weights import REQUIRED_FACTORS, _normalize, dynamic_weights


def metrics():
    return {name: {factor: 1.0 for factor in REQUIRED_FACTORS} for name in SIGNAL_NAMES}


def families():
    return {name: engine.family_of(name) for name in SIGNAL_NAMES}


@pytest.mark.parametrize("factor", REQUIRED_FACTORS)
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_signal_factor_is_rejected_before_weights(factor, bad):
    values = metrics()
    values[SIGNAL_NAMES[0]][factor] = bad
    with pytest.raises(ValueError, match="finite"):
        dynamic_weights(values, families())


def test_factor_product_overflow_is_rejected_before_weights():
    values = metrics()
    values[SIGNAL_NAMES[0]]["utility"] = 1e308
    values[SIGNAL_NAMES[0]]["quality"] = 1e308
    with pytest.raises(ValueError, match="finite"):
        dynamic_weights(values, families())


def test_total_weight_overflow_is_rejected_before_weights():
    values = metrics()
    for row in values.values():
        row["utility"] = 1e308
    with pytest.raises(ValueError, match="finite"):
        dynamic_weights(values, families())


def test_boolean_factor_cannot_be_treated_as_measured_utility():
    values = metrics()
    values[SIGNAL_NAMES[0]]["utility"] = True
    with pytest.raises(ValueError, match="numeric"):
        dynamic_weights(values, families())


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0])
def test_normalization_rejects_invalid_mass_components(bad):
    with pytest.raises(ValueError, match="finite|non-negative"):
        _normalize({"freq25": bad, "ewma10": 1.0})


def test_valid_signal_weights_match_independent_oracle_and_keep_caps():
    values = metrics()
    for index, row in enumerate(values.values(), 1):
        row["utility"] = index / 7.0
        row["quality"] = 0.6
        row["confidence"] = 0.8
    actual, components = dynamic_weights(values, families())
    expected, raw = recompute_dynamic_weights(values, families())
    assert actual == pytest.approx(expected)
    assert sum(actual.values()) == pytest.approx(1.0)
    assert all(math.isfinite(value) and 0 <= value <= 0.42 for value in actual.values())
    for family in set(families().values()):
        assert sum(actual[name] for name in actual if families()[name] == family) <= 0.7 + 1e-12
    assert {name: row["raw_product"] for name, row in components.items()} == pytest.approx(raw)
