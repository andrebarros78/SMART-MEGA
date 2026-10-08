from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import smart_champion_challenger as cc
from smart_signal_agent import SIGNAL_NAMES
from smart_signal_expansion_governance import (
    MAX_LIMITED_CHALLENGER_WEIGHT, MIN_CALIBRATION_OOS, MIN_VALIDATION_OOS,
    CandidateSignalState, SignalExpansionGovernance, load_registry, write_registry,
    sha256_json,
)


def _feed(gov, cid, start, calibration_value=1.0, validation_value=1.0, novelty=0.8):
    contest=start
    for _ in range(MIN_CALIBRATION_OOS):
        contest += 1; gov.observe_oos(cid, contest, calibration_value, novelty)
    for _ in range(MIN_VALIDATION_OOS):
        contest += 1; gov.observe_oos(cid, contest, validation_value, novelty)
    return contest


def _resign(obj):
    out=copy.deepcopy(obj); out.pop('sha256',None); obj['sha256']=sha256_json(out)


def test_new_candidate_starts_shadow_and_cannot_influence_materially():
    g=SignalExpansionGovernance(tuple(SIGNAL_NAMES)); s=g.register('new_signal','freq',3051)
    assert s.status=='SHADOW_CHALLENGER' and s.material_weight_cap==0.0
    assert s.evaluation()['automatic_material_influence'] is False
    assert s.evaluation()['champion_influence_prohibited'] is True
    with pytest.raises(ValueError): s.assert_material_use_allowed(0.001)


def test_canonical_collision_duplicate_unknown_and_causality_guards():
    g=SignalExpansionGovernance(tuple(SIGNAL_NAMES))
    with pytest.raises(ValueError): g.register(SIGNAL_NAMES[0],'freq',1)
    g.register('x','freq',10)
    with pytest.raises(ValueError): g.register('x','freq',10)
    with pytest.raises(ValueError): g.observe_oos('missing',11,1,1)
    with pytest.raises(ValueError): g.observe_oos('x',10,1,1)
    g.observe_oos('x',11,0,1)
    with pytest.raises(ValueError): g.observe_oos('x',11,0,1)
    with pytest.raises(ValueError): g.observe_oos('x',12,7,1)
    with pytest.raises(ValueError): g.observe_oos('x',12,0,2)


def test_positive_candidate_requires_separate_validation_then_evidence_bound_authorization():
    g=SignalExpansionGovernance(tuple(SIGNAL_NAMES)); g.register('good','freq',100)
    _feed(g,'good',100,1.0,1.0,0.9)
    state=g.candidates['good']; ev=state.evaluation()
    assert ev['eligible_for_material_challenger_influence'] is True
    assert state.status=='EVIDENCE_ELIGIBLE' and state.material_weight_cap==0.0
    proof=state.authorization_proof()
    with pytest.raises(ValueError): g.authorize('good','a'*64)
    bad=copy.deepcopy(proof); bad['candidate_evidence']['last_contest'] += 1; _resign(bad)
    with pytest.raises(ValueError): g.authorize('good',bad)
    auth=g.authorize('good',proof)
    assert auth['scope']=='CHALLENGER_ONLY' and auth['champion_influence'] is False
    assert auth['material_weight_cap']==MAX_LIMITED_CHALLENGER_WEIGHT
    state.assert_material_use_allowed(MAX_LIMITED_CHALLENGER_WEIGHT)
    with pytest.raises(ValueError): state.assert_material_use_allowed(MAX_LIMITED_CHALLENGER_WEIGHT+0.001)


def test_overfit_candidate_fails_when_validation_reverses():
    g=SignalExpansionGovernance(); g.register('overfit','freq',0)
    _feed(g,'overfit',0,1.0,-1.0,0.9)
    ev=g.candidates['overfit'].evaluation()
    assert ev['checks']['positive_validation_marginal_utility'] is False
    assert ev['eligible_for_material_challenger_influence'] is False
    with pytest.raises(ValueError): g.candidates['overfit'].authorization_proof()


def test_redundant_candidate_fails_despite_positive_hits():
    g=SignalExpansionGovernance(); g.register('clone','freq',0)
    _feed(g,'clone',0,1.0,1.0,0.10)
    ev=g.candidates['clone'].evaluation()
    assert ev['checks']['novelty_sufficient'] is False
    assert ev['eligible_for_material_challenger_influence'] is False


def test_noise_candidate_does_not_auto_promote():
    g=SignalExpansionGovernance(); g.register('noise','ewma',0)
    contest=0
    for i in range(MIN_CALIBRATION_OOS+MIN_VALIDATION_OOS):
        contest += 1
        delta=1.0 if i%2==0 else -1.0
        g.observe_oos('noise',contest,delta,0.8)
    assert g.candidates['noise'].evaluation()['eligible_for_material_challenger_influence'] is False


def test_registry_roundtrip_is_deterministic_and_authorization_bound(tmp_path: Path):
    g=SignalExpansionGovernance(('a','b')); g.register('good','freq',10); _feed(g,'good',10,1,1,0.8)
    proof=g.candidates['good'].authorization_proof(); g.authorize('good',proof)
    p=tmp_path/'registry.json'; h1=write_registry(p,g); loaded=load_registry(p,('a','b')); p2=tmp_path/'registry2.json'; h2=write_registry(p2,loaded)
    assert h1==h2 and json.loads(p.read_text())==json.loads(p2.read_text())
    with pytest.raises(ValueError): load_registry(p,('other',))


def test_registry_tampering_is_fail_closed_even_when_attacker_resigns_outer_document(tmp_path: Path):
    g=SignalExpansionGovernance(('a',)); g.register('good','freq',10); _feed(g,'good',10,1,1,.9)
    proof=g.candidates['good'].authorization_proof(); g.authorize('good',proof)
    p=tmp_path/'registry.json'; write_registry(p,g); original=json.loads(p.read_text())

    raw=copy.deepcopy(original); raw['candidate_count']=2
    _resign(raw); p.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='candidate_count'): load_registry(p,('a',))

    raw=copy.deepcopy(original); raw['candidates']['good']['mean_delta_hits']=999
    _resign(raw); p.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='candidate good sha256'): load_registry(p,('a',))

    raw=copy.deepcopy(original); row=raw['candidates']['good']; row['authorized_proof_sha256']='f'*64; _resign(row); _resign(raw)
    p.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='proof no longer matches'): load_registry(p,('a',))

    raw=copy.deepcopy(original); row=raw['candidates']['good']; row['status']='SHADOW_CHALLENGER'; row['authorized_proof_sha256']=None; row['material_weight_cap']=0.0; _resign(row); _resign(raw)
    p.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='shadow authorization state'): load_registry(p,('a',))


def test_registry_rejects_missing_or_bad_embedded_hash_and_rules(tmp_path: Path):
    g=SignalExpansionGovernance(('a',)); p=tmp_path/'r.json'; write_registry(p,g); obj=json.loads(p.read_text())
    obj.pop('sha256'); p.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='sha256'): load_registry(p,('a',))
    write_registry(p,g); obj=json.loads(p.read_text()); obj['rules']['champion_influence_prohibited']=False; _resign(obj); p.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='rules mismatch'): load_registry(p,('a',))


def test_candidate_constructor_and_state_guards():
    with pytest.raises(ValueError): CandidateSignalState('','freq',1)
    with pytest.raises(ValueError): CandidateSignalState('x','',1)
    with pytest.raises(ValueError): CandidateSignalState('x','freq',-1)


def test_freeze_hashes_and_snapshots_p11_registry(tmp_path: Path):
    rng=np.random.default_rng(1111); rows=[]
    for i in range(1,86):
        draw=np.sort(rng.choice(np.arange(1,61),6,replace=False))
        row={'Concurso':i,'Data do Sorteio':pd.Timestamp('2022-01-01')+pd.Timedelta(days=i)}
        row.update({f'Bola{j}':int(draw[j-1]) for j in range(1,7)}); rows.append(row)
    data=tmp_path/'m.xlsx'; pd.DataFrame(rows).to_excel(data,index=False)
    out=tmp_path/'freeze.json'; ledger=tmp_path/'ledger.json'; state=tmp_path/'state.json'
    res=cc.freeze_champion_challenger(data,86,out,ledger,state,start=35, enforce_temporal_guard=False)
    assert res['status']=='FROZEN'
    obj=json.loads(out.read_text()); led=json.loads(ledger.read_text()); fr=led['events'][0]
    assert len(obj['signal_expansion_governance_sha256'])==64
    assert len(obj['signal_expansion_registry_sha256'])==64
    snap=fr['snapshot']['signal_expansion_governance']
    assert snap['rules']['new_signals_start_shadow_only'] is True
    assert snap['rules']['champion_influence_prohibited'] is True
    assert snap['rules']['automatic_material_influence'] is False
    assert snap['rules']['registry_embedded_hash_required'] is True
    assert len(fr['hashes']['signal_expansion_governance'])==64


def test_new_oos_revokes_prior_authorization_and_requires_fresh_proof():
    g=SignalExpansionGovernance(); g.register('good2','freq',0); last=_feed(g,'good2',0,1,1,.9)
    proof=g.candidates['good2'].authorization_proof(); g.authorize('good2',proof)
    upd=g.observe_oos('good2',last+1,1,.9)
    assert upd['authorization_revoked_due_new_evidence'] is True
    assert g.candidates['good2'].status=='EVIDENCE_ELIGIBLE'
    assert g.candidates['good2'].authorized_proof_sha256 is None
    assert g.candidates['good2'].material_weight_cap==0.0
    with pytest.raises(ValueError): g.candidates['good2'].assert_material_use_allowed(0.01)


def test_unknown_authorization_and_missing_registry_and_bad_schema(tmp_path: Path):
    g=SignalExpansionGovernance()
    with pytest.raises(ValueError): g.authorize('missing','e'*64)
    missing=load_registry(tmp_path/'none.json',())
    assert missing.candidates=={}
    bad=tmp_path/'bad.json'; bad.write_text(json.dumps({'schema':'BAD','registry_schema':'BAD'}))
    with pytest.raises(ValueError): load_registry(bad,())


def test_insufficient_signal_evidence_serializes_as_strict_json(tmp_path):
    import json
    from smart_signal_expansion_governance import SignalExpansionGovernance, write_registry
    gov=SignalExpansionGovernance(("freq25",))
    state=gov.register("strict-json-candidate","novel",registered_cutoff=100)
    evidence=state.evaluation()
    assert evidence["validation_lcb95_delta_hits"] is None
    assert evidence["checks"]["validation_lcb_positive"] is False
    path=tmp_path/"strict-registry.json"
    write_registry(path,gov)
    raw=path.read_text(encoding="utf-8")
    assert "-Infinity" not in raw and "NaN" not in raw
    json.loads(raw,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
