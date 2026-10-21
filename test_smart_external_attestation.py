"""External evidence must be tied to tested GitHub code; Actions remain banned."""
import json
import socket
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from smart_github_certify import execution_provenance
from smart_product_certification import code_fingerprint, regression_source_binding, sha256_file


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()


def source_repo(root):
    git(root, "init", "-q")
    git(root, "remote", "add", "origin", "https://github.com/andrebarros78/SMART-MEGA.git")
    (root / "smart_example.py").write_text("VALUE = 3\n", encoding="utf-8")
    git(root, "add", "smart_example.py")
    git(root, "-c", "user.name=test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", "baseline")
    sha = git(root, "rev-parse", "HEAD")
    junit = root / "SMART_AUDIT_JUNIT_CURRENT.xml"
    junit.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0">'
                     '<testcase name="proof"/></testsuite>', encoding="utf-8")
    return sha, junit, code_fingerprint(root)


def test_external_provenance_binds_exact_head_and_approval(tmp_path, monkeypatch):
    sha, junit, fp = source_repo(tmp_path)
    uid = str(uuid4())
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.setenv("SMART_MEGA_CERTIFICATION_APPROVAL", sha)
    proof = execution_provenance(
        tmp_path, sha, uid, socket.gethostname(),
        executor_kind="EXTERNAL_GOVERNED_EXECUTOR"
    )
    assert proof["kind"] == "EXTERNAL_GOVERNED_EXECUTOR"
    assert proof["execution_id"] == uid
    assert proof["source_commit"] == sha
    assert proof["origin"] == "https://github.com/andrebarros78/SMART-MEGA.git"
    authority = {
        "certified_source_commit": sha,
        "certified_ci_run_id": uid,
        "certified_execution": proof,
        "certified_source_code_fingerprint_sha256": fp["sha256"],
        "certified_regression_junit_sha256": sha256_file(junit),
    }
    (tmp_path / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority))
    assert regression_source_binding(tmp_path, junit, fp)["status"] == "PASS"
    authority["certified_ci_run_id"] = str(uuid4())
    (tmp_path / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority))
    assert regression_source_binding(tmp_path, junit, fp)["status"] == "FAIL"


@pytest.mark.parametrize("variant", [
    "no_approval", "wrong_sha", "wrong_host", "wrong_origin",
    "github_actions", "github_event", "wrong_id", "wrong_kind"
])
def test_external_provenance_fails_closed(tmp_path, monkeypatch, variant):
    sha, _, _ = source_repo(tmp_path)
    uid = str(uuid4())
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.setenv("SMART_MEGA_CERTIFICATION_APPROVAL", sha)
    host = socket.gethostname()
    kind = "EXTERNAL_GOVERNED_EXECUTOR"
    if variant == "no_approval":
        monkeypatch.delenv("SMART_MEGA_CERTIFICATION_APPROVAL")
    if variant == "wrong_sha":
        sha = "a" * 40
    if variant == "wrong_host":
        host = "not-real-local-host"
    if variant == "wrong_origin":
        git(tmp_path, "remote", "set-url", "origin", "https://github.com/other/project.git")
    if variant == "github_actions":
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
    if variant == "github_event":
        monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    if variant == "wrong_id":
        uid = "123"
    if variant == "wrong_kind":
        kind = "GITHUB_ACTIONS"
    with pytest.raises((PermissionError, ValueError)):
        execution_provenance(tmp_path, sha, uid, host, executor_kind=kind)


def test_forged_external_certification_rejected(tmp_path):
    sha, junit, fp = source_repo(tmp_path)
    for kind in ("GITHUB_ACTIONS", "LMCP_LINUX_VPS", "FEDERATED_PC", None):
        authority = {
            "certified_source_commit": sha, "certified_ci_run_id": str(uuid4()),
            "certified_execution": {"kind": kind, "execution_id": str(uuid4()),
                                    "hostname": "unknown", "source_commit": sha},
            "certified_source_code_fingerprint_sha256": fp["sha256"],
            "certified_regression_junit_sha256": sha256_file(junit),
        }
        (tmp_path / "SMART_CANONICAL_ROOT.json").write_text(json.dumps(authority))
        assert regression_source_binding(tmp_path, junit, fp)["status"] == "FAIL"
