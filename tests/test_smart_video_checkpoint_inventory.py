"""B2 checkpoint inventory: read-only and conservative validity contract."""
import io
import json
import sys
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from smart_video_observation import (
    EXTRACTOR_VERSION, PREDICTIVE_EVIDENCE, ObservationConfig,
    _observation_fingerprint,
)
from smart_video_learning import audit_checkpoint_inventory, main


def create_checkpoint(root, contest, *, poisoned=False, fingerprint_valid=True):
    cfg = ObservationConfig()
    url = f"https://example.org/contest-{contest}.mp4"
    value = {
        "schema": "smart.video_observation.v1",
        "contest_id": str(contest),
        "source": url,
        "extractor_version": EXTRACTOR_VERSION,
        "predictive_evidence": PREDICTIVE_EVIDENCE,
        "hypothesis_id": None,
        "main_params": vars(cfg),
        "checkpoint_fingerprint": _observation_fingerprint(str(contest), url, cfg, None)
            if fingerprint_valid else "invalid",
        "status": "CANDIDATE",
        "analysis_scope": {"start_s": 0.0, "end_s": 100.0, "segment_guard_passed": True},
        "spatial_consensus": {"recurrent": True},
        "event_timestamps_s": [40.0, 50.0, 60.0],
        "created_at_utc": "2026-10-10T17:00:00+00:00",
    }
    if poisoned:
        value["metadata"] = {"nested": [{"drawn_numbers": [1, 2, 3, 4, 5, 6]}]}
    path = root / f"contest_{contest}.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_inventory_13_verified_unmodified(tmp_path):
    paths = [create_checkpoint(tmp_path, n) for n in range(3000, 3013)]
    before = {p.name: p.read_bytes() for p in paths}
    output = audit_checkpoint_inventory(tmp_path, expected_count=13)
    assert output["schema"] == "SMART_VIDEO_CHECKPOINT_INVENTORY_V1"
    assert output["status"] == "CHECKPOINT_INTEGRITY_PASS"
    assert output["files_discovered"] == 13
    assert output["valid_count"] == 13
    assert output["invalid_count"] == 0
    assert output["predictive_weight"] == 0
    assert not output["predictive_weight_authorized"]
    assert [int(s) for s in output["contest_ids"]] == list(range(3000, 3013))
    assert all(len(v["sha256"]) == 64 for v in output["records"])
    assert before == {p.name: p.read_bytes() for p in paths}
    assert sorted(x.name for x in tmp_path.iterdir()) == sorted(before)


def test_inventory_rejects_nested_result_labels_and_tampering(tmp_path):
    create_checkpoint(tmp_path, 3001, poisoned=True)
    create_checkpoint(tmp_path, 3002, fingerprint_valid=False)
    output = audit_checkpoint_inventory(tmp_path, expected_count=2)
    assert output["status"] == "INCOMPLETE"
    assert output["valid_count"] == 0
    assert output["invalid_count"] == 2
    assert {r["reason"] for r in output["records"]} == {
        "INVALID_OBJECT_OR_RESULT_LEAKAGE", "FINGERPRINT_MISMATCH"
    }
    assert "drawn_numbers" not in json.dumps(output)


def test_inventory_missing_path_fails_closed(tmp_path):
    report = audit_checkpoint_inventory(tmp_path / "absent", expected_count=13)
    assert report["status"] == "PATH_UNAVAILABLE"
    assert report["records"] == []
    assert not (tmp_path / "absent").exists()


def test_inventory_cli_uses_stdout_only_and_preserves_bytes(tmp_path):
    paths = [create_checkpoint(tmp_path, n) for n in range(3100, 3113)]
    before = {p.name: p.read_bytes() for p in paths}
    out = io.StringIO()
    argv = ["smart_video_learning.py", "--inventory-readonly",
            "--checkpoint-dir", str(tmp_path), "--expected-checkpoints", "13"]
    with patch.object(sys, "argv", argv), redirect_stdout(out):
        assert main() == 0
    result = json.loads(out.getvalue())
    assert result["status"] == "CHECKPOINT_INTEGRITY_PASS"
    assert before == {p.name: p.read_bytes() for p in paths}


def test_inventory_rejects_broader_execution_modes(tmp_path):
    with pytest.raises(SystemExit) as err:
        with patch.object(sys, "argv", [
            "smart_video_learning.py", "--inventory-readonly",
            "--checkpoint-dir", str(tmp_path), "--force",
        ]):
            main()
    assert err.value.code == 2


def test_inventory_limit_is_bounded(tmp_path):
    with pytest.raises(ValueError):
        audit_checkpoint_inventory(tmp_path, expected_count=513)
    with pytest.raises(ValueError):
        audit_checkpoint_inventory(tmp_path, expected_count=13, limit=12)
