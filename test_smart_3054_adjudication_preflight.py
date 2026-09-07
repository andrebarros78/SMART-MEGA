from pathlib import Path
import json

import pytest
import pandas as pd

import smart_3054_adjudication_preflight as preflight
from smart_current_epoch_contract import resolve as resolve_current_epoch

ROOT = Path(__file__).resolve().parent
FREEZE_3054 = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"


def _historical_preflight():
    doc = json.loads((ROOT / "SMART_3054_ADJUDICATION_PREFLIGHT.json").read_text(encoding="utf-8-sig"))
    assert doc["target_contest"] == 3054
    assert doc["cutoff_contest"] == 3053
    assert doc["active_freeze_sha256"] == FREEZE_3054
    return doc


def test_3054_historical_preflight_proves_pre_result_readiness_without_reopening_authority():
    doc = _historical_preflight()
    assert doc["readiness_status"] == "PASS"
    assert doc["sequence_before_result"]["valid"] is True
    assert doc["sequence_before_result"]["adjudicated"] is False
    assert doc["sequence_before_result"]["derived_event_count"] == 0
    assert doc["official_result_ingested"] is False
    assert doc["canonical_adjudication_executed"] is False
    assert doc["terminal_6of6_proven"] is False
    assert doc["checks"]["not_yet_adjudicated"] is True

    current = resolve_current_epoch(ROOT)
    if current["target_contest"] == 3054:
        paths = preflight._current_paths(ROOT)
        assert paths["adjudication_already_executed"] is True
        assert paths["adjudication_authority_mode"] == "PARALLEL_LOCKED_PROSPECTIVE_ADJUDICATED"
        assert paths["adjudication_evidence"]["freeze_sha256"] == FREEZE_3054
        assert paths["adjudication_evidence"]["actual_numbers"] == [8, 17, 24, 43, 47, 58]
        with pytest.raises(ValueError, match="already adjudicated"):
            preflight.build_preflight(ROOT)
    else:
        assert current["target_contest"] >= 3055
        with pytest.raises(ValueError, match="active epoch is not the 3054/3053"):
            preflight.build_preflight(ROOT)


def test_3054_reset_ready_without_preserved_lock_fails_closed(monkeypatch):
    current = resolve_current_epoch(ROOT)
    fake = dict(current)
    fake.update({
        "status": "RESET_READY",
        "target_contest": 3054,
        "cutoff_contest": 3053,
        "result_used": False,
        "parallel_locked_experiment": None,
    })
    monkeypatch.setattr(preflight, "resolve_current_epoch", lambda root: fake)
    with pytest.raises(ValueError, match="preserved locked prospective authority"):
        preflight._current_paths(ROOT)


def test_3054_probability_ledger_was_bound_to_frozen_authority():
    doc = _historical_preflight()
    probability = doc["probability_ledger"]
    assert probability["main_freeze_file_sha256"] == FREEZE_3054
    assert probability["candidate_count"] == len(probability["summaries"])
    assert probability["candidate_count"] > 0
    assert probability["all_candidates_have_60_probabilities"] is True
    assert probability["all_probability_sums_equal_six"] is True
    assert all(item["probability_count"] == 60 for item in probability["summaries"])
    assert all(abs(item["probability_sum"] - 6.0) <= 1e-8 for item in probability["summaries"])


def test_3054_historical_sandbox_rehearsal_was_non_mutating():
    doc = _historical_preflight()
    sandbox = doc["sandbox_rehearsal"]
    assert sandbox["adjudication_created"] is True
    assert sandbox["sequence_valid"] is True
    assert sandbox["missing_derived_event_types"] == []
    assert set(sandbox["derived_event_types"]) == preflight.EXPECTED_DERIVED_TYPES
    assert sandbox["duplicate_adjudication_rejected"] is True
    assert "already adjudicated" in sandbox["duplicate_error"]
    assert sandbox["canonical_ledger_used"] is False
    assert doc["canonical_hashes_before"] == doc["canonical_hashes_after"]
    assert doc["checks"]["canonical_artifacts_unchanged_by_sandbox"] is True


def test_3054_historical_result_store_was_cutoff_3053_and_current_store_advanced_only_after_adjudication():
    doc = _historical_preflight()
    store = doc["canonical_result_store"]
    assert store["contest_max"] == 3053
    assert store["target_absent"] is True
    assert store["contiguous_through_cutoff"] is True
    frame = pd.read_excel(ROOT / "Mega-Sena.xlsx")
    contests = pd.to_numeric(frame["Concurso"], errors="raise").astype(int)
    assert int(contests.max()) >= 3054
    assert 3054 in set(contests.tolist())
