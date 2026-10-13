from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from smart_f12_scientific_successor import (
    PREDICTIVE_FILE, evaluate, reconstruct_predecessor, _matches_expected_code,
)
from smart_f11_predictive_nonregression import BASELINE_SOURCE_SHA256

ROOT = Path(__file__).resolve().parent


def _bounded_selector_predecessor():
    """Remove ONLY the operator-request exclusion extension, preserving F11."""
    current = (ROOT / "smart_primary_card_selector.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    substitutions = (
        ("def _try_select(scores,ranking,cfg,pool_size,excluded_cards=frozenset()):",
         "def _try_select(scores,ranking,cfg,pool_size):"),
        ("        evaluated+=1\n        if tuple(sorted(combo)) in excluded_cards: continue\n        c=_counts(combo)",
         "        evaluated+=1; c=_counts(combo)"),
        ("config:PrimaryCardSelectorConfig|None=None,*,excluded_cards=None)->dict[str,Any]:",
         "config:PrimaryCardSelectorConfig|None=None)->dict[str,Any]:"),
        ('    excluded=set()\n    for card in (excluded_cards or ()):\n        if not isinstance(card,(list,tuple)) or len(card)!=6 or any(isinstance(n,bool) or not isinstance(n,Integral) or not 1<=int(n)<=60 for n in card) or len(set(card))!=6:\n            raise ValueError("excluded operator card must contain six distinct integers 1..60")\n        excluded.add(tuple(sorted(int(n) for n in card)))\n', ""),
        ("_try_select(scores,ranking,cfg,pool,excluded); attempts.append",
         "_try_select(scores,ranking,cfg,pool); attempts.append"),
        ('    audit.update(meta)\n    if excluded:\n        audit["operator_request_excluded_prior_cards"]=len(excluded)\n        audit["operator_request_distinct_six_number_card"]=True\n    audit["sha256"]=sha256_json(audit); return audit',
         '    audit.update(meta); audit["sha256"]=sha256_json(audit); return audit'),
    )
    for before, after in substitutions:
        assert current.count(before) == 1, before
        current = current.replace(before, after, 1)
    return current.encode("utf-8")


def test_f12_historical_gate_rejects_unapproved_selector_change_and_new_proof_is_scoped():
    # F12 was approved for ONE causal trace repair. A later operator-request
    # feature cannot be silently reclassified as unchanged F12 production code.
    import hashlib
    actual = evaluate(ROOT)
    assert actual["status"] == "FAIL"
    assert {k for k, ok in actual["checks"].items() if not ok} == {
        "all_other_production_sources_unchanged"
    }
    assert actual["checks"]["f11_historical_evidence_integrity"] is True
    assert actual["historical_comparison"]["p10"]["total_delta"] == 0
    assert actual["historical_comparison"]["p06"]["approved_for_predictive_promotion"] is False
    assert actual["prospective_advantage_proven"] is False
    assert actual["six_of_six_proven"] is False

    proof = json.loads((ROOT / "release_evidence/PR40_F11_SELECTOR_COMPATIBILITY_20261013.json").read_text())
    unsigned = {k: v for k, v in proof.items() if k != "sha256"}
    assert proof["sha256"] == hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    original = _bounded_selector_predecessor()
    assert _matches_expected_code(original, BASELINE_SOURCE_SHA256["smart_primary_card_selector.py"])
    assert hashlib.sha256((ROOT / "smart_primary_card_selector.py").read_bytes()).hexdigest() == proof["current_selector_sha256"]
    assert proof["f11_original_selector_sha256"] == BASELINE_SOURCE_SHA256["smart_primary_card_selector.py"]
    assert proof["explicit_added_guard_hunks"] == 6
    assert proof["f12_historical_same_source_gate_currently_valid"] is False
    assert proof["f11_historical_scientific_evidence_valid"] is True
    assert proof["operator_card_generated_in_production"] is False
    assert proof["six_hits_predictive_superiority_proven"] is False
    assert len(proof["synthetic_cases"]) == 4


def test_f12_immutable_archival_approval_not_rewritten_after_new_operator_extension():
    import hashlib
    stored = json.loads((ROOT / "SMART_F12_SCIENTIFIC_SUCCESSOR.json").read_text(encoding="utf-8"))
    signature = stored["sha256"]
    assert signature == hashlib.sha256(json.dumps(
        {k: v for k, v in stored.items() if k != "sha256"},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    assert stored["status"] == "PASS"
    assert stored["checks"]["all_other_production_sources_unchanged"] is True
    assert stored["prospective_advantage_proven"] is False
    # The archived PASS must not be passed off as current approval.
    assert evaluate(ROOT)["status"] == "FAIL"


def test_f12_reconstructed_approved_pipeline_is_bitwise_f11_identity():
    source = (ROOT / PREDICTIVE_FILE).read_bytes()
    pre = reconstruct_predecessor(source)
    assert pre is not None
    assert _matches_expected_code(pre, BASELINE_SOURCE_SHA256[PREDICTIVE_FILE])


def test_f12_altered_agent_parameters_rejected_even_if_authority_declared():
    source = (ROOT / PREDICTIVE_FILE).read_bytes()
    tampered = source.replace(b"expected_value != effective_value", b"expected_value == effective_value", 1)
    assert tampered != source
    assert reconstruct_predecessor(tampered) is None or not _matches_expected_code(
        reconstruct_predecessor(tampered), BASELINE_SOURCE_SHA256[PREDICTIVE_FILE]
    )


def test_f12_rejects_unrelated_predictive_code_change():
    source = (ROOT / PREDICTIVE_FILE).read_bytes()
    tampered = source.replace(b"MAXIMIZE_SIX_HIT_SINGLE_CARD", b"MAXIMIZE_SIX_HIT_SINGLE_BIAS", 1)
    assert tampered != source
    pre = reconstruct_predecessor(tampered)
    assert pre is None or not _matches_expected_code(pre, BASELINE_SOURCE_SHA256[PREDICTIVE_FILE])
