from pathlib import Path

import pytest

from smart_regression_evidence import junit_summary, promote


@pytest.mark.parametrize("xml", [
    '<testsuite tests="1500" failures="0" errors="0" skipped="0"/>',
    '<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="a"><failure>failed</failure></testcase></testsuite>',
    '<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="a"><error>broken</error></testcase></testsuite>',
    '<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="a"><skipped/></testcase></testsuite>',
    '<testsuites tests="1" failures="0" errors="0"><testsuite tests="1" failures="1" errors="0"><testcase name="a"><failure/></testcase></testsuite></testsuites>',
    '<testsuite tests="-1" failures="0" errors="0" skipped="0"><testcase name="a"/></testsuite>',
])
def test_declared_green_cannot_hide_missing_cases_or_bad_outcomes(tmp_path: Path, xml: str) -> None:
    candidate = tmp_path / "candidate.xml"
    current = tmp_path / "current.xml"
    candidate.write_text(xml, encoding="utf-8")
    current.write_bytes(b"preserved-authority")
    assert junit_summary(candidate)["status"] == "FAIL"
    with pytest.raises(ValueError, match="not green"):
        promote(candidate, current)
    assert current.read_bytes() == b"preserved-authority"


def test_nested_suites_are_counted_from_actual_cases(tmp_path: Path) -> None:
    path = tmp_path / "nested.xml"
    path.write_text(
        '<testsuites tests="2" failures="0" errors="0" skipped="0">'
        '<testsuite tests="2" failures="0" errors="0" skipped="0">'
        '<testcase name="outer"/><testsuite tests="1" failures="0" errors="0" skipped="0">'
        '<testcase name="inner"/></testsuite></testsuite></testsuites>', encoding="utf-8",
    )
    result = junit_summary(path)
    assert result["status"] == "PASS"
    assert result["tests"] == 2


@pytest.mark.parametrize("xml", [
    '<testsuite tests="1500" failures="0" errors="0" skipped="0"/>',
    '<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="a"><failure/></testcase></testsuite>',
])
def test_global_integrity_uses_the_same_verified_outcomes(tmp_path: Path, xml: str) -> None:
    from smart_global_integrity import junit_summary as global_summary

    path = tmp_path / "forged.xml"
    path.write_text(xml, encoding="utf-8")
    with pytest.raises(ValueError, match="not clean"):
        global_summary(path)
