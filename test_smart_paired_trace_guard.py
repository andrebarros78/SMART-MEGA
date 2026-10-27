"""Chronological holdout proof must bind predictions to each pre-draw snapshot.

A holdout aggregate alone is NOT a paired-trace proof and never licenses model
promotion. Tests cover source lineage, outcomes, ranking, time and exact p.
"""
from __future__ import annotations
from copy import deepcopy
from smart_paired_trace_guard import validate_trace, paired_sign_test

def fixture():
    draws = {3073: [2, 3, 20, 25, 39, 57], 3074: [7, 10, 14, 27, 36, 55]}
    rows = [
      {"contest": 3073, "prediction_cutoff": 3072, "baseline_top6": [2, 3, 11, 12, 30, 40],
       "candidate_top6": [1, 3, 11, 12, 30, 40], "baseline_hits": 2, "candidate_hits": 1},
      {"contest": 3074, "prediction_cutoff": 3073, "baseline_top6": [1, 7, 12, 40, 50, 59],
       "candidate_top6": [7, 10, 12, 40, 50, 59], "baseline_hits": 1, "candidate_hits": 2},
    ]
    doc = {
      "schema": "SMART_PAIRED_HOLDOUT_TRACE_1",
      "target_contest": 3075, "cutoff_contest": 3074,
      "holdout_start": 3073, "holdout_end": 3074,
      "baseline_engine_git_blob": "a" * 40, "candidate_engine_git_blob": "b" * 40,
      "snapshot_sha256": "f" * 64,
      "future_result_used": False, "promotion_authorized": False,
      "rows": rows,
      "summary": {"baseline_hits": 3, "candidate_hits": 3,
                  "candidate_wins": 1, "baseline_wins": 1, "ties": 0,
                  "one_sided_p": 0.75},
    }
    return draws, doc

def test_valid_chronological_trace_replays_exactly_and_still_blocks_promotion():
    actual, doc = fixture()
    independent = [([2, 3, 11, 12, 30, 40], [1, 3, 11, 12, 30, 40]),
                   ([1, 7, 12, 40, 50, 59], [7, 10, 12, 40, 50, 59])]
    report=validate_trace(doc,actual,replay_predictions=independent)
    assert report["status"] == "PASS"
    assert report["per_draw_prediction_replayed"] is True
    assert report["paired"]["one_sided_p"] == 0.75
    assert report["promotion_authorized"] is False

def test_aggregate_alone_does_not_prove_algorithm_predictions():
    actual, doc=fixture()
    report=validate_trace(doc,actual)
    assert report["status"] == "INCOMPLETE_REPLAY"
    assert report["per_draw_prediction_replayed"] is False
    assert report["promotion_authorized"] is False

def test_forged_prediction_detected_even_if_hit_count_stays_same():
    actual, doc=fixture()
    doc["rows"][0]["baseline_top6"] = [2, 3, 10, 12, 30, 40]
    original = [([2, 3, 11, 12, 30, 40], [1, 3, 11, 12, 30, 40]),
                ([1, 7, 12, 40, 50, 59], [7, 10, 12, 40, 50, 59])]
    report=validate_trace(doc,actual,replay_predictions=original)
    assert report["status"] == "FAIL"
    assert "PREDICTION_REPLAY_MISMATCH" in report["errors"]

def test_wrong_overlap_and_paired_statistics_rejected():
    actual,doc=fixture()
    doc["rows"][1]["candidate_hits"]=6
    report=validate_trace(doc,actual,replay_predictions=[
        (r["baseline_top6"],r["candidate_top6"]) for r in doc["rows"]])
    assert report["status"] == "FAIL"
    assert "HITS_MISMATCH" in report["errors"]

def test_temporal_leakage_or_future_draw_rejected():
    actual,doc=fixture()
    doc["rows"][0]["prediction_cutoff"]=3073
    report=validate_trace(doc,actual)
    assert "PIT_CUTOFF_INVALID" in report["errors"]
    assert report["status"] == "FAIL"
    assert report["promotion_authorized"] is False

def test_false_significance_claim_rejected():
    actual,doc=fixture()
    doc["summary"]["one_sided_p"]=0.000001
    report=validate_trace(doc,actual)
    assert "PAIRED_COUNTS_MISMATCH" in report["errors"]

def test_missing_contest_or_duplicate_denied():
    actual,doc=fixture()
    doc["rows"][1]["contest"]=3073
    report=validate_trace(doc,actual)
    assert "HOLDOUT_SEQUENCE_INVALID" in report["errors"]

def test_exact_sign_test_against_known_small_cases():
    assert paired_sign_test(5,2) == 0.2265625
    assert paired_sign_test(0,0) == 1.0
    assert paired_sign_test(1,1) == 0.75
