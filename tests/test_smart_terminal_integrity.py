"""Characterization tests for terminal evidence I/O, path, and temporal safety."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from smart_terminal_integrity import (
    atomic_write_json,
    file_sha256,
    project_local_path,
    read_json_object,
    validate_post_result_temporal_guard,
)


def test_file_hash_matches_sha256_with_chunked_input(tmp_path):
    path = tmp_path / "large.bin"
    data = b"ABC" * 400_000
    path.write_bytes(data)
    assert file_sha256(path) == hashlib.sha256(data).hexdigest()


def test_json_read_accepts_bom_and_rejects_non_object(tmp_path):
    path = tmp_path / "proof.json"
    path.write_text('{"status":"PASS"}', encoding="utf-8-sig")
    assert read_json_object(path) == {"status": "PASS"}
    path.write_text('[]', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object required"):
        read_json_object(path)


def test_json_atomic_write_overwrites_without_partial_files(tmp_path):
    path = tmp_path / "subdirectory" / "proof.json"
    atomic_write_json(path, {"status": "OLD"})
    atomic_write_json(path, {"status": "PASS", "label": "evidência"})
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "status": "PASS", "label": "evidência",
    }
    assert not list(path.parent.glob("proof.json.*.tmp"))


def test_project_path_accepts_child_and_rejects_escape(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    target = root / "runtime" / "proof.json"
    assert project_local_path(root, "runtime/proof.json", "receipt") == target.resolve()
    assert project_local_path(root, target, "receipt") == target.resolve()
    with pytest.raises(ValueError, match="receipt escapes canonical root"):
        project_local_path(root, "../outside.json", "receipt")


def _operator_documents():
    guard = {
        "status": "OPERATOR_UNVERIFIED_DRAW_TIME", "target_contest": 3071,
        "before_scheduled_draw": False, "result_used": False, "operator_selected": True,
    }
    schedule = {
        "authority": "OPERATOR_SELECTED_TARGET", "target_contest": 3071,
        "target_date": None, "operator_selected_target": True,
        "draw_time_independently_verified": False, "result_used": False,
    }
    active = {"operator_selected_target": True, "temporal_guard": guard, "target_schedule": schedule}
    freeze = {
        "target_contest": 3071, "cutoff_contest": 3070,
        "frozen_before_result": True, "causal_cutoff": True,
        "temporal_guard": dict(guard), "target_schedule": dict(schedule),
    }
    return active, freeze


def test_operator_time_remains_unverified_after_result(tmp_path):
    active, freeze = _operator_documents()
    assert validate_post_result_temporal_guard(
        active, freeze, 3071
    ) == "OPERATOR_TIME_UNVERIFIED_AUDIT_ONLY"
    assert active["target_schedule"]["draw_time_independently_verified"] is False


def test_temporal_guard_rejects_retrospective_promotion():
    active, freeze = _operator_documents()
    active["temporal_guard"]["status"] = "PASS"
    with pytest.raises(ValueError, match="temporal"):
        validate_post_result_temporal_guard(active, freeze, 3071)
