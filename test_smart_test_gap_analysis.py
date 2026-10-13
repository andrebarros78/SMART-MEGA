"""Adversarial proof that engineering-only test gaps were actually measured."""
from __future__ import annotations

from copy import deepcopy
import json
import shutil
from pathlib import Path

import pytest

import smart_regression_runner as regression
from smart_test_gap_analysis import SOURCE_FILES, TEST_FILES, _hash, verify_test_gap

ROOT = Path(__file__).resolve().parent
PROOF = ROOT / 'SMART_TEST_GAP_EVIDENCE_20261012.json'


def _snapshot(tmp_path: Path):
    evidence = json.loads(PROOF.read_text(encoding='utf-8'))
    for name in (*SOURCE_FILES, *TEST_FILES):
        shutil.copyfile(ROOT / name, tmp_path / name)
    return evidence


def test_coverage_evidence_is_real_and_consumed_by_regression_gate():
    original = json.loads(PROOF.read_text(encoding='utf-8'))
    consumed = verify_test_gap(original, ROOT)
    assert consumed['status'] == 'NATIVE_EXECUTION_CONSUMED_VERIFIED'
    assert consumed['capability'] == 'test-gap-analysis'
    assert consumed['consumer'] == 'smart_test_gap_analysis.verify_test_gap'
    assert consumed['tests_passed'] >= 2
    assert consumed['tested_modules'] == 5
    assert consumed['observed_missing_lines'] > 0
    assert consumed['predictive_weight_authorized'] is False
    gate = regression.consume_test_gap_evidence(ROOT)
    assert gate['status'] == 'PASS'
    assert gate['execution_receipt_sha256'] == consumed['execution_sha256']
    assert gate['observed_missing_lines'] == consumed['observed_missing_lines']
    assert gate['full_test_coverage_proven'] is False
    assert gate['external_skill_executed'] is False


def test_gap_evidence_rejects_forged_totals_and_self_hash(tmp_path):
    original = _snapshot(tmp_path)
    forged = deepcopy(original)
    forged['total_missing_lines'] += 1
    with pytest.raises(ValueError, match='SHA mismatch'):
        verify_test_gap(forged, tmp_path)
    forged['execution_sha256'] = _hash({k:v for k,v in forged.items() if k != 'execution_sha256'})
    with pytest.raises(ValueError, match='uncovered-line total invalid'):
        verify_test_gap(forged, tmp_path)


def test_gap_evidence_rejects_changed_source_and_suppressed_gaps(tmp_path):
    original = _snapshot(tmp_path)
    p = tmp_path / SOURCE_FILES[0]
    p.write_bytes(p.read_bytes()+b'\n# prospective tampering\n')
    with pytest.raises(ValueError, match='different source snapshot'):
        verify_test_gap(original, tmp_path)
    p.write_bytes((ROOT / SOURCE_FILES[0]).read_bytes())
    forged = deepcopy(original)
    first = SOURCE_FILES[0]
    forged['source_module_coverage'][first]['missing_lines'] = []
    forged['execution_sha256'] = _hash({k:v for k,v in forged.items() if k != 'execution_sha256'})
    with pytest.raises(ValueError, match='measured coverage invalid'):
        verify_test_gap(forged, tmp_path)


def test_gap_consumer_requires_receipt_and_rejects_untraced_scope(tmp_path):
    with pytest.raises(ValueError, match='execution evidence absent'):
        regression.consume_test_gap_evidence(tmp_path)
    original = _snapshot(tmp_path)
    original['source_module_coverage'].pop(SOURCE_FILES[0])
    original['execution_sha256'] = _hash({k:v for k,v in original.items() if k != 'execution_sha256'})
    with pytest.raises(ValueError, match='coverage incomplete'):
        verify_test_gap(original, tmp_path)


def test_critical_consumer_gate_must_exercise_more_than_prior_five_test_sample():
    """A larger selection is not itself a pass: critical paths must be reached."""
    report = json.loads(PROOF.read_text(encoding='utf-8'))
    verified = verify_test_gap(report, ROOT)
    assert verified['tests_passed'] >= 17
    rows = report['source_module_coverage']
    # Frozen results from the immediately preceding 5-test sample, *not*
    # product-wide coverage thresholds or prospective performance assertions.
    baseline_covered = {'smart_operator.py': 130,
                        'smart_post_result_report.py': 43}
    for module, count in baseline_covered.items():
        assert rows[module]['imported_by_selected_tests'] is True
        assert rows[module]['covered_lines'] > count, (
            f'new tests failed to exercise additional {module} statements'
        )
    assert report['total_missing_lines'] < 1613
    assert report['prospective_superiority_proven'] is False
    assert report['predictive_weight_authorized'] is False


@pytest.mark.parametrize("junit", [0, 1, 4, True, "17", -1])
def test_gap_consumer_rejects_impossible_junit_count_even_if_rehashed(tmp_path, junit):
    proof = _snapshot(tmp_path)
    proof['junit_tests'] = junit
    proof['execution_sha256'] = _hash({k: v for k, v in proof.items() if k != 'execution_sha256'})
    with pytest.raises(ValueError, match='execution did not pass'):
        verify_test_gap(proof, tmp_path)


@pytest.mark.parametrize("update", [
    {'imported_by_selected_tests': False},
    {'imported_by_selected_tests': 'yes'},
    {'missing_branches': None},
    {'missing_branches': [[-1, 'invalid']]},
    {'missing_branches': [[1, 2], [1, 2]]},
    {'missing_branches': [[2, 3], [1, 2]]},
])
def test_gap_consumer_rejects_inconsistent_trace_even_if_rehashed(tmp_path, update):
    proof = _snapshot(tmp_path)
    proof['source_module_coverage']['smart_operator.py'].update(update)
    proof['execution_sha256'] = _hash({k: v for k, v in proof.items() if k != 'execution_sha256'})
    with pytest.raises(ValueError, match='(traced-module|untraced module|missing branch)'):
        verify_test_gap(proof, tmp_path)


@pytest.mark.parametrize("claim", [
    {"observability_scope": "PRODUCT_WIDE_TEST_COVERAGE"},
    {"native_function_executed": "external-skill"},
    {"prospective_superiority_proven": True},
    {"predictive_weight_authorized": True},
])
def test_gap_consumer_rejects_privilege_or_scope_inflation_even_if_rehashed(tmp_path, claim):
    proof = _snapshot(tmp_path)
    proof.update(claim)
    proof['execution_sha256'] = _hash({k: v for k, v in proof.items() if k != 'execution_sha256'})
    with pytest.raises(ValueError, match='authority or consumer invalid'):
        verify_test_gap(proof, tmp_path)
