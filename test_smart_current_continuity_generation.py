import json
from pathlib import Path

import smart_finalize_deployment as finalizer

ROOT = Path(__file__).resolve().parent
FREEZE_SHA = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"


def test_finalizer_build_includes_current_governance_and_3054_readiness():
    proof = finalizer.build(ROOT)
    assert proof["deployment_status"] == "PASS"
    assert proof["freeze_3054"]["sha256"] == FREEZE_SHA
    assert proof["hypothesis_state"]["registry_schema"] == "SMART_HYPOTHESIS_REGISTRY_V4"
    assert proof["hypothesis_state"]["null_proof_claim"] is False
    assert proof["hypothesis_state"]["predictive_promotion_authority"] is False
    assert proof["canonical_result_store"]["contest_max"] == 3053
    assert proof["prospective_3054_readiness"]["preflight_status"] == "PASS"
    assert proof["prospective_3054_readiness"]["full_cycle_sandbox_status"] == "PASS"
    assert proof["official_evidence_policy"]["secondary_stale_or_unavailable_never_counts_as_consensus"] is True
    assert proof["terminal_executor_3054"]["sandbox_status"] == "PASS"
    assert proof["terminal_executor_3054"]["sandbox_repeat_idempotent"] is True
    assert proof["terminal_executor_3054"]["current_independent_audit_pair_count"] == 3
    assert proof["terminal_6of6_proven"] is False


def test_rendered_continuity_cannot_drop_canonical_mission_authority_again():
    proof = finalizer.build(ROOT)
    text = finalizer.render_continuity(proof)
    assert "SMART_MISSION_STATUS.json" in text
    assert "A autoridade canônica do estado da missão" in text
    assert "Estado terminal: `MISSION_ACTIVE`" in text
    assert "Não declarar `MISSION_PROVEN`" in text
    assert "SMART_HYPOTHESIS_REGISTRY_V4" in text
    assert "preflight" in text.lower()
    assert "adjudicar → aprender → prova sequencial" in text


def test_checkpoint_v3_records_new_proofs_without_false_terminal_claim():
    checkpoint = json.loads((ROOT / "SMART_EXECUTION_CHECKPOINT_20260904.json").read_text(encoding="utf-8-sig"))
    assert checkpoint["schema"] == "SMART_EXECUTION_CHECKPOINT_20260904_V3"
    assert checkpoint["critical_hashes"]["freeze_3054"] == FREEZE_SHA
    assert checkpoint["hypothesis_reconciliation"]["status"] == "PASS"
    assert checkpoint["canonical_result_store"]["contest_max"] == 3053
    assert checkpoint["prospective_3054"]["preflight_status"] == "PASS"
    assert checkpoint["prospective_3054"]["full_cycle_sandbox_status"] == "PASS"
    assert checkpoint["prospective_3054"]["official_result_ingested"] is False
    assert checkpoint["prospective_3054"]["terminal_executor_sandbox_status"] == "PASS"
    assert checkpoint["prospective_3054"]["terminal_executor_repeat_idempotent"] is True
    assert checkpoint["prospective_3054"]["independent_audit_pair_count"] == 3
    assert checkpoint["prospective_3054"]["prospective_authority_pair_count"] == 3
    assert checkpoint["terminal_6of6_proven"] is False
