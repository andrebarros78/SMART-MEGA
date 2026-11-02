"""Release attestation must bind the real portable Git checkout state."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import smart_release_attestation as target


def _signed(doc):
    document = dict(doc)
    raw = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    document["sha256"] = hashlib.sha256(raw).hexdigest()
    return document


def _document():
    return dict(host="executor", root="/checkout", version="6.3.2",
                git_head="a" * 40, git_branch="main", git_status_porcelain="",
                dataset_sha256="d" * 64, critical_code_manifest_sha256="f" * 64,
                authority_hashes={"junit.xml": "c" * 64})


def test_git_query_uses_current_checkout_and_not_windows_only_executable(tmp_path):
    subprocess.check_call(["git", "init", "-q", str(tmp_path)])
    subprocess.check_call(["git", "-C", str(tmp_path), "-c", "user.email=test@example.invalid", "-c", "user.name=Local Test", "commit", "--allow-empty", "-qm", "fixture"])
    expected = subprocess.check_output(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True).strip()
    assert target._git(tmp_path, "rev-parse", "HEAD") == expected
    assert target._git(tmp_path, "status", "--porcelain=v1") == ""


@pytest.mark.parametrize("field,value", [
    ("git_branch", "other-branch"),
    ("git_status_porcelain", " M critical_source.py"),
])
def test_attestation_verification_rejects_changed_git_context(monkeypatch, field, value):
    current = _document()
    monkeypatch.setattr(target, "build", lambda root: dict(current))
    stale = dict(current)
    stale[field] = value
    with pytest.raises(RuntimeError, match="release attestation stale: " + field):
        target.verify(Path("/unused"), _signed(stale))


def test_consistent_attestation_still_verifies(monkeypatch):
    current = _document()
    monkeypatch.setattr(target, "build", lambda root: dict(current))
    doc = _signed(current)
    assert target.verify(Path("/unused"), doc) == doc


def test_tampered_self_hash_rejected_before_freshness_checks(monkeypatch):
    current = _document()
    monkeypatch.setattr(target, "build", lambda root: dict(current))
    doc = _signed(current)
    doc["git_branch"] = "another"
    with pytest.raises(RuntimeError, match="release attestation self-hash mismatch"):
        target.verify(Path("/unused"), doc)
