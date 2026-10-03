from __future__ import annotations

import json
from pathlib import Path

import pytest

import smart_canonical_root_authority as authority


def _seal(doc: dict) -> dict:
    out = dict(doc)
    out.pop("sha256", None)
    out["sha256"] = authority._sha_json(out)
    return out


def _base() -> dict:
    return _seal({
        "schema": authority.SCHEMA,
        "project": "SMART-MEGA",
        "version": "6.3.2",
        "canonical_root": r"C:\SMART-MEGA",
        "legacy_alias": r"C:\ProgramData\B2-Learning-Work\SMART-MEGA",
        "legacy_alias_present": False,
        "canonical_state": "CANONICAL_ONLY",
        "git_head": "ref: refs/heads/historical",
        "git_ref_sha": "f4e7bae3775678312ff61e583a902e636cf20417",
        "certified_regression_tests": 1,
        "certified_regression_failures": 0,
        "certified_regression_errors": 0,
        "certified_regression_junit": authority.JUNIT_FILE,
        "certified_regression_junit_sha256": "old",
        "certified_regression": {"junit_file": authority.JUNIT_FILE, "junit_sha256": "old", "tests": 1, "failures": 0, "errors": 0, "skipped": 0, "status": "PASS"},
    })


def _binding(tmp_path: Path) -> tuple[Path, dict, dict, dict]:
    junit = tmp_path / authority.JUNIT_FILE
    junit.write_text("<testsuites tests='7' failures='0' errors='0' skipped='1'><testsuite tests='7' failures='0' errors='0' skipped='1'/></testsuites>", encoding="utf-8")
    regression = {"tests": 7, "failures": 0, "errors": 0, "skipped": 1, "status": "PASS", "sha256": "junit-summary"}
    fingerprint = {"file_count": 2, "files": [{"path": "a.py", "sha256": "a"}], "sha256": "fp-current"}
    binding = {
        "status": "PASS",
        "file": "SMART_AUDIT_JUNIT_CURRENT_PROOF.json",
        "file_sha256": "binding-file-current",
        "proof_sha256": "proof-current",
        "checks": {"all": True},
    }
    return junit, regression, fingerprint, binding


def test_refresh_binds_content_without_rewriting_historical_git_reference(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / authority.AUTHORITY_FILE
    path.write_text(json.dumps(_base()), encoding="utf-8")
    current = _binding(tmp_path)
    monkeypatch.setattr(authority, "_current_binding", lambda root: current)
    doc = authority.build(tmp_path)
    assert doc["git_ref_sha"] == "f4e7bae3775678312ff61e583a902e636cf20417"
    assert doc["git_reference_authoritative"] is False
    assert doc["authority_binding_mode"] == authority.BINDING_MODE
    assert doc["certified_regression_tests"] == 7
    assert doc["certified_regression_skipped"] == 1
    assert doc["certified_code_fingerprint_sha256"] == "fp-current"
    assert doc["certified_regression_binding_sha256"] == "binding-file-current"
    assert doc["certified_regression_proof_sha256"] == "proof-current"
    body = dict(doc); observed = body.pop("sha256")
    assert observed == authority._sha_json(body)


def test_write_preserves_crlf_representation_and_verifies(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / authority.AUTHORITY_FILE
    original = json.dumps(_base(), ensure_ascii=False, indent=2).replace("\n", "\r\n") + "\r\n"
    path.write_bytes(original.encode("utf-8"))
    current = _binding(tmp_path)
    monkeypatch.setattr(authority, "_current_binding", lambda root: current)
    authority.write(tmp_path)
    raw = path.read_bytes()
    assert b"\r\n" in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert authority.verify(tmp_path)["status"] == "PASS"


def test_verify_fails_closed_when_current_fingerprint_changes(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / authority.AUTHORITY_FILE
    path.write_text(json.dumps(_base()), encoding="utf-8")
    current = _binding(tmp_path)
    monkeypatch.setattr(authority, "_current_binding", lambda root: current)
    authority.write(tmp_path)
    junit, regression, fingerprint, binding = current
    stale = dict(fingerprint); stale["sha256"] = "fp-changed"
    monkeypatch.setattr(authority, "_current_binding", lambda root: (junit, regression, stale, binding))
    with pytest.raises(ValueError, match="code_fingerprint_current"):
        authority.verify(tmp_path)
