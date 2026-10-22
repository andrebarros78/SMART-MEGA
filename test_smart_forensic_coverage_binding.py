import json
from pathlib import Path

import pytest

import smart_github_certify as certify
import smart_global_integrity as integrity
from smart_source_identity import sha256_source_file


def coverage_fixture(root: Path) -> Path:
    rows = []
    files = {}
    for name in integrity.REQUIRED_GLOBAL_COVERAGE_SOURCES:
        path = root / name
        path.write_text("VALUE = 1\n", encoding="utf-8")
        files[name] = {"source_sha256": sha256_source_file(path), "summary": {"missing_lines": 0, "missing_branches": 0, "covered_lines": 1, "num_statements": 1, "covered_branches": 0, "num_branches": 0}}
        rows.append({"report_file": "coverage.json", "source_key": name})
    (root / "SMART_GLOBAL_INTEGRITY_PROOF.json").write_text(json.dumps({"coverage": rows}), encoding="utf-8")
    report = root / "coverage.json"
    report.write_text(json.dumps({"meta": {"branch_coverage": True}, "files": files}), encoding="utf-8")
    return report


def test_coverage_must_bind_every_measured_source(tmp_path: Path) -> None:
    report = coverage_fixture(tmp_path)
    certify.require_current_coverage_sources(tmp_path)
    data = json.loads(report.read_text())
    del data["files"][integrity.REQUIRED_GLOBAL_COVERAGE_SOURCES[0]]["source_sha256"]
    report.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="source-bound coverage required"):
        certify.require_current_coverage_sources(tmp_path)


def test_changed_code_cannot_reuse_previous_coverage(tmp_path: Path) -> None:
    coverage_fixture(tmp_path)
    (tmp_path / integrity.REQUIRED_GLOBAL_COVERAGE_SOURCES[0]).write_text("VALUE = 2\n")
    with pytest.raises(ValueError, match="source-bound coverage required"):
        certify.require_current_coverage_sources(tmp_path)


@pytest.mark.parametrize("change", ["duplicate", "missing", "escape"])
def test_invalid_coverage_inventory_fails_closed(tmp_path: Path, change: str) -> None:
    coverage_fixture(tmp_path)
    path = tmp_path / "SMART_GLOBAL_INTEGRITY_PROOF.json"
    proof = json.loads(path.read_text())
    if change == "duplicate":
        proof["coverage"].append(proof["coverage"][0])
    elif change == "missing":
        proof["coverage"].pop()
    else:
        proof["coverage"][0]["report_file"] = "../outside.json"
    path.write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="coverage"):
        certify.require_current_coverage_sources(tmp_path)


def test_refresh_rejects_unbound_coverage_before_any_authority_write(tmp_path: Path, monkeypatch) -> None:
    coverage_fixture(tmp_path)
    report = tmp_path / "coverage.json"
    report.write_text('{"files": {}}')
    current = tmp_path / certify.ARTIFACTS[0]
    current.write_bytes(b"preserved-current-junit")
    candidate = tmp_path / "candidate.xml"
    candidate.write_text('<testsuite tests="1" failures="0" errors="0"><testcase name="a"/></testsuite>')
    monkeypatch.setattr(certify, "execution_provenance", lambda *args, **kwargs: {})
    monkeypatch.setattr(certify.subprocess, "run", lambda *args, **kwargs: type("Result", (), {"stdout": "a" * 40})())
    monkeypatch.setattr("smart_linux_ci.baseline_junit_counts", lambda root: {"tests": 1})
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    with pytest.raises(ValueError, match="source-bound coverage required"):
        certify.refresh(tmp_path, candidate, "a" * 40, "unused")
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()} == before

@pytest.mark.parametrize("defect", ["missing_lines", "missing_branches", "counter_mismatch", "branch_disabled"])
def test_refresh_rejects_incomplete_bound_coverage_before_any_authority_write(tmp_path: Path, monkeypatch, defect: str) -> None:
    report = coverage_fixture(tmp_path)
    data = json.loads(report.read_text())
    source = integrity.REQUIRED_GLOBAL_COVERAGE_SOURCES[0]
    if defect == "branch_disabled":
        data["meta"]["branch_coverage"] = False
    elif defect == "counter_mismatch":
        data["files"][source]["summary"]["covered_lines"] = 0
    else:
        data["files"][source]["summary"][defect] = 1
    report.write_text(json.dumps(data))
    current = tmp_path / certify.ARTIFACTS[0]
    current.write_bytes(b"preserved-current-junit")
    candidate = tmp_path / "candidate.xml"
    candidate.write_text('<testsuite tests="1" failures="0" errors="0"><testcase name="a"/></testsuite>')
    monkeypatch.setattr(certify, "execution_provenance", lambda *args, **kwargs: {})
    monkeypatch.setattr(certify.subprocess, "run", lambda *args, **kwargs: type("Result", (), {"stdout": "a" * 40})())
    monkeypatch.setattr("smart_linux_ci.baseline_junit_counts", lambda root: {"tests": 1})
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    with pytest.raises(ValueError, match="coverage"):
        certify.refresh(tmp_path, candidate, "a" * 40, "unused")
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()} == before
