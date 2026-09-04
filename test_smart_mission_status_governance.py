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


def test_continuity_points_to_canonical_mission_status():
    text = (ROOT / 'SMART_CONTINUITY.md').read_text(encoding='utf-8-sig')
    assert 'SMART_MISSION_STATUS.json' in text
    assert 'Estado terminal: `MISSION_ACTIVE`' in text
    assert 'NÃ£o declarar `MISSION_PROVEN`' in text
