from __future__ import annotations

import json
import hashlib
import os
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AUTHORITY = ROOT / "SMART_CANONICAL_ROOT.json"


def test_canonical_root_authority_matches_sanitized_state() -> None:
    doc = json.loads(AUTHORITY.read_text(encoding="utf-8-sig"))
    assert doc["schema"] == "SMART_CANONICAL_ROOT_V1"
    assert doc["project"] == "SMART-MEGA"
    assert doc["version"] == (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()
    assert doc["canonical_root"] == r"C:\SMART-MEGA"
    assert doc["legacy_alias"] == r"C:\ProgramData\B2-Learning-Work\SMART-MEGA"
    assert doc["legacy_alias_type"] == "REMOVED"
    assert doc["legacy_alias_present"] is False
    assert doc["legacy_target"] == []
    assert doc["canonical_state"] == "CANONICAL_ONLY"

    junit = ROOT / doc["certified_regression"]["junit_file"]
    actual_junit_sha = hashlib.sha256(junit.read_bytes()).hexdigest()
    assert doc["certified_regression_junit_sha256"] == actual_junit_sha
    assert doc["certified_regression"]["junit_sha256"] == actual_junit_sha
    assert doc["certified_regression_tests"] == doc["certified_regression"]["tests"]
    assert doc["certified_regression_failures"] == doc["certified_regression"]["failures"] == 0
    assert doc["certified_regression_errors"] == doc["certified_regression"]["errors"] == 0

    if os.name == "nt" and socket.gethostname().casefold() == str(doc["hostname"]).casefold():
        assert Path(doc["canonical_root"]).resolve() == ROOT.resolve()
        assert Path(doc["canonical_root"]).is_dir()
        assert not Path(doc["legacy_alias"]).exists()
