from pathlib import Path
import smart_continuity_consolidator as cc

ROOT=Path(__file__).resolve().parent

def test_chat_continuity_consolidation_is_canonical_and_complete():
    doc=cc.build(ROOT)
    assert doc['consolidation_status']=='PASS'
    assert all(doc['checks'].values())
    assert doc['prospective_freeze']['sha256']==cc.FREEZE_EXPECTED_SHA256
    assert doc['canonical_data']['sha256']==cc.DATA_EXPECTED_SHA256
    assert doc['powered_falsification']['resolution_sufficient'] is True
    assert doc['monte_carlo_convergence']['predictive_weight_authorized'] is False
    assert doc['mission_state']=='MISSION_ACTIVE'
    assert doc['terminal_6of6_proven'] is False
