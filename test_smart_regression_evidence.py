from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

import smart_regression_evidence as re


def _write_junit(path: Path, *, tests: int, failures: int = 0, errors: int = 0) -> None:
    root = ET.Element("testsuites", tests=str(tests), failures=str(failures), errors=str(errors), skipped="0", time="0.1")
    suite = ET.SubElement(root, "testsuite", name="suite", tests=str(tests), failures=str(failures), errors=str(errors), skipped="0", time="0.1")
    for index in range(tests):
        case = ET.SubElement(suite, "testcase", name=f"case_{index}")
        if index < failures:
            ET.SubElement(case, "failure")
        elif index < failures + errors:
            ET.SubElement(case, "error")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def test_promote_green_candidate_atomically(tmp_path: Path):
    candidate = tmp_path / "candidate.xml"
    current = tmp_path / "current.xml"
    current.write_text("old", encoding="utf-8")
    _write_junit(candidate, tests=17)
    result = re.promote(candidate, current)
    assert result["status"] == "PASS"
    assert result["tests"] == 17
    assert result["sha256"] == re.sha256_file(candidate) == re.sha256_file(current)
    assert candidate.exists()


def test_rejects_failed_candidate_and_preserves_current(tmp_path: Path):
    candidate = tmp_path / "candidate.xml"
    current = tmp_path / "current.xml"
    current.write_text("stable", encoding="utf-8")
    before = re.sha256_file(current)
    _write_junit(candidate, tests=17, failures=1)
    with pytest.raises(ValueError, match="not green"):
        re.promote(candidate, current)
    assert re.sha256_file(current) == before


def test_rejects_empty_candidate(tmp_path: Path):
    candidate = tmp_path / "candidate.xml"
    current = tmp_path / "current.xml"
    _write_junit(candidate, tests=0)
    with pytest.raises(ValueError, match="not green"):
        re.promote(candidate, current)
    assert not current.exists()
