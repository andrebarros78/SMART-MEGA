from pathlib import Path
import json
import pytest

import smart_finalize_deployment as finalizer

ROOT = Path(__file__).resolve().parent


def test_canonical_mission_status_prevents_false_terminal_proof():
    status = json.loads((ROOT / 'SMART_MISSION_STATUS.json').read_text(encoding='utf-8'))
    assert status['schema'] == 'SMART_MISSION_STATUS_V2'
    assert status['status'] == 'MISSION_ACTIVE'
    assert status['terminal_6of6_proven'] is False
    assert status['scientific_predictive_status'] == 'UNPROVEN'
    assert status['prospective_advantage_status'] == 'INSUFFICIENT_EVIDENCE'
    demoted = {item['file']: item['authority'] for item in status['supersedes_terminal_authority_of']}
    assert demoted['SMART_MISSION_PROVEN_6OF6.json'] == 'HISTORICAL_ENGINEERING_ONLY'


def test_continuity_contract_separates_scientific_mission_from_product_completion():
    source = (ROOT / 'smart_finalize_deployment.py').read_text(encoding='utf-8')
    assert 'SMART_MISSION_STATUS.json' in source
    assert 'scientific_mission_controls_product_completion' in source
    assert 'MISSION_ACTIVE` cientifico nao significa produto inacabado' in source


def test_engineering_recertification_cannot_self_promote_to_mission_proven():
    mission = json.loads((ROOT / 'SMART_MISSION_STATUS.json').read_text(encoding='utf-8'))
    invalid = {
        'status': 'MISSION_PROVEN',
        'terminal_authority': True,
        'mission_state': mission['status'],
        'terminal_6of6_proven': mission['terminal_6of6_proven'],
        'scientific_predictive_status': mission['scientific_predictive_status'],
        'prospective_advantage_status': mission['prospective_advantage_status'],
    }
    with pytest.raises(RuntimeError, match='cannot declare MISSION_PROVEN'):
        finalizer.validate_engineering_chain_terminal_boundary(invalid, mission)


def test_engineering_recertification_boundary_mirrors_canonical_mission_status():
    mission = json.loads((ROOT / 'SMART_MISSION_STATUS.json').read_text(encoding='utf-8'))
    valid = {
        'status': 'ENGINEERING_CHAIN_PROVEN',
        'terminal_authority': False,
        'mission_state': mission['status'],
        'terminal_6of6_proven': mission['terminal_6of6_proven'],
        'scientific_predictive_status': mission['scientific_predictive_status'],
        'prospective_advantage_status': mission['prospective_advantage_status'],
    }
    assert finalizer.validate_engineering_chain_terminal_boundary(valid, mission) is True
    source = (ROOT / 'smart_finalize_deployment.py').read_text(encoding='utf-8')
    assert 'write_engineering_chain_proof(root, proof)' in source
    assert 'verify_engineering_chain_proof(root)' in source



def test_canonical_mission_status_classifies_all_root_terminal_tokens():
    import hashlib
    mission = json.loads((ROOT / 'SMART_MISSION_STATUS.json').read_text(encoding='utf-8'))
    assert mission['terminal_6of6_proven'] is False
    rule = mission['terminal_authority_inventory_rule']
    assert rule['unclassified_terminal_claims_fail_closed'] is True
    assert rule['hash_binding_required'] is True
    classified = {item['file']: item for item in mission['supersedes_terminal_authority_of']}
    observed = {}
    for path in sorted(ROOT.glob('*.json')):
        if path.name == 'SMART_MISSION_STATUS.json':
            continue
        try:
            obj = json.loads(path.read_text(encoding='utf-8-sig'))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        status = str(obj.get('status') or '')
        if status.startswith('MISSION_PROVEN') or obj.get('terminal_authority') is True or obj.get('terminal_6of6_proven') is True:
            observed[path.name] = {
                'status': status,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    assert set(observed) == set(classified), f'unclassified/stale terminal claims: observed={set(observed)} classified={set(classified)}'
    for name, current in observed.items():
        item = classified[name]
        assert item['authority'] == 'HISTORICAL_ENGINEERING_ONLY'
        assert item['sha256'] == current['sha256']
        assert item.get('observed_status', '') == current['status']
