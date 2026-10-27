"""Candidate shadow reviewer validates the pinned 224-row trace without fake replay."""
from copy import deepcopy
from pathlib import Path
import json

from smart_scientific_shadow_review import (
    audit_trace_manifest,
    read_evidence,
    review,
)

ROOT = Path(__file__).resolve().parent
TRACE = ROOT / "evidence/3075/SMART_3075_PAIRED_HOLDOUT_TRACE_224.json"


def test_real_trace_manifest_is_consistent_but_not_independently_replayed():
    current = review(ROOT)
    assert current["status"] == "PASS_SHADOW_ONLY"
    assert current["holdout"]["per_draw_trace_manifest_consistent"] is True
    assert current["holdout"]["per_draw_trace_verified"] is False
    assert current["holdout"]["per_draw_trace_manifest_n"] == 224
    assert "NO_VERIFIED_PER_DRAW_PAIRED_TRACE" in current["blockers"]
    assert current["promotion_authorized"] is False


def test_trace_manifest_corrupted_cutoff_rejected_even_with_same_summary():
    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    trace["rows"][0]["prediction_cutoff"] = 2851
    errors, audit = audit_trace_manifest(trace, read_evidence(ROOT))
    assert "PAIRED_TRACE_MANIFEST_INCONSISTENT" in errors
    assert audit["per_draw_trace_manifest_consistent"] is False


def test_trace_manifest_corrupted_hits_and_summary_rejected():
    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    trace["rows"][0]["candidate_hits"] += 1
    errors, audit = audit_trace_manifest(trace, read_evidence(ROOT))
    assert "PAIRED_TRACE_MANIFEST_INCONSISTENT" in errors
    assert audit["per_draw_trace_manifest_consistent"] is False


def test_trace_manifest_missing_row_rejected():
    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    trace["rows"].pop()
    errors, audit = audit_trace_manifest(trace, read_evidence(ROOT))
    assert "PAIRED_TRACE_MANIFEST_INCONSISTENT" in errors
    assert audit["per_draw_trace_manifest_consistent"] is False


def test_trace_manifest_worktree_substitution_rejected_even_with_clean_git_index(monkeypatch):
    import smart_scientific_shadow_review as gate
    original = Path.read_bytes
    broken = json.loads(TRACE.read_text(encoding="utf-8"))
    broken["rows"][0]["baseline_top6"] = [1, 2, 3, 4, 5, 6]
    fake_bytes = json.dumps(broken).encode("utf-8")

    def tampered_read(path):
        if Path(path).resolve() == TRACE.resolve():
            return fake_bytes
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", tampered_read)
    result = gate.review(ROOT)
    assert result["status"] == "INVALID_EVIDENCE"
    assert "PAIRED_TRACE_NOT_GIT_PINNED" in result["blockers"]
    assert result["promotion_authorized"] is False


def test_trace_manifest_falsified_p_value_rejected():
    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    trace["summary"]["one_sided_p"] = 0.00001
    errors, audit = audit_trace_manifest(trace, read_evidence(ROOT))
    assert "PAIRED_TRACE_MANIFEST_INCONSISTENT" in errors
    assert audit["per_draw_trace_verified"] is False


def test_trace_manifest_missing_original_snapshot_is_explicit():
    result = review(ROOT)
    assert result["holdout"]["per_draw_trace_manifest_consistent"] is True
    assert result["holdout"]["independent_prediction_replay_performed"] is False
    assert result["holdout"]["independent_official_results_verified"] is False
    assert result["promotion_authorized"] is False

