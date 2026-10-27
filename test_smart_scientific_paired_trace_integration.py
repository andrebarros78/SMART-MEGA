"""Regression tests: integrate the 224-draw paired PIT trace into the SHADOW gate.

The historical F11/F12 certificates remain immutable. A signed artifact alone
is not an independent prediction replay. No test creates production authority.
"""
from copy import deepcopy
import json
from pathlib import Path

from smart_scientific_shadow_review import review

ROOT = Path(__file__).resolve().parent
TRACE_FILE = ROOT / "evidence/3075/SMART_3075_PAIRED_HOLDOUT_TRACE_224.json"


def test_gate_recognizes_git_pinned_224_draw_trace_without_fake_replay():
    result = review(ROOT)
    trace = result["paired_trace"]
    assert trace["artifact_git_blob_verified"] is True
    assert trace["chronological_rows"] == 224
    assert trace["holdout"]["baseline_hits"] == 128
    assert trace["holdout"]["candidate_hits"] == 131
    assert trace["holdout"]["candidate_wins"] == 5
    assert trace["holdout"]["baseline_wins"] == 2
    assert trace["holdout"]["ties"] == 217
    assert trace["per_draw_prediction_replayed"] is False
    assert "NO_VERIFIED_PER_DRAW_PAIRED_TRACE" in result["blockers"]
    assert result["promotion_authorized"] is False


def test_cannot_call_archived_trace_independent_without_sources():
    result = review(ROOT)
    assert result["status"] == "PASS_SHADOW_ONLY"
    assert result["paired_trace"]["status"] == "PINNED_REPLAY_REQUIRED"
    assert result["paired_trace"]["per_draw_prediction_replayed"] is False


def test_tampered_holdout_row_fails_closed_even_if_signed_aggregate_exists():
    doc = json.loads(TRACE_FILE.read_text(encoding="utf-8-sig"))
    doc["rows"][0]["baseline_hits"] = 6
    result = review(ROOT, trace_override=doc)
    assert result["status"] == "INVALID_EVIDENCE"
    assert "PAIRED_TRACE_ARTIFACT_NOT_PINNED" in result["blockers"]
    assert result["promotion_authorized"] is False


def test_corrupted_trace_summary_is_rejected():
    doc = json.loads(TRACE_FILE.read_text(encoding="utf-8-sig"))
    doc["summary"]["one_sided_p"] = 1e-12
    result = review(ROOT, trace_override=doc)
    assert result["status"] == "INVALID_EVIDENCE"
    assert "PAIRED_TRACE_SUMMARY_INVALID" in result["blockers"]


def test_future_contamination_or_wrong_source_is_invalid_not_eligible():
    doc = json.loads(TRACE_FILE.read_text(encoding="utf-8-sig"))
    doc["future_result_used"] = True
    result = review(ROOT, trace_override=doc)
    assert result["status"] == "INVALID_EVIDENCE"
    assert "PAIRED_TRACE_TEMPORAL_OR_SOURCE_INVALID" in result["blockers"]


def test_real_replay_path_rejects_missing_snapshot_without_promotion(tmp_path):
    result = review(ROOT, frozen_snapshot=tmp_path / "missing.xlsx",
                    baseline_engine=tmp_path / "missing_engine.py")
    assert result["status"] == "INVALID_EVIDENCE"
    assert "INDEPENDENT_PAIRED_REPLAY_FAILED" in result["blockers"]
    assert "NO_VERIFIED_PER_DRAW_PAIRED_TRACE" in result["blockers"]
    assert result["promotion_authorized"] is False


def test_even_valid_independent_replay_does_not_override_scientific_blocks(monkeypatch, tmp_path):
    import smart_scientific_shadow_review as sci
    original = json.loads(TRACE_FILE.read_text(encoding="utf-8-sig"))
    monkeypatch.setattr(sci, "produce_independent_trace", lambda root, snapshot, baseline: deepcopy(original))
    result = sci.review(ROOT, frozen_snapshot=tmp_path / "fixture.xlsx",
                        baseline_engine=tmp_path / "fixture.py")
    assert result["status"] == "PASS_SHADOW_ONLY"
    assert result["paired_trace"]["per_draw_prediction_replayed"] is True
    assert "NO_VERIFIED_PER_DRAW_PAIRED_TRACE" not in result["blockers"]
    assert "PAIRED_GAIN_NOT_SIGNIFICANT" in result["blockers"]
    assert "GLOBAL_NONREGRESSION_FAILED" in result["blockers"]
    assert "F12_SOURCE_SUCCESSION_NOT_CERTIFIED" in result["blockers"]
    assert "PROSPECTIVE_SUPERIORITY_NOT_PROVEN" in result["blockers"]
    assert result["promotion_authorized"] is False
