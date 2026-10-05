"""Federated regression provenance cannot impersonate GitHub Actions."""
import json
import socket
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from smart_github_certify import execution_provenance
from smart_product_certification import code_fingerprint, regression_source_binding, sha256_file


def _repo(root: Path) -> tuple[str, Path, dict]:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/andrebarros78/SMART-MEGA.git"], cwd=root, check=True)
    (root / "smart_example.py").write_text("print('tested')\n", encoding="utf-8")
    subprocess.run(["git", "add", "smart_example.py"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com",
                    "commit", "-qm", "tested"], cwd=root, check=True)
    source = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    junit = root / "SMART_AUDIT_JUNIT_CURRENT.xml"
    junit.write_text("<testsuites><testsuite tests='1' failures='0' errors='0'><testcase name='x'/></testsuite></testsuites>", encoding="utf-8")
    return source, junit, code_fingerprint(root)


def test_federated_provenance_and_source_binding(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    source, junit, fingerprint = _repo(tmp_path)
    execution = execution_provenance(tmp_path, source, str(uuid4()), socket.gethostname())
    assert execution["kind"] == "FEDERATED_PC"
    assert "run_id" not in execution
    authority = {"certified_source_commit": source, "certified_ci_run_id": None,
                 "certified_execution": execution,
                 "certified_source_code_fingerprint_sha256": fingerprint["sha256"],
                 "certified_regression_junit_sha256": sha256_file(junit)}
    (tmp_path / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority), encoding="utf-8")
    binding = regression_source_binding(tmp_path, junit, fingerprint)
    assert binding["status"] == "PASS"
    assert binding["execution"] == execution
    assert binding["ci_run_id"] is None
    (tmp_path / "smart_example.py").write_text("print('untested')\n", encoding="utf-8")
    assert regression_source_binding(tmp_path, junit, code_fingerprint(tmp_path))["status"] == "FAIL"


@pytest.mark.parametrize("fault", ["host", "uuid", "origin"])
def test_federated_provenance_rejects_wrong_identity(tmp_path, fault):
    source, _, _ = _repo(tmp_path)
    host, execution_id = socket.gethostname(), str(uuid4())
    if fault == "host":
        host += "-wrong"
    elif fault == "uuid":
        execution_id = "123"
    else:
        subprocess.run(["git", "remote", "set-url", "origin", "https://github.com/andrebarros78/OTHER.git"], cwd=tmp_path, check=True)
    with pytest.raises((ValueError, PermissionError)):
        execution_provenance(tmp_path, source, execution_id, host)


@pytest.mark.parametrize("execution,ci_run", [
    ({"kind": "FEDERATED_PC", "execution_id": "123", "hostname": "PC-ESCOLA"}, None),
    ({"kind": "FEDERATED_PC", "execution_id": "00000000-0000-0000-0000-000000000001", "hostname": " PC-ESCOLA "}, None),
    ({"kind": "FEDERATED_PC", "execution_id": "00000000-0000-0000-0000-000000000001", "hostname": "PC-ESCOLA"}, "123"),
    ({"kind": "UNKNOWN"}, "123"),
    ({"kind": "GITHUB_ACTIONS", "run_id": "456"}, "123"),
])
def test_binding_rejects_invalid_or_conflicting_executor(tmp_path, execution, ci_run):
    source, junit, fingerprint = _repo(tmp_path)
    authority = {"certified_source_commit": source, "certified_ci_run_id": ci_run,
                 "certified_execution": execution,
                 "certified_source_code_fingerprint_sha256": fingerprint["sha256"],
                 "certified_regression_junit_sha256": sha256_file(junit)}
    (tmp_path / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority), encoding="utf-8")
    assert regression_source_binding(tmp_path, junit, fingerprint)["status"] == "FAIL"


def test_github_provenance_requires_real_repository_and_numeric_run(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    with pytest.raises(PermissionError):
        execution_provenance(tmp_path, "a" * 40, "123")
    monkeypatch.setenv("GITHUB_REPOSITORY", "andrebarros78/SMART-MEGA")
    assert execution_provenance(tmp_path, "a" * 40, "123") == {"kind": "GITHUB_ACTIONS", "run_id": "123"}
    with pytest.raises(ValueError):
        execution_provenance(tmp_path, "a" * 40, str(uuid4()))
