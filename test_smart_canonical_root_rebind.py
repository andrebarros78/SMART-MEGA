from __future__ import annotations

import hashlib
import json
from pathlib import Path

import smart_canonical_root_rebind as rebind


def _sha(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _authority(path: Path) -> None:
    doc = {
        "schema": "SMART_CANONICAL_ROOT_V1",
        "project": "SMART-MEGA",
        "version": "6.3.2",
        "canonical_root": r"C:\SMART-MEGA",
        "hostname": "DESKTOP-4T6AS9K",
        "canonical_state": "CANONICAL_ONLY",
        "legacy_alias_present": False,
        "certified_regression_tests": 1,
        "certified_regression_failures": 0,
        "certified_regression_errors": 0,
        "certified_regression_skipped": 0,
        "certified_regression_junit": "SMART_AUDIT_JUNIT_CURRENT.xml",
        "certified_regression_junit_sha256": "0" * 64,
        "certified_regression": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0, "status": "PASS", "junit_file": "SMART_AUDIT_JUNIT_CURRENT.xml", "junit_sha256": "0" * 64},
    }
    doc["sha256"] = _sha(doc)
    path.write_text(json.dumps(doc), encoding="utf-8")


def _junit(path: Path, *, failures: int = 0) -> None:
    path.write_text(
        f'<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="{failures}" skipped="0" tests="7" time="1.0"></testsuite></testsuites>',
        encoding="utf-8",
    )


def test_rebind_binds_green_current_regression_and_preserves_self_hash(tmp_path, monkeypatch):
    authority = tmp_path / "SMART_CANONICAL_ROOT.json"
    junit = tmp_path / "SMART_AUDIT_JUNIT_CURRENT.xml"
    _authority(authority); _junit(junit)
    monkeypatch.setattr(rebind, "_git", lambda *args: None)
    out = rebind.rebind(tmp_path)
    doc = json.loads(authority.read_text(encoding="utf-8"))
    body = dict(doc); observed = body.pop("sha256")
    assert observed == _sha(body) == out["authority_sha256"]
    assert doc["certified_regression_tests"] == 7
    assert doc["certified_regression_failures"] == 0
    assert doc["certified_regression_errors"] == 0
    assert doc["certified_regression_junit_sha256"] == hashlib.sha256(junit.read_bytes()).hexdigest()
    assert doc["certified_regression"]["junit_sha256"] == doc["certified_regression_junit_sha256"]


def test_rebind_refuses_failed_regression(tmp_path, monkeypatch):
    authority = tmp_path / "SMART_CANONICAL_ROOT.json"
    junit = tmp_path / "SMART_AUDIT_JUNIT_CURRENT.xml"
    _authority(authority); _junit(junit, failures=1)
    before = authority.read_bytes()
    monkeypatch.setattr(rebind, "_git", lambda *args: None)
    try:
        rebind.rebind(tmp_path)
    except ValueError as exc:
        assert "not green" in str(exc)
    else:
        raise AssertionError("failed regression must not rebind authority")
    assert authority.read_bytes() == before
