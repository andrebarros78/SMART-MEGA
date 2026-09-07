from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

import smart_champion_challenger as cc
import smart_evidence_only_promotion as p15
import smart_global_integrity as gi
import smart_sequential_prospective_proof as sp
from test_smart_evidence_only_promotion import _audit, _gate, _integrity, _p13_eligible


def _valid_freeze() -> dict:
    hashes = {name: f'{idx + 700:064x}' for idx, name in enumerate(cc.PROMOTION_LINEAGE_COMPONENTS)}
    lineage = {'schema': cc.PROMOTION_LINEAGE_SCHEMA, 'component_hashes': copy.deepcopy(hashes)}
    raw = json.dumps(lineage, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    lineage['sha256'] = hashlib.sha256(raw).hexdigest()
    return {'hashes': hashes, 'promotion_lineage': lineage, 'frozen_before_result': True, 'causal_cutoff': True}


def test_p14_orchestrator_remaining_fail_closed_branches(monkeypatch):
    with pytest.raises(ValueError, match='invalid SMART signal ledger contract'):
        cc._validate_ledger_contract({'schema': 'bad', 'events': []})
    with pytest.raises(ValueError, match='invalid target contest'):
        cc._validate_ledger_contract({'schema': cc.LEDGER_SCHEMA, 'events': [{'event_type': 'FREEZE', 'target_contest': -1}]})

    h = 'a' * 64
    monkeypatch.setattr(sp, 'validate_target_sequence', lambda ledger, target: {'active_freeze_sha256': h})
    dup = {'schema': cc.LEDGER_SCHEMA, 'events': [
        {'event_type': 'FREEZE', 'target_contest': 9, 'freeze_sha256': h},
        {'event_type': 'FREEZE', 'target_contest': 9, 'freeze_sha256': h},
    ]}
    with pytest.raises(ValueError, match='exactly one active freeze'):
        cc.active_freeze(dup, 9)

    monkeypatch.setattr(cc, '_validate_ledger_contract', lambda ledger: None)
    with pytest.raises(ValueError, match='duplicate freeze hash'):
        cc.paired_events({'schema': cc.LEDGER_SCHEMA, 'events': [
            {'event_type': 'FREEZE', 'target_contest': 1, 'freeze_sha256': h},
            {'event_type': 'FREEZE', 'target_contest': 2, 'freeze_sha256': h},
        ]})
    with pytest.raises(ValueError, match='duplicate adjudication'):
        cc.paired_events({'schema': cc.LEDGER_SCHEMA, 'events': [
            {'event_type': 'ADJUDICATION', 'target_contest': 1},
            {'event_type': 'ADJUDICATION', 'target_contest': 1},
        ]})
    with pytest.raises(ValueError, match='unknown freeze'):
        cc.paired_events({'schema': cc.LEDGER_SCHEMA, 'events': [
            {'event_type': 'ADJUDICATION', 'target_contest': 1, 'freeze_sha256': h},
        ]})
    with pytest.raises(ValueError, match='freeze must precede'):
        cc.paired_events({'schema': cc.LEDGER_SCHEMA, 'events': [
            {'event_type': 'ADJUDICATION', 'target_contest': 1, 'freeze_sha256': h},
            {'event_type': 'FREEZE', 'target_contest': 1, 'freeze_sha256': h},
        ]})
    with pytest.raises(ValueError, match='target mismatch'):
        cc.paired_events({'schema': cc.LEDGER_SCHEMA, 'events': [
            {'event_type': 'FREEZE', 'target_contest': 2, 'freeze_sha256': h},
            {'event_type': 'ADJUDICATION', 'target_contest': 1, 'freeze_sha256': h},
        ]})
    monkeypatch.setattr(cc, 'active_freeze', lambda ledger, target: None)
    with pytest.raises(ValueError, match='does not reference active freeze'):
        cc.paired_events({'schema': cc.LEDGER_SCHEMA, 'events': [
            {'event_type': 'FREEZE', 'target_contest': 1, 'freeze_sha256': h},
            {'event_type': 'ADJUDICATION', 'target_contest': 1, 'freeze_sha256': h},
        ]})


def test_p14_orchestrator_fingerprint_rejection_branches():
    base = _valid_freeze()
    cases = []
    x = copy.deepcopy(base); x['promotion_lineage']['sha256'] = 'x'; cases.append(x)
    x = copy.deepcopy(base); x['promotion_lineage']['sha256'] = 'g' * 64; cases.append(x)
    x = copy.deepcopy(base); x['promotion_lineage']['component_hashes']['engine'] = '0' * 64; cases.append(x)
    x = copy.deepcopy(base); x['hashes'] = []; cases.append(x)
    x = copy.deepcopy(base); x['hashes']['engine'] = 'x'; cases.append(x)
    x = copy.deepcopy(base); x['hashes']['engine'] = 'g' * 64; cases.append(x)
    x = copy.deepcopy(base); x['promotion_lineage']['component_hashes']['engine'] = 'f' * 64
    raw = {k: v for k, v in x['promotion_lineage'].items() if k != 'sha256'}
    x['promotion_lineage']['sha256'] = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    cases.append(x)
    for row in cases:
        assert cc._promotion_candidate_fingerprint(row) is None


def test_p14_orchestrator_lineage_reset_and_invalid_factor(monkeypatch):
    fr1 = _valid_freeze(); fr2 = _valid_freeze()
    fr2['promotion_lineage']['component_hashes']['engine'] = 'e' * 64
    raw = {k: v for k, v in fr2['promotion_lineage'].items() if k != 'sha256'}
    fr2['promotion_lineage']['sha256'] = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    fr2['hashes']['engine'] = 'e' * 64
    fp1 = cc._promotion_candidate_fingerprint(fr1); fp2 = cc._promotion_candidate_fingerprint(fr2)
    assert fp1 and fp2 and fp1 != fp2
    monkeypatch.setattr(cc, 'paired_events', lambda ledger: [
        (1, fr1, {'challenger_hits': 1, 'champion_hits': 1}),
        (2, fr2, {'challenger_hits': 1, 'champion_hits': 1}),
    ])
    status = cc.promotion_eligibility_status({'schema': cc.LEDGER_SCHEMA, 'events': []})
    assert status['discarded_prior_version_pairs'] == 1

    monkeypatch.setattr(cc, 'paired_events', lambda ledger: [(1, fr2, {'challenger_hits': -100, 'champion_hits': 100})])
    monkeypatch.setattr(cc, 'assess_promotion_records', lambda records, e_value: {'eligible': False, 'decision': 'KEEP_CHAMPION'})
    with pytest.raises(ValueError, match='invalid lineage e-process factor'):
        cc.promotion_eligibility_status({'schema': cc.LEDGER_SCHEMA, 'events': []})


def test_p14_orchestrator_freeze_closed_after_adjudication(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(cc, 'require_pre_3052_gate', lambda target: {'status': 'PASS'})
    monkeypatch.setattr(cc.e, 'load_draws', lambda path: (np.zeros((10, 6), dtype=int), np.arange(1, 11)))
    monkeypatch.setattr(cc, 'load_ledger', lambda path: {'schema': cc.LEDGER_SCHEMA, 'events': [
        {'event_type': 'ADJUDICATION', 'target_contest': 11}
    ]})
    monkeypatch.setattr(cc, 'active_freeze', lambda ledger, target: None)
    with pytest.raises(ValueError, match='already adjudicated'):
        cc.freeze_champion_challenger(tmp_path/'x.xlsx', 11, tmp_path/'f.json', tmp_path/'l.json', tmp_path/'s.json', enforce_temporal_guard=False)


def test_p15_remaining_p13_gate_and_integrity_fail_closed_branches():
    bad = _p13_eligible(); bad['candidate_fingerprint'] = 'short'
    with pytest.raises(ValueError, match='64-hex'):
        p15._validated_p13(bad)
    bad = _p13_eligible(); bad['candidate_fingerprint'] = 'g' * 64
    with pytest.raises(ValueError, match='hexadecimal'):
        p15._validated_p13(bad)

    gate = _gate(); gate['mandatory_before_freeze'] = False
    assert 'implementation_gate_mandatory_flag_invalid' in p15._gate_evidence(gate)[0]
    gate = _gate(); gate['completion_rule'] = 'bad'
    assert 'implementation_gate_completion_rule_invalid' in p15._gate_evidence(gate)[0]
    gate = _gate(); gate['governance'] = {}
    assert 'implementation_gate_governance_invalid' in p15._gate_evidence(gate)[0]
    gate = _gate(); gate['items'][0]['id'] = 'BAD'
    assert 'implementation_gate_ids_invalid' in p15._gate_evidence(gate)[0]
    gate = _gate(); gate['items'][0] = None
    blockers, summary = p15._gate_evidence(gate)
    assert 'implementation_gate_not_15_of_15_proven' in blockers and 'INVALID_ITEM' in summary['pending_items']

    x = _integrity(); x['status'] = 'FAIL'
    assert 'global_integrity_not_pass' in p15._global_integrity_evidence(x)[0]
    x = _integrity(); x['material_deficiencies'] = ['x']
    assert 'global_integrity_material_deficiencies_present' in p15._global_integrity_evidence(x)[0]
    x = _integrity(); x['proof_file_sha256'] = 'short'
    assert 'global_integrity_proof_hash_missing' in p15._global_integrity_evidence(x)[0]


def test_p15_remaining_audit_fail_closed_branches():
    p13 = _p13_eligible()
    audit = _audit(p13)
    audit['prospective_ledger']['promotion_lineage_comparison']['candidate_fingerprint'] = 'b' * 64
    audit['prospective_ledger']['promotion_lineage_comparison']['lineage_recomputed_independently'] = False
    audit['prospective_ledger']['promotion_lineage_comparison']['e_value'] = float(p13['e_value']) + 1.0
    audit.pop('material_deficiencies')
    audit.pop('independence')
    audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})
    blockers = p15._audit_evidence(audit, p13)[0]
    assert 'p13_p14_lineage_fingerprint_mismatch' in blockers
    assert 'independent_audit_promotion_lineage_not_recomputed' in blockers
    assert 'p13_p14_lineage_e_value_mismatch' in blockers
    assert 'independent_audit_material_deficiencies_missing' in blockers
    assert 'independent_audit_independence_evidence_missing' in blockers

    audit = _audit(p13)
    audit['independence'] = {'status':'FAIL','independent':False,'static_import_scan':False,'forbidden_dependencies_found':['x']}
    audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})
    assert 'independent_audit_independence_evidence_invalid' in p15._audit_evidence(audit, p13)[0]


def test_p15_file_wrapper_error_and_import_fallback_branches(monkeypatch, tmp_path: Path):
    gate_path = tmp_path/'gate.json'; audit_path = tmp_path/'audit.json'
    gate_path.write_text(json.dumps(_gate()), encoding='utf-8')
    audit_path.write_text(json.dumps(_audit()), encoding='utf-8')
    monkeypatch.setattr(gi, 'verify_global_integrity', lambda **kwargs: (_ for _ in ()).throw(ValueError('boom')))
    out = p15.assess_evidence_only_promotion_from_files(_p13_eligible(), gate_path, audit_path)
    assert out['authorized'] is False and 'global_integrity_not_pass' in out['blockers']

    good_integrity = _integrity()
    monkeypatch.setattr(gi, 'verify_global_integrity', lambda **kwargs: good_integrity)
    old = gi.DEFAULT_PROOF_PATH
    monkeypatch.delattr(gi, 'DEFAULT_PROOF_PATH')
    try:
        out = p15.assess_evidence_only_promotion_from_files(_p13_eligible(), gate_path, audit_path)
        assert out['evidence_files']['global_integrity_file'].endswith('SMART_GLOBAL_INTEGRITY_PROOF.json')
    finally:
        monkeypatch.setattr(gi, 'DEFAULT_PROOF_PATH', old, raising=False)


def test_p15_authorization_requires_global_integrity_flag():
    authorized = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), _audit(), _integrity())
    bad = copy.deepcopy(authorized)
    bad['global_integrity_verified'] = False
    bad['sha256'] = p15.sha256_json({k:v for k,v in bad.items() if k!='sha256'})
    with pytest.raises(PermissionError, match='global integrity'):
        p15.require_authorized_promotion(bad)

def test_p14_default_gate_path_enforces_current_red_team_and_global_integrity(monkeypatch, tmp_path: Path):
    import smart_continuous_red_team as rt
    import smart_global_integrity as gi
    gate_path = tmp_path / 'gate.json'
    gate = {
        'schema': cc.PRE_3052_GATE_SCHEMA,
        'freeze_allowed': True,
        'items': [
            {'priority': i, 'id': f'P{i:02d}', 'status': 'PROVEN', 'evidence': [{'proof': i}]}
            for i in range(1, 16)
        ],
    }
    gate_path.write_text(json.dumps(gate), encoding='utf-8')
    calls = []
    monkeypatch.setattr(cc, 'PRE_3052_GATE_PATH', gate_path)
    monkeypatch.setattr(rt, 'verify_latest_report', lambda **kwargs: calls.append(('red', kwargs)) or {'status': 'PASS'})
    monkeypatch.setattr(gi, 'verify_global_integrity', lambda **kwargs: calls.append(('global', kwargs)) or {'status': 'PASS'})
    out = cc.require_pre_3052_gate(3052, gate_path)
    assert out['freeze_allowed'] is True
    assert [name for name, _ in calls] == ['red', 'global']


def test_p14_immutable_state_archive_fail_closed_branches(tmp_path, monkeypatch):
    import smart_champion_challenger as cc
    state = tmp_path / 'state.json'
    state.write_text('{"x":1}', encoding='utf-8')
    expected = cc.sha256(state)
    archive = cc.archive_state_snapshot(state, expected)
    assert archive.is_file() and cc.sha256(archive) == expected
    assert cc.archive_state_snapshot(state, expected) == archive
    archive.write_text('corrupt', encoding='utf-8')
    with pytest.raises(ValueError, match='collision/mismatch'):
        cc.archive_state_snapshot(state, expected)

    archive.unlink()
    original_sha = cc.sha256
    monkeypatch.setattr(cc, 'sha256', lambda path: '0' * 64 if Path(path).parent.name == 'SMART_STATE_ARCHIVE' else original_sha(Path(path)))
    with pytest.raises(ValueError, match='write verification failed'):
        cc.archive_state_snapshot(state, expected)
    assert not archive.exists()

