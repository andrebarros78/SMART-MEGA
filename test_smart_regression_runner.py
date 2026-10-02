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
    proof_path = tmp_path / runner.CURRENT_PROOF
    assert proof_path.is_file()
    proof = __import__("json").loads(proof_path.read_text(encoding="utf-8"))
    expected_proof = runner._regression_proof(tmp_path, current, evidence.junit_summary(current), result["code_fingerprint"])
    assert proof == expected_proof
    assert result["current_proof_sha256"] == proof["sha256"]


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
    assert not (tmp_path / runner.CURRENT_PROOF).exists()


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


def test_pytest_runtime_utilities_are_not_collected():
    root = Path(__file__).resolve().parent
    config = (root / "pytest.ini").read_text(encoding="utf-8-sig")
    line = next(line for line in config.splitlines() if line.strip().startswith("norecursedirs"))
    excluded = set(line.split("=", 1)[1].split())
    assert "runtime" in excluded
    risky = [p.name for p in (root / "runtime").glob("*.py") if p.name.startswith("test_") or p.name.endswith("_test.py")]
    assert all("runtime" in excluded for _ in risky)


def _write_canonical_authority(root: Path, legacy: Path) -> None:
    (root / runner.CANONICAL_AUTHORITY).write_text(
        __import__("json").dumps({
            "canonical_root": str(root.resolve()),
            "legacy_alias": str(legacy),
            "legacy_alias_present": False,
            "legacy_alias_type": "REMOVED",
            "canonical_state": "CANONICAL_ONLY",
        }),
        encoding="utf-8",
    )


def test_runner_rejects_present_legacy_alias_before_regression(tmp_path, monkeypatch):
    current = tmp_path / runner.CURRENT
    current.write_text("stable", encoding="utf-8")
    legacy = tmp_path / "legacy"; legacy.mkdir()
    _write_canonical_authority(tmp_path, legacy)
    called = {"value": False}
    def fake_run(*args, **kwargs):
        called["value"] = True
        return _Completed(0)
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    result = runner.run_regression(tmp_path)
    assert result["status"] == "FAIL"
    assert result["reason"] == "CANONICAL_ENVIRONMENT_INVALID_BEFORE_REGRESSION"
    assert result["promoted"] is False
    assert called["value"] is False


def test_runner_rejects_legacy_alias_recreation_during_regression(tmp_path, monkeypatch):
    current = tmp_path / runner.CURRENT
    current.write_text("stable", encoding="utf-8")
    legacy = tmp_path / "legacy"
    _write_canonical_authority(tmp_path, legacy)
    before = evidence.sha256_file(current)
    def fake_run(command, cwd, check, env):
        _write_junit(tmp_path / runner.CANDIDATE, tests=23)
        legacy.mkdir()
        return _Completed(0)
    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    result = runner.run_regression(tmp_path)
    assert result["status"] == "FAIL"
    assert result["reason"] == "CANONICAL_ENVIRONMENT_CHANGED_DURING_REGRESSION"
    assert result["promoted"] is False
    assert result["canonical_environment_before"]["legacy_alias_exists"] is False
    assert result["canonical_environment_after"]["legacy_alias_exists"] is True
    assert evidence.sha256_file(current) == before
