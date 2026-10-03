from __future__ import annotations



import copy

import hashlib

import json

from pathlib import Path



import numpy as np

import pandas as pd

import pytest



import smart_champion_challenger as cc

import smart_evidence_only_promotion as p15
import smart_global_integrity as gi

from smart_promotion_gate import assess_promotion_records





def _p13_eligible() -> dict:

    status = assess_promotion_records(

        [{'challenger_hits': 4, 'champion_hits': 3} for _ in range(20)],

        e_value=10.0,

    )

    status['candidate_fingerprint'] = 'a' * 64

    status['lineage_pair_count'] = int(status['n'])

    return status





def _p13_ineligible() -> dict:

    return assess_promotion_records([], e_value=1.0)





def _gate(all_proven: bool = True, freeze_allowed: bool = True) -> dict:
    items = []
    ids = list(gi.EXPECTED_GATE_IDS)
    for i, item_id in enumerate(ids, start=1):
        proven = all_proven or i != 14
        items.append({
            'priority': i, 'id': item_id,
            'status': 'PROVEN' if proven else 'TO_VERIFY_OR_IMPLEMENT',
            'evidence': [{'file': f'proof-{i}.json', 'sha256': f'{i:064x}'[-64:]}] if proven else [],
        })
    proven_count = sum(1 for row in items if row['status'] == 'PROVEN')
    return {
        'schema': p15.IMPLEMENTATION_GATE_SCHEMA, 'target_contest': 3052,
        'mandatory_before_freeze': True, 'freeze_allowed': freeze_allowed,
        'completion_rule': 'ALL_15_ITEMS_STATUS_PROVEN_WITH_EVIDENCE',
        'governance': {k: True for k in gi.REQUIRED_GATE_GOVERNANCE},
        'items': items,
        'progress': {'proven_items': proven_count, 'total_items': 15,
                     'remaining_items': 15 - proven_count,
                     'remaining_ids': [row['id'] for row in items if row['status'] != 'PROVEN']},
    }


def _integrity() -> dict:
    return {
        'status': 'PASS', 'proof_file': gi.DEFAULT_PROOF_PATH.name, 'proof_file_sha256': 'f' * 64,
        'critical_source_hashes_current': True, 'coverage_current': True,
        'red_team_current': True, 'independent_audit_current': True,
        'full_regression_current': True, 'material_deficiencies': [],
    }


def _audit(p13_status: dict | None = None) -> dict:

    p13_status = p13_status or _p13_eligible()

    comparison = {

        'adjudicated_contests': int(p13_status['n']),

        'champion_hits': int(p13_status['champion_hits']),

        'challenger_hits': int(p13_status['challenger_hits']),

        'advantage_hits': int(p13_status['advantage_hits']),

        'cumulative_regret': int(p13_status['cumulative_regret']),

        'all_pairs_recomputed': True,

    }

    lineage_comparison = {

        **{k: comparison[k] for k in ('adjudicated_contests','champion_hits','challenger_hits','advantage_hits','cumulative_regret')},

        'candidate_fingerprint': p13_status.get('candidate_fingerprint'),

        'e_value': float(p13_status['e_value']),

        'lineage_recomputed_independently': True,

        'lineage_pairs_recomputed': True,

    }

    audit = {

        'schema': p15.INDEPENDENT_AUDIT_SCHEMA,

        'status': 'PASS',

        'coverage': {'status': 'PASS', 'count': 3},

        'prospective_ledger': {

            'status': 'PASS',

            'pair_count': int(p13_status['n']),

            'no_future_leakage': True,

            'hash_integrity': True,

            'e_process_recomputed': True,

            'full_champion_comparison': comparison,

            'promotion_lineage_comparison': lineage_comparison,

        },

        'deterministic_replay': {

            'status': 'PASS',

            'deterministic': True,

            'causal_cutoff_verified': True,
            'independent_decision_oracle': {
                'status': 'PASS', 'verified': True, 'production_engine_imported': False,
            },

        },

        'checks': {name: True for name in p15.REQUIRED_AUDIT_CHECKS},

        'promotion_authority': False,

        'independent_of_promotion_decision': True,

        'independence': {'status':'PASS','independent':True,'static_import_scan':True,'forbidden_dependencies_found':[]},

        'material_deficiencies': [],

    }

    audit['sha256'] = p15.sha256_json(audit)

    return audit





def _ledger(n: int = 20, challenger: int = 6, champion: int = 3, e_value: float = 10.0) -> dict:

    events = []

    component_hashes = {name: f'{idx + 101:064x}' for idx, name in enumerate(cc.PROMOTION_LINEAGE_COMPONENTS)}

    lineage = {'schema': cc.PROMOTION_LINEAGE_SCHEMA, 'component_hashes': component_hashes}

    lineage['sha256'] = hashlib.sha256(json.dumps(lineage, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    for i in range(n):

        contest = 5000 + i

        h = f'{contest:064x}'[-64:]

        events.append({

            'event_type': 'FREEZE',

            'target_contest': contest,

            'freeze_sha256': h,

            'frozen_before_result': True,

            'causal_cutoff': True,

            'hashes': component_hashes,

            'promotion_lineage': lineage,

        })

        events.append({

            'event_type': 'ADJUDICATION',

            'target_contest': contest,

            'freeze_sha256': h,

            'challenger_hits': challenger,

            'champion_hits': champion,

            'e_value_after': e_value,

        })

    return {'schema': cc.LEDGER_SCHEMA, 'events': events}





def test_policy_is_fail_closed_and_requires_all_evidence_layers():

    policy = p15.policy_snapshot()

    assert policy['schema'] == p15.POLICY_SCHEMA

    assert policy['p13_statistical_eligibility_required'] is True

    assert policy['p14_independent_audit_pass_required'] is True

    assert policy['all_15_implementation_items_proven_required'] is True
    assert policy['current_global_integrity_proof_required'] is True

    assert policy['missing_or_invalid_evidence_keeps_champion'] is True

    assert policy['manual_override_prohibited'] is True

    assert len(policy['sha256']) == 64





def test_ineligible_p13_keeps_champion_without_loading_other_evidence():

    status = p15.assess_evidence_only_promotion(_p13_ineligible())

    assert status['authorized'] is False

    assert status['decision'] == 'KEEP_CHAMPION'

    assert status['champion_remains_active'] is True

    assert status['blockers'] == ['p13_not_eligible']





def test_p13_eligibility_alone_never_authorizes_promotion():

    status = p15.assess_evidence_only_promotion(_p13_eligible())

    assert status['p13_eligible'] is True

    assert status['authorized'] is False

    assert 'implementation_gate_missing' in status['blockers']

    assert 'independent_audit_missing' in status['blockers']





def test_full_gate_and_valid_independent_audit_authorize_only_when_metrics_match():

    p13_status = _p13_eligible()

    status = p15.assess_evidence_only_promotion(p13_status, _gate(), _audit(p13_status), _integrity())

    assert status['authorized'] is True

    assert status['decision'] == 'PROMOTE_SIGNAL_INTELLIGENCE_CHALLENGER'

    assert status['production_switch_may_proceed'] is True

    assert status['known_material_deficiency_count'] == 0

    assert status['blockers'] == []

    assert p15.require_authorized_promotion(status) is status





def test_global_integrity_is_mandatory_for_authorization():
    p13_status = _p13_eligible()
    blocked = p15.assess_evidence_only_promotion(p13_status, _gate(), _audit(p13_status))
    assert blocked['authorized'] is False
    assert 'global_integrity_missing_or_unverified' in blocked['blockers']
    assert blocked['global_integrity_verified'] is False
    bad = _integrity(); bad['coverage_current'] = False
    blocked = p15.assess_evidence_only_promotion(p13_status, _gate(), _audit(p13_status), bad)
    assert 'global_integrity_current_evidence_incomplete' in blocked['blockers']
    allowed = p15.assess_evidence_only_promotion(p13_status, _gate(), _audit(p13_status), _integrity())
    assert allowed['authorized'] is True and allowed['global_integrity_verified'] is True


def test_gate_must_be_exactly_15_of_15_proven_and_freeze_allowed():

    status = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(all_proven=False), _audit())

    assert status['authorized'] is False

    assert 'implementation_gate_not_15_of_15_proven' in status['blockers']

    assert 'p14_not_proven_in_implementation_gate' in status['blockers']



    status = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(freeze_allowed=False), _audit())

    assert status['authorized'] is False

    assert 'implementation_gate_freeze_not_allowed' in status['blockers']





def test_gate_schema_item_count_priorities_and_p15_status_are_fail_closed():

    gate = _gate()

    gate['schema'] = 'bad'

    assert 'implementation_gate_schema_invalid' in p15.assess_evidence_only_promotion(_p13_eligible(), gate, _audit())['blockers']



    gate = _gate(); gate['items'] = gate['items'][:-1]

    assert 'implementation_gate_items_invalid' in p15.assess_evidence_only_promotion(_p13_eligible(), gate, _audit())['blockers']



    gate = _gate(); gate['items'][0]['priority'] = 99

    assert 'implementation_gate_priorities_invalid' in p15.assess_evidence_only_promotion(_p13_eligible(), gate, _audit())['blockers']



    gate = _gate(); gate['items'][-1]['status'] = 'TO_VERIFY_OR_IMPLEMENT'; gate['items'][-1]['evidence'] = []

    blockers = p15.assess_evidence_only_promotion(_p13_eligible(), gate, _audit())['blockers']

    assert 'p15_not_proven_in_implementation_gate' in blockers





def test_audit_hash_independence_checks_and_material_deficiencies_are_mandatory():

    audit = _audit(); audit['status'] = 'FAIL'

    blockers = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']

    assert 'independent_audit_not_pass' in blockers

    assert 'independent_audit_self_hash_invalid' in blockers



    audit = _audit(); audit['promotion_authority'] = True; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    assert 'independent_audit_has_promotion_authority' in p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']



    audit = _audit(); audit['independent_of_promotion_decision'] = False; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    assert 'independent_audit_independence_not_proven' in p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']



    audit = _audit(); audit['material_deficiencies'] = ['open regression']; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    assert 'known_material_deficiencies_present' in p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']





def test_audit_required_checks_ledger_replay_coverage_and_pair_recomputation_are_mandatory():

    audit = _audit(); audit['checks']['hash_integrity'] = False; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    assert 'independent_audit_required_checks_failed' in p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']



    audit = _audit(); audit['prospective_ledger']['status'] = 'FAIL'; audit['prospective_ledger']['no_future_leakage'] = False; audit['prospective_ledger']['hash_integrity'] = False; audit['prospective_ledger']['e_process_recomputed'] = False; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    blockers = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']

    assert 'independent_audit_ledger_not_pass' in blockers

    assert 'independent_audit_future_leakage_not_cleared' in blockers

    assert 'independent_audit_hash_integrity_not_cleared' in blockers

    assert 'independent_audit_e_process_not_recomputed' in blockers



    audit = _audit(); audit['deterministic_replay']['status'] = 'FAIL'; audit['deterministic_replay']['deterministic'] = False; audit['deterministic_replay']['causal_cutoff_verified'] = False; audit['coverage']['status'] = 'FAIL'; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    blockers = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']

    assert 'independent_audit_replay_not_deterministic' in blockers

    assert 'independent_audit_replay_causal_cutoff_not_verified' in blockers

    assert 'independent_audit_coverage_not_pass' in blockers



    audit = _audit(); audit['prospective_ledger']['full_champion_comparison']['all_pairs_recomputed'] = False; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    assert 'independent_audit_not_all_pairs_recomputed' in p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']





def test_p13_p14_metric_identity_is_required_for_reproducibility():

    p13_status = _p13_eligible()

    for field in ('adjudicated_contests', 'champion_hits', 'challenger_hits', 'advantage_hits', 'cumulative_regret'):

        audit = _audit(p13_status)

        audit['prospective_ledger']['promotion_lineage_comparison'][field] += 1

        audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

        status = p15.assess_evidence_only_promotion(p13_status, _gate(), audit)

        assert any(b.startswith('p13_p14_metric_mismatch_') for b in status['blockers'])



    audit = _audit(p13_status); audit['prospective_ledger']['promotion_lineage_comparison']['adjudicated_contests'] += 1; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    assert 'p13_p14_pair_count_mismatch' in p15.assess_evidence_only_promotion(p13_status, _gate(), audit)['blockers']





def test_invalid_p13_contract_is_rejected_instead_of_coerced():

    with pytest.raises(ValueError): p15.assess_evidence_only_promotion(None)  # type: ignore[arg-type]

    bad = _p13_eligible(); bad['eligible'] = 'yes'

    with pytest.raises(ValueError): p15.assess_evidence_only_promotion(bad)

    bad = _p13_eligible(); bad['decision'] = 'KEEP_CHAMPION'

    with pytest.raises(ValueError): p15.assess_evidence_only_promotion(bad)

    bad = _p13_ineligible(); bad['decision'] = p15.P13_PROMOTE_DECISION

    with pytest.raises(ValueError): p15.assess_evidence_only_promotion(bad)

    for field in ('n', 'challenger_hits', 'champion_hits', 'advantage_hits', 'cumulative_regret', 'e_value'):

        bad = _p13_eligible(); bad[field] = float('nan')

        with pytest.raises(ValueError): p15.assess_evidence_only_promotion(bad)

    bad = _p13_eligible(); bad['n'] = -1

    with pytest.raises(ValueError): p15.assess_evidence_only_promotion(bad)





def test_file_based_assessment_records_evidence_hashes_and_fails_closed_when_missing(monkeypatch, tmp_path: Path):

    monkeypatch.setattr(gi, 'verify_global_integrity', lambda **kwargs: _integrity())
    gate_path = tmp_path / 'gate.json'; audit_path = tmp_path / 'audit.json'

    gate_path.write_text(json.dumps(_gate()), encoding='utf-8')

    audit_path.write_text(json.dumps(_audit()), encoding='utf-8')

    status = p15.assess_evidence_only_promotion_from_files(_p13_eligible(), gate_path, audit_path)

    assert status['authorized'] is True

    assert len(status['evidence_files']['implementation_gate_sha256']) == 64

    assert len(status['evidence_files']['independent_audit_file_sha256']) == 64



    missing = p15.assess_evidence_only_promotion_from_files(_p13_eligible(), tmp_path/'missing-gate.json', tmp_path/'missing-audit.json')

    assert missing['authorized'] is False

    assert 'implementation_gate_missing' in missing['blockers']

    assert 'independent_audit_missing' in missing['blockers']





def test_production_switch_guard_rejects_missing_tampered_or_blocked_authorization():

    with pytest.raises(PermissionError): p15.require_authorized_promotion(None)  # type: ignore[arg-type]

    with pytest.raises(PermissionError): p15.require_authorized_promotion({'schema':'bad'})

    blocked = p15.assess_evidence_only_promotion(_p13_eligible())

    with pytest.raises(PermissionError): p15.require_authorized_promotion(blocked)

    authorized = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), _audit(), _integrity())

    tampered = copy.deepcopy(authorized); tampered['reason'] = 'tampered'

    with pytest.raises(PermissionError): p15.require_authorized_promotion(tampered)

    tampered = copy.deepcopy(authorized); tampered['known_material_deficiency_count'] = 1; tampered['blockers'] = ['x']; tampered['sha256'] = p15.sha256_json({k:v for k,v in tampered.items() if k!='sha256'})

    with pytest.raises(PermissionError): p15.require_authorized_promotion(tampered)





def test_champion_challenger_separates_p13_eligibility_from_p15_authorization(monkeypatch, tmp_path: Path):

    monkeypatch.setattr(gi, 'verify_global_integrity', lambda **kwargs: _integrity())
    ledger = _ledger()

    p13_status = cc.promotion_eligibility_status(ledger)

    assert p13_status['eligible'] is True

    assert p13_status['decision'] == p15.P13_PROMOTE_DECISION



    blocked = cc.promotion_status(ledger, tmp_path/'missing-gate.json', tmp_path/'missing-audit.json')

    assert blocked['authorized'] is False

    assert blocked['decision'] == 'KEEP_CHAMPION'



    gate_path = tmp_path/'gate.json'; audit_path = tmp_path/'audit.json'

    gate_path.write_text(json.dumps(_gate()), encoding='utf-8')

    audit_path.write_text(json.dumps(_audit(p13_status)), encoding='utf-8')

    allowed = cc.promotion_status(ledger, gate_path, audit_path)

    assert allowed['authorized'] is True

    assert allowed['decision'] == p15.FINAL_PROMOTE_DECISION





def _dataset(n: int, seed: int = 1515) -> pd.DataFrame:

    rng = np.random.default_rng(seed)

    rows = []

    for contest in range(1, n + 1):

        draw = np.sort(rng.choice(np.arange(1, 61), 6, replace=False))

        row = {'Concurso': contest, 'Data do Sorteio': pd.Timestamp('2025-01-01') + pd.Timedelta(days=contest)}

        row.update({f'Bola{i}': int(draw[i - 1]) for i in range(1, 7)})

        rows.append(row)

    return pd.DataFrame(rows)





def test_future_freeze_hashes_and_snapshots_p15_policy(tmp_path: Path):

    data = tmp_path/'pre.xlsx'; out = tmp_path/'freeze.json'; ledger = tmp_path/'ledger.json'; state = tmp_path/'state.json'

    _dataset(40).to_excel(data, index=False)

    result = cc.freeze_champion_challenger(data, 41, out, ledger, state, start=20, enforce_temporal_guard=False)

    assert result['status'] == 'FROZEN'

    frozen = json.loads(out.read_text(encoding='utf-8'))

    led = json.loads(ledger.read_text(encoding='utf-8'))

    event = led['events'][0]

    assert frozen['evidence_only_promotion_sha256'] == cc.sha256_source_file(Path('smart_evidence_only_promotion.py'))

    assert event['hashes']['evidence_only_promotion'] == frozen['evidence_only_promotion_sha256']

    assert frozen['evidence_only_promotion_policy'] == p15.policy_snapshot()

    assert event['snapshot']['evidence_only_promotion_policy'] == frozen['evidence_only_promotion_policy']

    assert frozen['production_switch_performed'] is False

    assert frozen['champion_remains_active'] is True





def test_remaining_fail_closed_audit_shape_guards_and_authorization_decision():

    assert p15._audit_self_hash_valid({'sha256': 'short'}) is False



    audit = _audit(); audit['schema'] = 'bad'; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    assert 'independent_audit_schema_invalid' in p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']



    audit = _audit(); audit['checks'] = []; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    blockers = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']

    assert 'independent_audit_checks_missing' in blockers



    audit = _audit(); audit['prospective_ledger'] = []; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    blockers = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']

    assert 'independent_audit_ledger_evidence_missing' in blockers

    assert 'independent_audit_champion_comparison_missing' in blockers



    audit = _audit(); audit['deterministic_replay'] = []; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    assert 'independent_audit_replay_missing' in p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']



    audit = _audit(); audit['prospective_ledger']['full_champion_comparison'] = []; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    assert 'independent_audit_champion_comparison_missing' in p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']



    audit = _audit(); audit['material_deficiencies'] = 'bad'; audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})

    blockers = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), audit)['blockers']

    assert 'independent_audit_material_deficiencies_invalid' in blockers

    assert 'known_material_deficiencies_present' in blockers



    authorized = p15.assess_evidence_only_promotion(_p13_eligible(), _gate(), _audit(), _integrity())

    bad_decision = copy.deepcopy(authorized)

    bad_decision['decision'] = 'KEEP_CHAMPION'

    bad_decision['sha256'] = p15.sha256_json({k:v for k,v in bad_decision.items() if k!='sha256'})

    with pytest.raises(PermissionError, match='decision'):

        p15.require_authorized_promotion(bad_decision)



