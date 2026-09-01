from __future__ import annotations

import copy
from pathlib import Path

import pytest

import smart_evidence_only_promotion as p15
import smart_global_integrity as gi
from smart_promotion_gate import assess_promotion_records


def eligible() -> dict:
    out = assess_promotion_records([{'challenger_hits': 6, 'champion_hits': 0} for _ in range(20)], e_value=20.0)
    out['candidate_fingerprint'] = 'a' * 64
    out['lineage_pair_count'] = out['n']
    return out


def integrity() -> dict:
    return {
        'status': 'PASS', 'proof_file': 'SMART_GLOBAL_INTEGRITY_PROOF.json',
        'proof_file_sha256': 'b' * 64, 'critical_source_hashes_current': True,
        'coverage_current': True, 'red_team_current': True,
        'independent_audit_current': True, 'full_regression_current': True,
        'material_deficiencies': [],
    }


def test_p13_integer_and_internal_consistency_are_strict():
    for field in ('n', 'challenger_hits', 'champion_hits', 'advantage_hits', 'cumulative_regret'):
        bad = eligible(); bad[field] = float(bad[field])
        with pytest.raises(ValueError, match='integer evidence'):
            p15._validated_p13(bad)
    bad = eligible(); bad['e_value'] = -0.1
    with pytest.raises(ValueError, match='non-negative'):
        p15._validated_p13(bad)
    bad = eligible(); bad['challenger_hits'] = -1
    with pytest.raises(ValueError, match='non-negative'):
        p15._validated_p13(bad)
    bad = eligible(); bad['advantage_hits'] += 1
    with pytest.raises(ValueError, match='advantage_hits'):
        p15._validated_p13(bad)
    bad = eligible(); bad['cumulative_regret'] += 1
    with pytest.raises(ValueError, match='cumulative_regret'):
        p15._validated_p13(bad)
    bad = eligible(); bad['lineage_pair_count'] = 20.0
    with pytest.raises(ValueError, match='lineage pair count'):
        p15._validated_p13(bad)


def test_global_integrity_hash_requires_hexadecimal():
    status = integrity(); status['proof_file_sha256'] = 'z' * 64
    blockers, summary = p15._global_integrity_evidence(status)
    assert 'global_integrity_proof_hash_invalid' in blockers
    assert summary['verified'] is False


def test_gate_target_does_not_coerce_strings_or_booleans():
    from test_smart_evidence_only_promotion import _gate
    for bad_target in ('3052', True, 3052.0):
        gate = _gate(); gate['target_contest'] = bad_target
        blockers, _ = p15._gate_evidence(gate)
        assert 'implementation_gate_target_invalid' in blockers


def test_malformed_junit_is_governed_value_error(tmp_path: Path):
    path = tmp_path / 'bad.xml'; path.write_text('<testsuites><broken>', encoding='utf-8')
    with pytest.raises(ValueError, match='malformed'):
        gi.junit_summary(path)
