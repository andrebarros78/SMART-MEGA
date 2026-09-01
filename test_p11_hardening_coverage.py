from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import smart_signal_expansion_governance as seg
from smart_signal_expansion_governance import CandidateSignalState, SignalExpansionGovernance, MIN_CALIBRATION_OOS, MIN_VALIDATION_OOS, MAX_LIMITED_CHALLENGER_WEIGHT, load_registry, sha256_json


def feed(g, cid, start, value=1.0, novelty=.9):
    c=start
    for _ in range(MIN_CALIBRATION_OOS + MIN_VALIDATION_OOS):
        c += 1
        g.observe_oos(cid,c,value,novelty)
    return c


def resign(obj):
    obj.pop('sha256',None)
    obj['sha256']=sha256_json(obj)


def test_helper_and_authorization_guard_paths():
    assert seg._float_equal('x',1.0) is False
    assert seg._float_equal(float('inf'),float('inf')) is True
    assert seg._float_equal(float('inf'),float('-inf')) is False
    g=SignalExpansionGovernance(); g.register('s','f',0); feed(g,'s',0)
    st=g.candidates['s']; h=st.authorization_proof()['sha256']; st.authorize_material_influence(h)
    st.authorized_proof_sha256='bad'
    with pytest.raises(ValueError,match='missing or invalid'):
        st.assert_material_use_allowed(0.0)


def test_rehydration_count_and_status_guards():
    base=CandidateSignalState('b','f',10); row=base.snapshot()
    bad=copy.deepcopy(base); bad.total_observations=-1
    with pytest.raises(ValueError,match='non-negative'): seg._validate_rehydrated_candidate(bad,row)
    bad=copy.deepcopy(base); bad.total_observations=1
    with pytest.raises(ValueError,match='counts are inconsistent'): seg._validate_rehydrated_candidate(bad,row)
    bad=copy.deepcopy(base); bad.calibration_observations=MIN_CALIBRATION_OOS+1; bad.total_observations=bad.calibration_observations; bad.last_contest=100
    with pytest.raises(ValueError,match='calibration partition exceeds'): seg._validate_rehydrated_candidate(bad,row)
    bad=copy.deepcopy(base); bad.validation_observations=1; bad.total_observations=1; bad.last_contest=11
    with pytest.raises(ValueError,match='validation cannot precede'): seg._validate_rehydrated_candidate(bad,row)
    bad=copy.deepcopy(base); bad.last_contest=11
    with pytest.raises(ValueError,match='last_contest invalid without'): seg._validate_rehydrated_candidate(bad,row)
    bad=copy.deepcopy(base); bad.total_observations=1; bad.calibration_observations=1
    with pytest.raises(ValueError,match='last_contest invalid'): seg._validate_rehydrated_candidate(bad,row)
    bad=copy.deepcopy(base); bad.status='EVIDENCE_ELIGIBLE'
    with pytest.raises(ValueError,match='evidence-eligible'): seg._validate_rehydrated_candidate(bad,row)
    bad=copy.deepcopy(base); bad.status='UNKNOWN'
    with pytest.raises(ValueError,match='unknown candidate'): seg._validate_rehydrated_candidate(bad,row)


def test_rehydration_evidence_and_authorized_guards():
    g=SignalExpansionGovernance(); g.register('e','f',0); feed(g,'e',0)
    st=g.candidates['e']; row=st.snapshot()
    r=copy.deepcopy(row); r.pop('mean_novelty')
    with pytest.raises(ValueError,match='missing evidence'): seg._validate_rehydrated_candidate(copy.deepcopy(st),r)
    r=copy.deepcopy(row); r['mean_novelty']=999.0
    with pytest.raises(ValueError,match='mean_novelty'): seg._validate_rehydrated_candidate(copy.deepcopy(st),r)
    r=copy.deepcopy(row); r['automatic_material_influence']=True
    with pytest.raises(ValueError,match='automatic_material_influence'): seg._validate_rehydrated_candidate(copy.deepcopy(st),r)
    r=copy.deepcopy(row); r['checks']={}
    with pytest.raises(ValueError,match='eligibility checks'): seg._validate_rehydrated_candidate(copy.deepcopy(st),r)
    bad=copy.deepcopy(st); bad.status='SHADOW_CHALLENGER'
    with pytest.raises(ValueError,match='shadow authorization'): seg._validate_rehydrated_candidate(bad,row)
    bad=copy.deepcopy(st); bad.status='LIMITED_CHALLENGER_AUTHORIZED'; bad.authorized_proof_sha256='bad'; bad.material_weight_cap=MAX_LIMITED_CHALLENGER_WEIGHT
    with pytest.raises(ValueError,match='authorized state lacks'): seg._validate_rehydrated_candidate(bad,row)
    bad=copy.deepcopy(st); bad.status='LIMITED_CHALLENGER_AUTHORIZED'; bad.authorized_proof_sha256=bad.authorization_proof()['sha256']; bad.material_weight_cap=MAX_LIMITED_CHALLENGER_WEIGHT/2
    with pytest.raises(ValueError,match='material cap mismatch'): seg._validate_rehydrated_candidate(bad,row)


def test_load_document_shape_guards(tmp_path: Path):
    p=tmp_path/'r.json'; p.write_text(json.dumps([]))
    with pytest.raises(ValueError,match='invalid signal expansion registry document'): load_registry(p,())
    obj=SignalExpansionGovernance(()).snapshot(); obj['candidates']=[]; resign(obj); p.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='candidates must be an object'): load_registry(p,())
    obj=SignalExpansionGovernance(()).snapshot(); obj['candidate_count']=1; obj['candidates']={'x': []}; resign(obj); p.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='candidate registry row must be an object'): load_registry(p,())


def test_valid_shadow_and_evidence_eligible_rehydration_paths():
    shadow=CandidateSignalState('shadow','f',10)
    seg._validate_rehydrated_candidate(shadow, shadow.snapshot())
    g=SignalExpansionGovernance(); g.register('eligible_ok','f',0); feed(g,'eligible_ok',0)
    eligible=g.candidates['eligible_ok']
    assert eligible.status == 'EVIDENCE_ELIGIBLE'
    seg._validate_rehydrated_candidate(eligible, eligible.snapshot())
