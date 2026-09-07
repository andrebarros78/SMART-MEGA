import pytest
import numpy as np

import smart_b7_champion_probability as m


def test_split_boundaries():
    assert m.split_name(2200) == "calibration"
    assert m.split_name(2201) == "validation"
    assert m.split_name(2700) == "validation"
    assert m.split_name(2701) == "holdout"


def test_actual_vector_has_six_ones():
    y = m.actual_vector([1,2,3,4,5,6])
    assert y.shape == (60,)
    assert y.sum() == 6


def test_summary_uniform_is_zero_edge():
    rows=[]
    ulog = m.binary_log_loss(np.full(60,.1), m.actual_vector([1,2,3,4,5,6]))
    for i in range(3):
        rows.append({"brier":.09,"uniform_brier":.09,"log_loss":ulog,"uniform_log_loss":ulog,"hits":0.6})
    s=m._summarize(rows)
    assert s["brier_edge_pct"] == pytest.approx(0.0)
    assert s["log_loss_edge_pct"] == pytest.approx(0.0)
