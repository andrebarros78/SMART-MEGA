"""F11/F12-preserving integration tests for the 224-draw paired trace.

An intact Git blob is not proof of independent PIT replay. Only external
verified snapshot + independent frozen baseline re-execution may clear the
'NO_VERIFIED_PER_DRAW_PAIRED_TRACE' blocker. Nothing can authorize production.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import smart_scientific_shadow_review as gate

ROOT = Path(__file__).resolve().parent


def test_unassisted_shadow_review_recognizes_pinned_trace_without_claiming_replay():
    result = gate.review(ROOT)
    assert result["status"] == "PASS_SHADOW_ONLY"
    assert result["holdout"]["trace_artifact_integrity_verified"] is True
    assert result["holdout"]["per_draw_trace_verified"] is False
    assert result["holdout"]["per_draw_prediction_replayed"] is False
    assert "NO_VERIFIED_PER_DRAW_PAIRED_TRACE" in result["blockers"]
    assert result["promotion_authorized"] is False
    assert result["historical_f11_reproduced"] is True
    assert result["archived_f12_certificate_intact"] is True


def test_independent_replay_removes_only_trace_blocker(monkeypatch, tmp_path):
    # Fixed external inputs are mandatory; mocked producer isolates gate wiring
    # here. A separate real replay tests the SHA-pinned engines and data.
    replayed = gate.read_paired_trace(ROOT)
    called = []

    def independent(snapshot, baseline, root):
        called.append((snapshot, baseline, root))
        return deepcopy(replayed)

    monkeypatch.setattr(gate, "produce_independent_trace", independent)
    result = gate.review(
        ROOT,
        frozen_snapshot=tmp_path / "snapshot.xlsx",
        baseline_engine=tmp_path / "baseline.py",
    )
    assert len(called) == 1
    assert result["status"] == "PASS_SHADOW_ONLY"
    assert result["holdout"]["trace_artifact_integrity_verified"] is True
    assert result["holdout"]["per_draw_trace_verified"] is True
    assert result["holdout"]["per_draw_prediction_replayed"] is True
    assert "NO_VERIFIED_PER_DRAW_PAIRED_TRACE" not in result["blockers"]
    assert "PAIRED_GAIN_NOT_SIGNIFICANT" in result["blockers"]
    assert "GLOBAL_NONREGRESSION_FAILED" in result["blockers"]
    assert "PROSPECTIVE_SUPERIORITY_NOT_PROVEN" in result["blockers"]
    assert "F12_SOURCE_SUCCESSION_NOT_CERTIFIED" in result["blockers"]
    assert result["promotion_authorized"] is False


def test_replay_inconsistent_with_published_predictions_is_rejected(monkeypatch, tmp_path):
    data = gate.read_paired_trace(ROOT)
    data["rows"][0]["candidate_top6"] = [1, 2, 3, 4, 5, 6]
    monkeypatch.setattr(gate, "produce_independent_trace", lambda *a: data)
    result = gate.review(ROOT, frozen_snapshot=tmp_path / "snapshot.xlsx",
                         baseline_engine=tmp_path / "baseline.py")
    assert result["status"] == "INVALID_EVIDENCE"
    assert "TRACE_REPLAY_MISMATCH" in result["blockers"]
    assert result["holdout"]["per_draw_trace_verified"] is False
    assert result["promotion_authorized"] is False


def test_wrong_or_missing_independent_replay_sources_fail_closed(monkeypatch, tmp_path):
    def bad_source(*_):
        raise ValueError("mismatched snapshot sha256")

    monkeypatch.setattr(gate, "produce_independent_trace", bad_source)
    result = gate.review(ROOT, frozen_snapshot=tmp_path / "wrong.xlsx",
                         baseline_engine=tmp_path / "baseline.py")
    assert result["status"] == "INVALID_EVIDENCE"
    assert "TRACE_REPLAY_FAILED" in result["blockers"]
    assert "NO_VERIFIED_PER_DRAW_PAIRED_TRACE" in result["blockers"]


def test_partial_replay_source_request_is_not_silently_ignored(tmp_path):
    result = gate.review(ROOT, frozen_snapshot=tmp_path / "snapshot.xlsx")
    assert result["status"] == "INVALID_EVIDENCE"
    assert "TRACE_REPLAY_INPUTS_INCOMPLETE" in result["blockers"]
    assert result["promotion_authorized"] is False


def test_tampered_published_trace_hash_invalidates_shadow(monkeypatch):
    monkeypatch.setattr(gate, "PINNED_PAIRED_TRACE_SHA256", "0" * 64)
    result = gate.review(ROOT)
    assert result["status"] == "INVALID_EVIDENCE"
    assert "PAIRED_TRACE_HASH_MISMATCH" in result["blockers"]
    assert result["holdout"]["trace_artifact_integrity_verified"] is False


def test_fabricated_trace_aggregate_does_not_claim_integrity(monkeypatch):
    genuine = gate.read_paired_trace(ROOT)
    forged = deepcopy(genuine)
    forged["summary"]["candidate_hits"] += 10
    monkeypatch.setattr(gate, "read_paired_trace", lambda root: forged)
    result = gate.review(ROOT)
    assert result["status"] == "INVALID_EVIDENCE"
    assert "PAIRED_TRACE_AGGREGATE_MISMATCH" in result["blockers"]
    assert result["promotion_authorized"] is False
