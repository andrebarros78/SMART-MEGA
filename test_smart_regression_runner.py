from pathlib import Path
import xml.etree.ElementTree as ET

import smart_regression_evidence as evidence
import smart_regression_runner as runner


def _write_junit(path: Path, *, tests: int, failures: int = 0, errors: int = 0) -> None:
    root = ET.Element("testsuites", tests=str(tests), failures=str(failures), errors=str(errors), skipped="0", time="0.1")
    ET.SubElement(root, "testsuite", name="suite", tests=str(tests), failures=str(failures), errors=str(errors), skipped="0", time="0.1")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


class _Completed:
    def __init__(self, returncode: int):
        self.returncode = returncode


def test_runner_promotes_only_green_candidate(tmp_path, monkeypatch):
    current = tmp_path / runner.CURRENT
    current.write_text("stable", encoding="utf-8")
    before = evidence.sha256_file(current)

    def fake_run(command, cwd, check, env):
        assert runner.CANDIDATE in command[-1]
        assert runner.CURRENT not in " ".join(command)
        assert Path(cwd) == tmp_path
        assert "-E" in command
        assert env["PYTHONPATH"] == ""
        assert env["PYTHONNOUSERSITE"] == "1"
        _write_junit(tmp_path / runner.CANDIDATE, tests=23)
        assert evidence.sha256_file(current) == before
        return _Completed(0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    result = runner.run_regression(tmp_path)
    assert result["status"] == "PASS"
    assert result["promoted"] is True
    assert result["candidate"]["tests"] == 23
    assert result["code_fingerprint_stable"] is True
    assert result["isolated_python_environment"] is True
    assert result["exclusive_runner_lock"] is True
    assert evidence.sha256_file(current) == evidence.sha256_file(tmp_path / runner.CANDIDATE)


def test_runner_failed_candidate_preserves_current(tmp_path, monkeypatch):
    current = tmp_path / runner.CURRENT
    current.write_text("stable", encoding="utf-8")
    before = evidence.sha256_file(current)

    def fake_run(command, cwd, check, env):
        _write_junit(tmp_path / runner.CANDIDATE, tests=23, failures=1)
        return _Completed(1)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    result = runner.run_regression(tmp_path)
    assert result["status"] == "FAIL"
    assert result["reason"] == "TEST_FAILURE"
    assert result["promoted"] is False
    assert result["current_preserved"] is True
    assert evidence.sha256_file(current) == before


def test_runner_missing_candidate_preserves_current(tmp_path, monkeypatch):
    current = tmp_path / runner.CURRENT
    current.write_text("stable", encoding="utf-8")
    before = evidence.sha256_file(current)
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: _Completed(2))
    result = runner.run_regression(tmp_path)
    assert result["status"] == "FAIL"
    assert result["reason"] == "CANDIDATE_MISSING"
    assert result["candidate_present"] is False
    assert result["current_preserved"] is True
    assert evidence.sha256_file(current) == before


def test_runner_rejects_code_mutation_during_green_regression(tmp_path, monkeypatch):
    current = tmp_path / runner.CURRENT
    current.write_text("stable", encoding="utf-8")
    (tmp_path / "smart_alpha.py").write_text("VALUE = 1\n", encoding="utf-8")
    before = evidence.sha256_file(current)

    def fake_run(command, cwd, check, env):
        _write_junit(tmp_path / runner.CANDIDATE, tests=23)
        (tmp_path / "smart_alpha.py").write_text("VALUE = 2\n", encoding="utf-8")
        return _Completed(0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    result = runner.run_regression(tmp_path)
    assert result["status"] == "FAIL"
    assert result["reason"] == "CODE_CHANGED_DURING_REGRESSION"
    assert result["promoted"] is False
    assert result["current_preserved"] is True
    assert evidence.sha256_file(current) == before


def test_candidate_and_current_are_distinct_contracts():
    assert runner.CANDIDATE != runner.CURRENT
    assert runner.CANDIDATE.endswith("_CANDIDATE.xml")
    assert runner.CURRENT.endswith("_CURRENT.xml")
def test_runner_rejects_concurrent_second_instance(tmp_path):
    with runner._RegressionLock(tmp_path):
        result = runner.run_regression(tmp_path)
    assert result["status"] == "FAIL"
    assert result["reason"] == "REGRESSION_ALREADY_RUNNING"
    assert result["promoted"] is False