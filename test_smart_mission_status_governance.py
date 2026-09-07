from pathlib import Path
import json

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
