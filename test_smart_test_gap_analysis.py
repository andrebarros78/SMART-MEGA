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
