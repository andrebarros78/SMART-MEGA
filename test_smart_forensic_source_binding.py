from pathlib import Path
import hashlib
import json
import socket
import subprocess
import uuid

import pytest

import smart_product_certification as certification
import smart_regression_runner as runner


@pytest.mark.parametrize("fingerprint", [certification.code_fingerprint, runner.code_fingerprint])
@pytest.mark.parametrize("relative", ["conftest.py", "tests/test_scientific_contract.py"])
def test_test_harness_bytes_are_part_of_source_evidence(tmp_path: Path, fingerprint, relative: str) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("VALUE = 1\n", encoding="utf-8")
    before = fingerprint(tmp_path)
    path.write_text("VALUE = 2\n", encoding="utf-8")
    assert fingerprint(tmp_path)["sha256"] != before["sha256"]


def test_nested_test_names_remain_distinct_in_certification(tmp_path: Path) -> None:
    for relative in ("tests/a/test_contract.py", "tests/b/test_contract.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        path.write_text("pass\n", encoding="utf-8")
    rows = certification.code_fingerprint(tmp_path)["files"]
    assert {row["path"] for row in rows} == {"tests/a/test_contract.py", "tests/b/test_contract.py"}


def test_git_binding_accepts_nested_tests_and_rejects_their_drift(tmp_path: Path) -> None:
    files = ("smart_example.py", "conftest.py", "tests/test_causal.py")
    for relative in files:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("VALUE = 1\n", encoding="utf-8")

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True,
        ).stdout.strip()

    git("init", "-q")
    git("add", "--", *files)
    git("-c", "user.name=Test", "-c", "user.email=test@example.org", "commit", "-qm", "fixture")
    source = git("rev-parse", "HEAD")
    junit = tmp_path / "junit.xml"
    junit.write_text('<testsuite tests="1" failures="0" errors="0"><testcase name="a"/></testsuite>', encoding="utf-8")
    fingerprint = certification.code_fingerprint(tmp_path)
    execution_id = str(uuid.uuid4())
    authority = {
        "certified_source_commit": source,
        "certified_ci_run_id": execution_id,
        "certified_execution": {
            "kind": "EXTERNAL_GOVERNED_EXECUTOR", "execution_id": execution_id,
            "source_commit": source, "hostname": socket.gethostname(),
            "origin": "https://github.com/andrebarros78/SMART-MEGA.git",
        },
        "certified_source_code_fingerprint_sha256": fingerprint["sha256"],
        "certified_regression_junit_sha256": hashlib.sha256(junit.read_bytes()).hexdigest(),
    }
    (tmp_path / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority), encoding="utf-8")
    assert certification.regression_source_binding(tmp_path, junit, fingerprint)["status"] == "PASS"
    (tmp_path / "tests/test_causal.py").write_text("VALUE = 2\n", encoding="utf-8")
    after = certification.code_fingerprint(tmp_path)
    result = certification.regression_source_binding(tmp_path, junit, after)
    assert result["status"] == "FAIL"
    assert result["checks"]["source_files_match_tested_commit"] is False
