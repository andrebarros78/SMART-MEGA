"""Negative regressions for retired federated certification authorities."""
import json
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
    subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                    "commit", "-qm", "tested"], cwd=root, check=True)
    source = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                            check=True, capture_output=True, text=True).stdout.strip()
    junit = root / "SMART_AUDIT_JUNIT_CURRENT.xml"
    junit.write_text("<testsuite tests='1' failures='0' errors='0'><testcase name='x'/></testsuite>", encoding="utf-8")
    return source, junit, code_fingerprint(root)


def _write_authority(root: Path, source: str, junit: Path, fingerprint: dict,
                     execution: dict | None, run_id: str | None) -> None:
    authority = {
        "certified_source_commit": source,
        "certified_ci_run_id": run_id,
        "certified_execution": execution,
        "certified_source_code_fingerprint_sha256": fingerprint["sha256"],
        "certified_regression_junit_sha256": sha256_file(junit)
    }
    (root / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority), encoding="utf-8")


@pytest.mark.parametrize("kind", ["FEDERATED_PC", "LMCP_LINUX_VPS"])
def test_legacy_executor_cannot_mint_certification(tmp_path, monkeypatch, kind):
    source, _, _ = _repo(tmp_path)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "andrebarros78/SMART-MEGA")
    monkeypatch.setenv("GITHUB_SHA", source)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    with pytest.raises(PermissionError, match="retired"):
        execution_provenance(tmp_path, source, str(uuid4()), "wmcp-cloud-01", executor_kind=kind)


@pytest.mark.parametrize("kind", ["FEDERATED_PC", "LMCP_LINUX_VPS", "UNKNOWN", None])
def test_legacy_or_missing_execution_does_not_bind_regression(tmp_path, kind):
    source, junit, fp = _repo(tmp_path)
    execution = None if kind is None else {
        "kind": kind, "execution_id": str(uuid4()), "hostname": "wmcp-cloud-01",
        "provider": "LMCP",
    }
    _write_authority(tmp_path, source, junit, fp, execution, "123" if kind is None else None)
    report = regression_source_binding(tmp_path, junit, fp)
    assert report["status"] == "FAIL"
    assert report["checks"]["execution_recorded"] is False


@pytest.mark.parametrize("execution,ci_run", [
    ({"kind": "FEDERATED_PC", "execution_id": "123", "hostname": "PC-ESCOLA"}, None),
    ({"kind": "LMCP_LINUX_VPS", "execution_id": "00000000-0000-0000-0000-000000000001",
      "provider": "LMCP", "hostname": "wmcp-cloud-01"}, None),
    ({"kind": "GITHUB_ACTIONS", "run_id": "456"}, "123"),
    ({"kind": "GITHUB_ACTIONS", "run_id": "123"}, None),
])
def test_binding_rejects_mismatched_or_external_run(tmp_path, execution, ci_run):
    source, junit, fp = _repo(tmp_path)
    _write_authority(tmp_path, source, junit, fp, execution, ci_run)
    assert regression_source_binding(tmp_path, junit, fp)["status"] == "FAIL"


def test_github_provenance_requires_real_repository_commit_and_run(tmp_path, monkeypatch):
    source, _, _ = _repo(tmp_path)
    for key in ("GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(PermissionError):
        execution_provenance(tmp_path, source, "123")
    for key, value in {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "andrebarros78/SMART-MEGA",
        "GITHUB_SHA": source, "GITHUB_RUN_ID": "123",
    }.items():
        monkeypatch.setenv(key, value)
    assert execution_provenance(tmp_path, source, "123") == {
        "kind": "GITHUB_ACTIONS", "run_id": "123"
    }
    with pytest.raises(ValueError):
        execution_provenance(tmp_path, source, str(uuid4()))


def test_github_regression_binding_requires_exact_file_hash_and_code_fingerprint(tmp_path):
    source, junit, fp = _repo(tmp_path)
    _write_authority(tmp_path, source, junit, fp, {"kind": "GITHUB_ACTIONS", "run_id": "123"}, "123")
    assert regression_source_binding(tmp_path, junit, fp)["status"] == "PASS"
    (tmp_path / "smart_example.py").write_text("print('changed')\n", encoding="utf-8")
    current = code_fingerprint(tmp_path)
    assert regression_source_binding(tmp_path, junit, current)["status"] == "FAIL"
