import json
from pathlib import Path

import smart_finalize_deployment as finalizer

ROOT = Path(__file__).resolve().parent
LEGACY_FREEZE_SHA = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"


def test_finalizer_build_uses_current_epoch_not_legacy_freeze_as_authority():
    proof = finalizer.build(ROOT)
    assert proof["deployment_status"] == "PASS"
    assert proof["checks"]["total_integration_gate_pass"] is True
    assert proof["total_integration"]["status"] == "PASS"
    assert proof["total_integration"]["health"] == "HEALTHY"
    assert proof["total_integration"]["schema"] == "SMART_TOTAL_INTEGRATION_GATE_V2"
    assert proof["checks"]["wmcp_execution_proof_pass"] is True
    assert proof["wmcp_execution"]["command_state"] == "completed"
    assert proof["wmcp_execution"]["exit_code"] == 0
    assert proof["wmcp_execution"]["proof_schema"] == "SMART_WMCP_EXECUTION_PROOF_V2"
    assert proof["wmcp_execution"]["live_supervisor_state"] == "ready"
    assert proof["wmcp_execution"]["live_worker_mode"] in {"LIVE", "DEMAND_DRAINED"}
    assert proof["current_epoch"]["target_contest"] == 3054
    assert proof["current_epoch"]["cutoff_contest"] == 3053
    assert proof["current_epoch"]["result_used"] is False
    if proof["current_epoch"]["status"] == "RESET_READY":
        assert proof["freeze_3054"]["authority"] == "NONE_RESET_READY"
        assert proof["freeze_3054"]["sha256"] is None
    else:
        assert proof["current_epoch"]["status"] == "FROZEN"
        assert proof["freeze_3054"]["authority"] == "CARRY_FORWARD_PROSPECTIVE_AUTHORITY"
        assert len(proof["freeze_3054"]["sha256"]) == 64
    assert proof["agent_skill_orchestration"]["role_executor_count"] == 9
    assert proof["adversarial_claim_audit"]["status"] == "PASS"
    assert proof["prospective_3054_readiness"]["legacy_authority"] == "PRE_FULL_ACTIVATION_HISTORICAL_ONLY"
    assert proof["terminal_executor_3054"]["current_terminal_authority"] is False
    assert proof["terminal_6of6_proven"] is False


def test_rendered_continuity_cannot_restore_legacy_authority_or_inflate_agent_claims():
    proof = finalizer.build(ROOT)
    text = finalizer.render_continuity(proof)
    assert "SMART_MISSION_STATUS.json" in text
    assert "SMART_ACTIVE_EPOCH.json" in text
    assert "CARRY_FORWARD_PROSPECTIVE_AUTHORITY" in text
    assert "nao sao nove LLMs autonomos" in text
    assert "nao execucao direta" in text
    assert "mesmo X" in text
    assert f"Estado terminal: `{proof['mission_state']}`" in text
    assert "Nao declarar `MISSION_PROVEN`" in text


def test_checkpoint_v3_is_explicitly_historical_and_has_no_current_authority():
    checkpoint = json.loads((ROOT / "SMART_EXECUTION_CHECKPOINT_20260904.json").read_text(encoding="utf-8-sig"))
    assert checkpoint["schema"] == "SMART_EXECUTION_CHECKPOINT_20260904_V3"
    assert checkpoint["critical_hashes"]["freeze_3054"] == LEGACY_FREEZE_SHA
    current = finalizer.resolve_current_epoch(ROOT)
    if current["status"] == "FROZEN":
        assert current["freeze_sha256"] != "" and len(current["freeze_sha256"]) == 64
    else:
        assert current["freeze_sha256"] is None
    assert checkpoint["terminal_6of6_proven"] is False
