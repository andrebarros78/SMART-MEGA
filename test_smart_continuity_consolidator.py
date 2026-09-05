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
    assert doc['checks']['total_integration_gate_pass'] is True
    assert doc['total_integration']['status']=='PASS'
    assert doc['total_integration']['health']=='HEALTHY'
    assert doc['checks']['wmcp_execution_proof_pass'] is True
    assert doc['wmcp_execution']['command_state']=='completed'
    assert doc['wmcp_execution']['exit_code']==0
    assert doc['monte_carlo_convergence']['predictive_weight_authorized'] is False
    assert doc['mission_state']=='MISSION_ACTIVE'
    assert doc['terminal_6of6_proven'] is False
