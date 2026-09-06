from pathlib import Path

import pytest

import smart_3054_full_cycle_sandbox as sandbox
from smart_current_epoch_contract import resolve as resolve_current_epoch

ROOT = Path(__file__).resolve().parent


def _sandbox_or_reset_block():
    current = resolve_current_epoch(ROOT)
    if current["status"] == "RESET_READY":
        with pytest.raises(ValueError, match="requires a FROZEN active epoch"):
            sandbox.build_sandbox(ROOT)
        return current, None
    assert current["status"] == "FROZEN"
    document = sandbox.build_sandbox(ROOT)
    assert document["active_freeze_sha256"] == current["freeze_sha256"]
    return current, document


def test_full_3054_sandbox_reaches_learning_sequence_without_current_state_mutation():
    current, document = _sandbox_or_reset_block()
    if document is None:
        assert current["freeze_authority_present"] is False
        return
    assert document["status"] == "PASS"
    assert document["active_epoch_id"] == current["epoch_id"]
    assert document["target_date"] == "06/09/2026"
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


def test_full_3054_sandbox_duplicate_guards_when_frozen():
    current, document = _sandbox_or_reset_block()
    if document is None:
        assert current["status"] == "RESET_READY"
        return
    guards = document["duplicate_guards"]
    assert guards["learning_rejected"] is True
    assert guards["proof_rejected"] is True
    assert "already recorded" in guards["learning_error"]
    assert "already recorded" in guards["proof_error"] or "already" in guards["proof_error"]
