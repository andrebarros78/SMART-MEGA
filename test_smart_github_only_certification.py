"""Security regression: certification must accept only a bound GitHub-run identity."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from smart_github_certify import execution_provenance
from smart_product_certification import code_fingerprint, regression_source_binding, sha256_file


def _github_env(monkeypatch, commit="a" * 40, run="123"):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "andrebarros78/SMART-MEGA")
    monkeypatch.setenv("GITHUB_SHA", commit)
    monkeypatch.setenv("GITHUB_RUN_ID", run)


def test_external_certifiers_cannot_reclaim_production_authority(tmp_path, monkeypatch):
    _github_env(monkeypatch)
    for external in ("LMCP_LINUX_VPS", "FEDERATED_PC"):
        with pytest.raises(PermissionError, match="retired|GitHub"):
            execution_provenance(
                tmp_path, "a" * 40, str(uuid4()), "wmcp-cloud-01", executor_kind=external
            )
    with pytest.raises(PermissionError, match="retired|GitHub"):
        execution_provenance(tmp_path, "a" * 40, "123", "PC-ESCOLA")


@pytest.mark.parametrize("field,value", [
    ("GITHUB_ACTIONS", "false"),
    ("GITHUB_REPOSITORY", "andrebarros78/OTHER"),
    ("GITHUB_SHA", "b" * 40),
    ("GITHUB_RUN_ID", "456"),
])
def test_github_certifier_requires_all_real_run_bindings(tmp_path, monkeypatch, field, value):
    _github_env(monkeypatch)
    monkeypatch.setenv(field, value)
    with pytest.raises(PermissionError, match="GitHub"):
        execution_provenance(tmp_path, "a" * 40, "123")


def test_github_certifier_binds_exact_commit_and_run(tmp_path, monkeypatch):
    _github_env(monkeypatch)
    assert execution_provenance(tmp_path, "a" * 40, "123") == {
        "kind": "GITHUB_ACTIONS", "run_id": "123"
    }


def _repo(root: Path):
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    source = root / "smart_example.py"
    source.write_text("print('tested')\n", encoding="utf-8")
    subprocess.run(["git", "add", "smart_example.py"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                    "commit", "-qm", "source"], cwd=root, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                         capture_output=True, text=True).stdout.strip()
    junit = root / "SMART_AUDIT_JUNIT_CURRENT.xml"
    junit.write_text('<testsuite tests="1" failures="0" errors="0"><testcase name="x"/></testsuite>', encoding="utf-8")
    return sha, junit, code_fingerprint(root)


@pytest.mark.parametrize("kind", ["LMCP_LINUX_VPS", "FEDERATED_PC", None, "GITHUB_ACTIONS"])
def test_binding_rejects_legacy_or_unattributed_execution(tmp_path, kind):
    sha, junit, fingerprint = _repo(tmp_path)
    if kind == "GITHUB_ACTIONS":
        exec_meta = {"kind": kind, "run_id": "123"}
        ci_run = "123"
    elif kind is None:
        exec_meta = None
        ci_run = "123"
    else:
        exec_meta = {"kind": kind, "execution_id": str(uuid4()),
                     "provider": "LMCP", "hostname": "wmcp-cloud-01"}
        ci_run = None
    authority = {
        "certified_source_commit": sha,
        "certified_ci_run_id": ci_run,
        "certified_execution": exec_meta,
        "certified_source_code_fingerprint_sha256": fingerprint["sha256"],
        "certified_regression_junit_sha256": sha256_file(junit)
    }
    (tmp_path / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority), encoding="utf-8")
    status = regression_source_binding(tmp_path, junit, fingerprint)["status"]
    assert status == ("PASS" if kind == "GITHUB_ACTIONS" else "FAIL")
