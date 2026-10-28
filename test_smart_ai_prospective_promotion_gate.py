"""Fail-closed: retrospective significance cannot authorize operational promotion."""
import json
import pytest
import smart_ai_fine_tuning as tuning
from test_smart_ai_fine_tuning_statistical_gate import _candidate, _trace

def _significant():
    baseline_trace, challenger_trace = _trace([0]*100, [1]*75 + [0]*25)
    base = _candidate("baseline", 290, 205, 0, baseline_trace)
    challenger = _candidate("candidate", 300, 215, 75, challenger_trace)
    return [base, challenger]

def test_significant_retrospective_holdout_never_grants_operational_promotion():
    results = _significant()
    outcome = tuning.adjudicate_selected(results, tuning.select_without_holdout(results))
    assert outcome["holdout_statistical_evidence"]["verified"] is True
    assert outcome["holdout_statistical_evidence"]["prospective_superiority_proven"] is False
    assert outcome["retrospective_eligible"] is True
    assert outcome["promotion_authorized"] is False
    assert outcome["effective_candidate_id"] == "baseline"

def test_forged_report_cannot_mint_promoted_authority():
    rows = _significant()
    report = {
        "schema": tuning.SCHEMA, "status": "PASS", "target_contest": 2951,
        "cutoff_contest": 2950, "data_sha256": "a"*64,
        "sha256": "b"*64, "results": rows,
        "adjudication": {"effective_candidate_id": "candidate", "promotion_authorized": True}
    }
    with pytest.raises(ValueError, match="prospective|promotion"):
        tuning.build_authority(report)

def test_self_hashed_legacy_promoted_authority_is_rejected(tmp_path):
    authority = {
        "schema": tuning.AUTHORITY_SCHEMA, "status": "AUTHORIZED",
        "target_contest": 2951, "cutoff_contest": 2950,
        "data_sha256": "a"*64, "fine_tuning_report_sha256": "b"*64,
        "fine_tuning_report_file_sha256": None,
        "effective_candidate": {"candidate_id":"candidate", "eta":0.5,
          "redundancy_threshold":0.85, "meta_strength":0.06},
        "promotion_authorized": True, "causal_partitioning": True,
        "holdout_used_for_selection": False, "future_result_used": False
    }
    authority["sha256"] = tuning.sha256_json(authority)
    path = tmp_path/"legacy-promoted-authority.json"
    path.write_text(json.dumps(authority), encoding="utf-8")
    with pytest.raises(ValueError, match="prospective|promotion"):
        tuning.load_authority(path, target_contest=2951, data_sha256="a"*64)

def test_self_hashed_baseline_parameter_tampering_rejected(tmp_path):
    baseline = tuning.candidate_space()[0]
    authority = {
        'schema': tuning.AUTHORITY_SCHEMA,
        'status': 'BASELINE_RETAINED',
        'target_contest': 3075,
        'cutoff_contest': 3074,
        'data_sha256': 'a'*64,
        'fine_tuning_report_sha256': 'b'*64,
        'fine_tuning_report_file_sha256': None,
        'effective_candidate': {
            'candidate_id': 'baseline',
            'eta': 1.25,
            'redundancy_threshold': baseline.redundancy_threshold,
            'meta_strength': baseline.meta_strength,
        },
        'promotion_authorized': False,
        'causal_partitioning': True,
        'holdout_used_for_selection': False,
        'future_result_used': False,
    }
    authority['sha256'] = tuning.sha256_json(authority)
    path = tmp_path / 'tampered-baseline-authority.json'
    path.write_text(json.dumps(authority), encoding='utf-8')
    with pytest.raises(ValueError, match='baseline|parameter'):
        tuning.load_authority(path, target_contest=3075, data_sha256='a'*64)


def test_self_hashed_false_causal_partitioning_rejected(tmp_path):
    baseline = tuning.candidate_space()[0]
    authority = {
        'schema': tuning.AUTHORITY_SCHEMA,
        'status': 'BASELINE_RETAINED',
        'target_contest': 3075,
        'cutoff_contest': 3074,
        'data_sha256': 'a'*64,
        'fine_tuning_report_sha256': 'b'*64,
        'fine_tuning_report_file_sha256': None,
        'effective_candidate': {
            'candidate_id': 'baseline',
            'eta': baseline.eta,
            'redundancy_threshold': baseline.redundancy_threshold,
            'meta_strength': baseline.meta_strength,
        },
        'promotion_authorized': False,
        'causal_partitioning': False,
        'holdout_used_for_selection': False,
        'future_result_used': False,
    }
    authority['sha256'] = tuning.sha256_json(authority)
    path = tmp_path / 'tampered-causality-authority.json'
    path.write_text(json.dumps(authority), encoding='utf-8')
    with pytest.raises(ValueError, match='causal'):
        tuning.load_authority(path, target_contest=3075, data_sha256='a'*64)
