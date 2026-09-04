from pathlib import Path

import smart_3054_adjudication_preflight as preflight

ROOT = Path(__file__).resolve().parent
FREEZE_SHA = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"


def test_3054_preflight_is_bound_to_active_freeze_and_pre_result_state():
    document = preflight.build_preflight(ROOT)
    assert document["readiness_status"] == "PASS"
    assert document["active_freeze_sha256"] == FREEZE_SHA
    assert document["sequence_before_result"]["valid"] is True
    assert document["sequence_before_result"]["adjudicated"] is False
    assert document["sequence_before_result"]["derived_event_count"] == 0
    assert document["official_result_ingested"] is False
    assert document["canonical_adjudication_executed"] is False
    assert document["terminal_6of6_proven"] is False


def test_3054_probability_ledger_preserves_full_distribution_for_every_candidate():
    document = preflight.build_preflight(ROOT)
    probability = document["probability_ledger"]
    assert probability["candidate_count"] == len(probability["summaries"])
    assert probability["candidate_count"] > 0
    assert probability["all_candidates_have_60_probabilities"] is True
    assert probability["all_probability_sums_equal_six"] is True
    assert all(item["probability_count"] == 60 for item in probability["summaries"])
    assert all(abs(item["probability_sum"] - 6.0) <= 1e-8 for item in probability["summaries"])


def test_3054_sandbox_rehearsal_proves_sequence_and_duplicate_guard_without_canonical_mutation():
    document = preflight.build_preflight(ROOT)
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


def test_3054_canonical_result_store_is_ready_for_next_official_result():
    document = preflight.build_preflight(ROOT)
    store = document["canonical_result_store"]
    assert store["contest_max"] == 3053
    assert store["target_absent"] is True
    assert store["contiguous_through_cutoff"] is True
