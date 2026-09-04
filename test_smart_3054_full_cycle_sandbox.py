from pathlib import Path

import smart_3054_full_cycle_sandbox as sandbox

ROOT = Path(__file__).resolve().parent
FREEZE_SHA = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"


def test_full_3054_sandbox_reaches_learning_and_sequence_proof_without_touching_canonical_state():
    document = sandbox.build_sandbox(ROOT)
    assert document["status"] == "PASS"
    assert document["active_freeze_sha256"] == FREEZE_SHA
    assert document["learning"]["last_contest"] == 3054
    assert document["learning"]["learning_event_status"] == "LEARNING_RECORDED"
    assert document["sequence"]["valid"] is True
    assert document["sequence"]["learning_recorded"] is True
    assert document["sequence"]["proof_recorded"] is True
    assert document["target_event_types"][-2:] == ["LEARNING_UPDATE", "SEQUENTIAL_PROOF"]
    assert document["canonical_hashes_before"] == document["canonical_hashes_after"]
    assert document["checks"]["canonical_protected_artifacts_unchanged"] is True
    assert document["official_result_ingested"] is False
    assert document["canonical_learning_executed"] is False
    assert document["terminal_6of6_proven"] is False


def test_full_3054_sandbox_rejects_duplicate_learning_and_proof():
    document = sandbox.build_sandbox(ROOT)
    guards = document["duplicate_guards"]
    assert guards["learning_rejected"] is True
    assert guards["proof_rejected"] is True
    assert "already recorded" in guards["learning_error"]
    assert "already recorded" in guards["proof_error"] or "already" in guards["proof_error"]
