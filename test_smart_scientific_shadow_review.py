"""TDD for an independent candidate-only scientific review.

The immutable F11/F12 historical certifications must stay untouched, and a
retrospective repair without significant paired gain cannot enter production.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from smart_scientific_shadow_review import review, _paired_sign_test


ROOT = Path(__file__).resolve().parent


def test_original_scientific_certifications_are_not_silently_rewritten():
    report = review(ROOT)
    assert report["status"] == "PASS_SHADOW_ONLY"
    assert report["historical_f11_reproduced"] is True
    assert report["archived_f12_certificate_intact"] is True
    assert report["live_f12_status"] == "FAIL"
    assert report["promotion_authorized"] is False
    assert report["prospective_advantage_proven"] is False
    assert "F12_SOURCE_SUCCESSION_NOT_CERTIFIED" in report["blockers"]


def test_real_paired_evidence_cannot_be_called_predictively_superior():
    report = review(ROOT)
    assert report["holdout"]["candidate_wins"] == 5
    assert report["holdout"]["baseline_wins"] == 2
    assert report["holdout"]["ties"] == 217
    assert abs(report["holdout"]["one_sided_p"] - 0.2265625) < 1e-12
    assert report["comparisons"]["global_gain"] == -6
    assert "PAIRED_GAIN_NOT_SIGNIFICANT" in report["blockers"]
    assert "GLOBAL_NONREGRESSION_FAILED" in report["blockers"]
    assert "PROSPECTIVE_SUPERIORITY_NOT_PROVEN" in report["blockers"]


def test_sign_test_is_exact_and_conservative_for_ties():
    assert _paired_sign_test(5, 2) == 0.2265625
    assert _paired_sign_test(0, 0) == 1.0
    assert _paired_sign_test(30, 0) < 0.01


def test_reject_future_result_used_in_retrospective_evidence():
    from smart_scientific_shadow_review import read_evidence
    changed = deepcopy(read_evidence(ROOT))
    changed["future_result_3075_used_in_experiment"] = True
    report = review(ROOT, evidence_override=changed)
    assert report["status"] == "INVALID_EVIDENCE"
    assert "TEMPORAL_LEAKAGE_OR_BAD_CUTOFF" in report["blockers"]
    assert report["promotion_authorized"] is False


def test_reject_falsified_p_value():
    from smart_scientific_shadow_review import read_evidence
    changed = deepcopy(read_evidence(ROOT))
    changed["paired_holdout"]["one_sided_sign_test_p"] = 0.000001
    report = review(ROOT, evidence_override=changed)
    assert report["status"] == "INVALID_EVIDENCE"
    assert "PAIRED_EVIDENCE_INCONSISTENT" in report["blockers"]


def test_reject_discordance_mismatch():
    from smart_scientific_shadow_review import read_evidence
    changed = deepcopy(read_evidence(ROOT))
    changed["paired_holdout"]["ties"] = 216
    report = review(ROOT, evidence_override=changed)
    assert report["status"] == "INVALID_EVIDENCE"
    assert "PAIRED_EVIDENCE_INCONSISTENT" in report["blockers"]


def test_reject_false_prospective_promotion_claim():
    from smart_scientific_shadow_review import read_evidence
    changed = deepcopy(read_evidence(ROOT))
    changed["predictive_advantage_proven"] = True
    changed["promotion_authorized"] = True
    report = review(ROOT, evidence_override=changed)
    assert report["status"] == "INVALID_EVIDENCE"
    assert report["promotion_authorized"] is False


def test_even_large_hypothetical_holdout_gain_does_not_override_prospective_gate():
    from smart_scientific_shadow_review import read_evidence
    changed = deepcopy(read_evidence(ROOT))
    changed["paired_holdout"].update({
        "candidate_wins": 30, "baseline_wins": 0, "ties": 194,
        "one_sided_sign_test_p": _paired_sign_test(30, 0),
    })
    changed["candidate"]["holdout"]["hits"] += 30
    changed["candidate"]["global"]["hits"] += 30
    report = review(ROOT, evidence_override=changed)
    assert report["promotion_authorized"] is False
    assert report["prospective_advantage_proven"] is False
    assert "PROSPECTIVE_SUPERIORITY_NOT_PROVEN" in report["blockers"]


def test_reject_unexpected_live_f12_safety_check_failure(monkeypatch):
    """Never turn an unrelated F12 regression into a 'safe shadow' certificate."""
    import smart_scientific_shadow_review as gate
    original = gate.evaluate_f12

    def compromised(root):
        result = original(root)
        result["checks"]["p10_no_regression_vs_reference"] = False
        result["status"] = "FAIL"
        return result

    monkeypatch.setattr(gate, "evaluate_f12", compromised)
    result = gate.review(ROOT)
    assert result["status"] == "INVALID_EVIDENCE"
    assert "UNEXPECTED_F12_GUARD_FAILURE" in result["blockers"]


def test_reject_unreviewed_additional_predictor_source_difference(monkeypatch):
    """Scope is pinned; changing a sixth F11 source needs a new review."""
    import smart_scientific_shadow_review as gate
    original = gate.evaluate_f12

    def compromised(root):
        result = original(root)
        result["sources"]["smart_primary_card_selector.py"]["approved_f11_source_preserved"] = False
        result["checks"]["all_other_predictive_sources_preserved_after_exact_guard_reversal"] = False
        result["status"] = "FAIL"
        return result

    monkeypatch.setattr(gate, "evaluate_f12", compromised)
    result = gate.review(ROOT)
    assert result["status"] == "INVALID_EVIDENCE"
    assert "UNREVIEWED_PREDICTIVE_SOURCE_DIFF" in result["blockers"]
