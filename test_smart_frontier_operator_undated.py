"""An operator-requested contest is valid without claiming a scheduled date."""
import json

import numpy as np
import pytest

from smart_frontier_signal_lab import FrontierState, freeze_shadow


def state():
    model=FrontierState(recent_window=4)
    model.update(np.array([1,2,3,4,5,6]),0)
    model.update(np.array([7,8,9,10,11,12]),2)
    return model


def test_missing_operator_target_date_neutralizes_only_calendar_signal():
    model=state()
    without_date=model.predict(None).document()
    with_date=model.predict(0).document()
    assert set(without_date)==set(with_date)
    assert without_date['frontier_weekday_bayes']['production_authority'] is False
    probs=without_date['frontier_weekday_bayes']['probabilities']
    assert len(probs)==60
    assert all(abs(value-0.1)<1e-12 for value in probs.values())
    for name in without_date:
        if name!='frontier_weekday_bayes':
            assert without_date[name]==with_date[name]


def test_undated_shadow_freeze_has_no_fabricated_calendar(tmp_path):
    model=state()
    data=tmp_path/'data.bin';data.write_bytes(b'history only')
    report=tmp_path/'report.json';report.write_text('{}')
    freeze_path=tmp_path/'freeze.json'
    result=freeze_shadow(model,data,3071,None,report,freeze_path,tmp_path/'registry.json')
    assert result['target_date'] is None
    assert result['calendar_conditioning']=='NEUTRALIZED_MISSING_TARGET_DATE'
    assert result['production_authority'] is False
    assert result['material_weight']==0.0
    assert result['result_used'] is False
    assert result['candidate_count']==5
    assert json.loads(freeze_path.read_text())==result


def test_invalid_supplied_date_still_rejected(tmp_path):
    model=state()
    data=tmp_path/'data.bin';data.write_bytes(b'history')
    report=tmp_path/'report.json';report.write_text('{}')
    with pytest.raises(ValueError):
        freeze_shadow(model,data,3071,'bad-date',report,tmp_path/'freeze.json',tmp_path/'registry.json')
    assert not (tmp_path/'freeze.json').exists()
