from pathlib import Path

import pytest

import smart_3054_adjudication_preflight as preflight
from smart_current_epoch_contract import resolve as resolve_current_epoch

ROOT = Path(__file__).resolve().parent


def _current_document_or_reset_block():
    current = resolve_current_epoch(ROOT)
    assert current["target_contest"] == 3054
    assert current["cutoff_contest"] == 3053
    if current["status"] == "RESET_READY":
        with pytest.raises(ValueError, match="requires a FROZEN active epoch"):
            preflight.build_preflight(ROOT)
        return current, None
    assert current["status"] == "FROZEN"
    document = preflight.build_preflight(ROOT)
    assert document["active_freeze_sha256"] == current["freeze_sha256"]
    return current, document


def test_3054_preflight_fails_closed_before_freeze_or_binds_current_active_freeze():
    current, document = _current_document_or_reset_block()
    if document is None:
        assert current["freeze_authority_present"] is False
        assert current["freeze_sha256"] is None
        return
    assert document["readiness_status"] == "PASS"
    assert document["sequence_before_result"]["valid"] is True
    assert document["sequence_before_result"]["adjudicated"] is False
    assert document["sequence_before_result"]["derived_event_count"] == 0
    assert document["official_result_ingested"] is False
    assert document["canonical_adjudication_executed"] is False
    assert document["terminal_6of6_proven"] is False
    assert document["active_epoch_id"] == current["epoch_id"]


def test_3054_probability_ledger_is_current_epoch_bound_when_frozen():
    current, document = _current_document_or_reset_block()
    if document is None:
        assert current["status"] == "RESET_READY"
        return
    probability = document["probability_ledger"]
    assert probability["main_freeze_file_sha256"] == current["freeze_sha256"]
    assert probability["candidate_count"] == len(probability["summaries"])
    assert probability["candidate_count"] > 0
    assert probability["all_candidates_have_60_probabilities"] is True
    assert probability["all_probability_sums_equal_six"] is True
    assert all(item["probability_count"] == 60 for item in probability["summaries"])
    assert all(abs(item["probability_sum"] - 6.0) <= 1e-8 for item in probability["summaries"])


def test_3054_sandbox_rehearsal_is_non_mutating_when_frozen():
    current, document = _current_document_or_reset_block()
    if document is None:
        assert current["status"] == "RESET_READY"
        return
    sandbox = document["sandbox_rehearsal"]
    assert sandbox["adjudication_created"] is True
    assert sandbox["sequence_valid"] is True
    assert sandbox["missing_derived_event_types"] == []
    assert set(sandbox["derived_event_types"]) == preflight.EXPECTED_DERIVED_TYPES
    assert sandbox["duplicate_adjudication_rejected"] is True
    assert "already adjudicated" in sandbox["duplicate_error"]
    assert sandbox["canonical_ledger_used"] is False
    assert document["canonical_hashes_before"] == document["canonical_hashes_after"]
    assert document["checks"]["canonical_artifacts_unchanged_by_sandbox"] is True


def test_3054_result_store_contract_tracks_active_epoch_cutoff():
    current, document = _current_document_or_reset_block()
    if document is None:
        assert current["cutoff_contest"] == 3053
        return
    store = document["canonical_result_store"]
    assert store["contest_max"] == current["cutoff_contest"]
    assert store["target_absent"] is True
    assert store["contiguous_through_cutoff"] is True
