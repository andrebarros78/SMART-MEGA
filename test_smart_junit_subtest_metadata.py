"""Subtests-count reconciliation must preserve real test outcomes and reject invented evidence."""
from pathlib import Path

import pytest

from smart_regression_evidence import junit_summary
import smart_regression_evidence as sre


def _sample(tmp_path, *, base=1, subtests=2, reported=3, log_subtests=None,
            failure=False, skipped=False, deselected=0):
    source=tmp_path/'original.xml'
    log=tmp_path/'terminal.log'
    out=tmp_path/'normalized.xml'
    if log_subtests is None:
        log_subtests=subtests
    fragment=('<failure message="actual fail"/>' if failure else
              '<skipped message="actual skip"/>' if skipped else '')
    body=''.join(f'<testcase classname="regression" name="case_{i}"/>' for i in range(base-1))
    body+=f'<testcase classname="regression" name="case_last">{fragment}</testcase>'
    source.write_text(
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<testsuites><testsuite tests="{reported}" errors="0" failures="{int(failure)}" skipped="{int(skipped)}">'
        f'{body}</testsuite></testsuites>',encoding='utf-8')
    log.write_text(f'{base} passed, {deselected} deselected, 0 warnings, {log_subtests} subtests passed in 0.22s\n',
                   encoding='utf-8')
    return source,log,out


def test_pytest_subtest_normalizer_reconciles_only_suite_metadata(tmp_path):
    source,log,out=_sample(tmp_path)
    raw=source.read_bytes()
    assert junit_summary(source)['status']=='FAIL'
    proof=sre.normalize_pytest_subtest_junit(source,log,out)
    assert junit_summary(out)['status']=='PASS'
    assert source.read_bytes()==raw
    assert out.read_bytes()==raw.replace(b'tests="3"',b'tests="1"',1)
    assert proof['serialized_testcases']==1
    assert proof['subtests']==2
    assert proof['reported_total_before']==3
    assert proof['status']=='PASS_METADATA_ONLY'
    assert proof['original_junit_sha256']==junit_summary(source)['sha256']
    assert proof['normalized_junit_sha256']==junit_summary(out)['sha256']


@pytest.mark.parametrize('reported,log_subtests',[(4,2),(3,3),(2,2)])
def test_forged_suite_totals_or_fake_subtest_log_fail_closed(tmp_path,reported,log_subtests):
    source,log,out=_sample(tmp_path,reported=reported,log_subtests=log_subtests)
    with pytest.raises(ValueError):
        sre.normalize_pytest_subtest_junit(source,log,out)
    assert not out.exists()


@pytest.mark.parametrize('failure,skipped',[(True,False),(False,True)])
def test_any_actual_failure_or_skip_rejected(tmp_path,failure,skipped):
    source,log,out=_sample(tmp_path,failure=failure,skipped=skipped)
    with pytest.raises(ValueError):
        sre.normalize_pytest_subtest_junit(source,log,out)
    assert not out.exists()


def test_refuses_to_overwrite_any_original_or_existing_candidate(tmp_path):
    source,log,out=_sample(tmp_path)
    with pytest.raises(ValueError):
        sre.normalize_pytest_subtest_junit(source,log,source)
    out.write_text('DO NOT OVERWRITE',encoding='utf-8')
    with pytest.raises(FileExistsError):
        sre.normalize_pytest_subtest_junit(source,log,out)
    assert out.read_text(encoding='utf-8')=='DO NOT OVERWRITE'


def test_terminal_log_without_verified_subtests_rejected(tmp_path):
    source,log,out=_sample(tmp_path)
    log.write_text('1 passed in 0.22s\n',encoding='utf-8')
    with pytest.raises(ValueError):
        sre.normalize_pytest_subtest_junit(source,log,out)
    assert not out.exists()

def test_normalizer_rejects_deselected_tests_even_when_junit_counts_match(tmp_path):
    source, log, out = _sample(tmp_path, deselected=1)
    with pytest.raises(ValueError, match="deselected"):
        sre.normalize_pytest_subtest_junit(source, log, out)
    assert not out.exists()
