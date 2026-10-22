"""Security regression: only externally governed GitHub-canonical evidence is admissible."""
import json
import subprocess
from pathlib import Path
from uuid import uuid4
import pytest
from smart_github_certify import execution_provenance
from smart_product_certification import code_fingerprint, regression_source_binding, sha256_file


def _repo(root):
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    source = root / "smart_example.py"
    source.write_text("print('tested')\n", encoding="utf-8")
    subprocess.run(["git", "add", "smart_example.py"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
                    "commit", "-qm", "source"], cwd=root, check=True)
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True,
                         capture_output=True, text=True).stdout.strip()
    junit = root / "SMART_AUDIT_JUNIT_CURRENT.xml"
    junit.write_text('<testsuite tests="1" failures="0" errors="0"><testcase name="x"/></testsuite>',
                     encoding="utf-8")
    return sha, junit, code_fingerprint(root)


@pytest.mark.parametrize("kind", ["LMCP_LINUX_VPS", "FEDERATED_PC", "GITHUB_ACTIONS", "UNKNOWN"])
def test_legacy_certifiers_cannot_reclaim_production_authority(tmp_path, monkeypatch, kind):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    with pytest.raises(PermissionError, match="retired|GitHub"):
        execution_provenance(tmp_path, "a" * 40, str(uuid4()), "wmcp-cloud-01", executor_kind=kind)


@pytest.mark.parametrize("field,value", [
    ("GITHUB_ACTIONS", "true"),
    ("GITHUB_EVENT_NAME", "workflow_dispatch"),
])
def test_github_action_environment_denied(tmp_path, monkeypatch, field, value):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.setenv(field, value)
    with pytest.raises(PermissionError, match="GitHub Actions"):
        execution_provenance(tmp_path, "a" * 40, str(uuid4()), "x",
                             executor_kind="EXTERNAL_GOVERNED_EXECUTOR")


@pytest.mark.parametrize("kind", ["LMCP_LINUX_VPS", "FEDERATED_PC", None, "GITHUB_ACTIONS"])
def test_binding_rejects_all_legacy_or_unattributed_execution(tmp_path, kind):
    sha, junit, fingerprint = _repo(tmp_path)
    exec_meta = ({"kind": kind, "run_id": "123"}
                 if kind == "GITHUB_ACTIONS" else
                 None if kind is None else
                 {"kind": kind, "execution_id": str(uuid4()), "hostname": "wmcp-cloud-01"})
    authority = {
        "certified_source_commit": sha,
        "certified_ci_run_id": "123",
        "certified_execution": exec_meta,
        "certified_source_code_fingerprint_sha256": fingerprint["sha256"],
        "certified_regression_junit_sha256": sha256_file(junit)
    }
    (tmp_path / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority), encoding="utf-8")
    report = regression_source_binding(tmp_path, junit, fingerprint)
    assert report["status"] == "FAIL"
    assert report["checks"]["execution_recorded"] is False
