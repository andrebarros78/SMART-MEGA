import json
from pathlib import Path

import pytest

import smart_b7_operator as op
import smart_b7_prospective_freeze as freeze
from smart_b7_predictive_edge import sha256_json

ROOT=Path(__file__).resolve().parent


def test_operator_version_and_status_without_final_freeze(monkeypatch, tmp_path):
    (tmp_path/'VERSION').write_text('7.0.0\n',encoding='utf-8')
    assert op.version(tmp_path)=='7.0.0'
    s=op.status(tmp_path)
    assert s['version']=='7.0.0'
    assert s['mode']=='PARALLEL_PROSPECTIVE_EVIDENCE_COLLECTION'
    assert s['predictive_advantage_claimed'] is False


def test_freeze_schedule_guard_rejects_date_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(freeze, 'resolve_target_schedule', lambda root,target:{'schema':'SMART_TARGET_SCHEDULE_AUTHORITY_3','target_contest':target,'target_date':'08/09/2026','scheduled_datetime':'2026-09-08T21:00:00-03:00'})
    monkeypatch.setattr(freeze, 'assert_pre_draw_window', lambda schedule:{'status':'PASS'})
    data=tmp_path/'data.xlsx'; data.write_bytes(b'not-used-because-load-is-monkeypatched')
    report={'selected_strength':0.0,'shadow_challenger_strength':1.0,'selection_partition':'validation','evaluation_partition':'holdout','future_leakage':False,'canonical_probability_mode':'UNIFORM_BASELINE_NO_REGRESSION','validation_gate':{},'shadow_challenger_holdout':{}}
    report['sha256']=sha256_json(report)
    rp=tmp_path/'report.json'; rp.write_text(json.dumps(report),encoding='utf-8')
    monkeypatch.setattr(freeze.e,'load_draws',lambda p: (__import__('numpy').array([[1,2,3,4,5,6]]),__import__('numpy').array([3054])))
    with pytest.raises(ValueError, match='official schedule'):
        freeze.build(data,rp,3055,'09/09/2026')


def test_verify_freeze_rejects_tamper(tmp_path):
    (tmp_path/'VERSION').write_text('7.0.0\n',encoding='utf-8')
    doc={'target_contest':3055,'cutoff_contest':3054,'result_used':False,'frozen_before_result':True}
    doc['sha256']=sha256_json(doc)
    p=tmp_path/'B7_X_PROSPECTIVE_FREEZE_FINAL.json'; p.write_text(json.dumps(doc),encoding='utf-8')
    with pytest.raises(ValueError):
        op.verify_freeze(tmp_path,p)
