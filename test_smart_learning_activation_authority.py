import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import smart_learning_activation_authority as aa
from smart_learning_activation_gate import evaluate
import smart_champion_challenger as cc

ROOT = Path(__file__).resolve().parent


def _decision():
    return evaluate(
        calibration_gain=1.0, validation_gain=1.0, holdout_gain=1.0, global_gain=1.0,
        preregistered=True, prospective_evidence=True, leakage_free=True,
    )


def _dataset(n=35, seed=551):
    rng=np.random.default_rng(seed)
    rows=[]
    for c in range(1,n+1):
        d=np.sort(rng.choice(np.arange(1,61),6,replace=False))
        rows.append({'Concurso':c, **{f'Bola{i+1}':int(d[i]) for i in range(6)}})
    return pd.DataFrame(rows)


def test_missing_activation_authority_is_explicit_fail_closed(tmp_path):
    cfg=aa.load_activation_authority(tmp_path/'missing.json', target_contest=4000, root=ROOT)
    assert cfg.enabled is False
    assert cfg.marginal_strength == 0.0
    assert cfg.allow_meta_alternate_selection is False
    assert cfg.decision is None
    assert cfg.authority['status']=='FAIL_CLOSED_INACTIVE'


def test_hash_bound_single_target_authority_roundtrip_and_tamper_rejection(tmp_path):
    authority=aa.build_authority(
        target_contest=4000, decision=_decision(), evidence_sha256='a'*64,
        marginal_strength=0.25, allow_meta_alternate_selection=True, root=ROOT,
    )
    p=tmp_path/'authority.json'
    aa.write_authority(p,authority)
    cfg=aa.load_activation_authority(p,target_contest=4000,root=ROOT)
    assert cfg.enabled is True
    assert cfg.marginal_strength == 0.25
    assert cfg.allow_meta_alternate_selection is True
    assert cfg.decision.predictive_weight_authorized is True
    with pytest.raises(ValueError,match='target mismatch'):
        aa.load_activation_authority(p,target_contest=4001,root=ROOT)
    obj=json.loads(p.read_text(encoding='utf-8')); obj['marginal_strength']=0.5; p.write_text(json.dumps(obj),encoding='utf-8')
    with pytest.raises(ValueError,match='self-hash'):
        aa.load_activation_authority(p,target_contest=4000,root=ROOT)


def test_pre_result_freeze_supersede_requires_explicit_authorization(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    data=tmp_path/'pre.xlsx'; _dataset().to_excel(data,index=False)
    out=tmp_path/'freeze.json'; ledger=tmp_path/'ledger.json'; state=tmp_path/'state.json'
    first=cc.freeze_champion_challenger(data,36,out,ledger,state,start=20, enforce_temporal_guard=False)
    assert first['status']=='FROZEN'
    first_hash=first['freeze_sha256']
    with pytest.raises(ValueError,match='explicit pre-result supersede authorization'):
        cc.freeze_champion_challenger(data,36,out,ledger,state,start=21, enforce_temporal_guard=False)
    second=cc.freeze_champion_challenger(data,36,out,ledger,state,start=21,allow_pre_result_supersede=True, enforce_temporal_guard=False)
    assert second['status']=='FROZEN_SUPERSEDING_PRIOR'
    assert second['freeze_sha256'] != first_hash
    events=json.loads(ledger.read_text(encoding='utf-8'))['events']
    assert [e['event_type'] for e in events] == ['FREEZE','FREEZE','SUPERSEDE']
