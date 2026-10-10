"""Contract tests: V2 consumes prior checkpoints without pretending to predict."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from smart_video_observation import EXTRACTOR_VERSION, ObservationConfig, _observation_fingerprint
from research.visual_learning_v2 import analyze, publish


def _fixture(root: Path, contest: int, *, status: str = "INSUFFICIENT_EVIDENCE",
             source: str | None = None, nested_result: bool = False,
             version: str | None = None, candidate_valid: bool = True) -> Path:
    cfg = ObservationConfig().validated()
    source = source or f"https://www.youtube.com/watch?v=official-{contest}"
    row = {
        "schema": "smart.video_observation.v1",
        "contest_id": str(contest),
        "source": source,
        "extractor_version": EXTRACTOR_VERSION if version is None else version,
        "hypothesis_id": None,
        "checkpoint_fingerprint": _observation_fingerprint(str(contest), source, cfg, None),
        "predictive_evidence": "NOT_ESTABLISHED",
        "main_params": vars(cfg),
        "status": status,
        "coverage_ratio": 0.35,
        "analysis_scope": {
            "start_s": 100, "end_s": 200,
            "segment_guard_passed": candidate_valid,
        },
        "spatial_consensus": {"recurrent": candidate_valid},
        "event_timestamps_s": [110, 130, 150, 170],
        "errors": [],
    }
    if nested_result:
        row["errors"] = [{"winning_numbers": [1, 2, 3, 4, 5, 6]}]
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"contest_{contest}.json"
    path.write_text(json.dumps(row, sort_keys=True), encoding="utf-8")
    return path


def test_no_input_fails_closed_without_learning_claim(tmp_path):
    report = analyze(tmp_path / "not-exists", 3100)
    assert report["learning_status"] == "NO_VERIFIED_INPUT"
    assert report["predictive_weight_authorized"] is False
    assert report["models_retrained"] is False
    assert report["eligible_observations"] == 0


def test_consume_negative_observations_as_method_feedback(tmp_path):
    _fixture(tmp_path, 3001, status="INSUFFICIENT_EVIDENCE")
    _fixture(tmp_path, 3002, status="STREAM_FAILED")
    report = analyze(tmp_path, 3003)
    assert report["eligible_observations"] == 2
    assert report["status_counts"] == {"INSUFFICIENT_EVIDENCE": 1, "STREAM_FAILED": 1}
    assert report["candidate_observations"] == 0
    assert report["technical_availability_posterior_mean"] is None


def test_future_same_contest_never_enters_learning(tmp_path):
    _fixture(tmp_path, 3000)
    _fixture(tmp_path, 3001)
    _fixture(tmp_path, 3002)
    report = analyze(tmp_path, 3001)
    assert report["training_contests"] == [3000]
    assert report["rejected_counts"]["FUTURE_OR_SAME_CONTEST"] == 2


def test_nested_results_leakage_rejected(tmp_path):
    _fixture(tmp_path, 3000, nested_result=True)
    report = analyze(tmp_path, 3001)
    assert report["eligible_observations"] == 0
    assert report["rejected_counts"]["RESULT_LABEL_LEAKAGE"] == 1


def test_legacy_versions_do_not_silently_migrate(tmp_path):
    _fixture(tmp_path, 3000, version="1.2.0")
    report = analyze(tmp_path, 3001)
    assert report["rejected_counts"]["LEGACY_VERSION_UNVERIFIED"] == 1
    assert report["learning_status"] == "NO_VERIFIED_INPUT"


def test_candidate_requires_spatial_and_segment_guards(tmp_path):
    _fixture(tmp_path, 3000, status="CANDIDATE", candidate_valid=False)
    bad = analyze(tmp_path, 3001)
    assert bad["rejected_counts"]["CANDIDATE_UNVERIFIED"] == 1
    _fixture(tmp_path, 3000, status="CANDIDATE", candidate_valid=True)
    good = analyze(tmp_path, 3001)
    assert good["candidate_observations"] == 1
    assert good["predictive_weight_authorized"] is False


def test_same_video_not_double_counted(tmp_path):
    source = "https://youtube.com/watch?v=same-broadcast"
    _fixture(tmp_path, 3000, source=source)
    _fixture(tmp_path, 3001, source=source)
    report = analyze(tmp_path, 3002)
    assert report["eligible_observations"] == 1
    assert report["rejected_counts"]["DUPLICATE_SOURCE"] == 1


def test_integrity_fingerprint_rejects_tampering(tmp_path):
    p = _fixture(tmp_path, 3000)
    row = json.loads(p.read_text())
    row["source"] = "https://youtube.com/watch?v=swapped"
    p.write_text(json.dumps(row))
    report = analyze(tmp_path, 3001)
    assert report["rejected_counts"]["FINGERPRINT_MISMATCH"] == 1


def test_snapshot_is_reproducible_and_reader_can_verify(tmp_path):
    obs, store = tmp_path / "checkpoint", tmp_path / "memory"
    _fixture(obs, 3000)
    pointer1 = publish(obs, store, 3001)
    pointer2 = publish(obs, store, 3001)
    assert pointer1 == pointer2
    snapshot = store / pointer1["snapshot_file"]
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == pointer1["snapshot_sha256"]
    assert json.loads((store / "LATEST.json").read_text()) == pointer1
    assert len(list((store / "snapshots").glob("*.json"))) == 1


def test_changed_input_creates_new_immutable_snapshot(tmp_path):
    obs, store = tmp_path / "checkpoint", tmp_path / "memory"
    p = _fixture(obs, 3000)
    first = publish(obs, store, 3001)
    _fixture(obs, 3000, status="UNOBSERVABLE")
    second = publish(obs, store, 3001)
    assert first["snapshot_sha256"] != second["snapshot_sha256"]
    assert (store / first["snapshot_file"]).exists()
    assert (store / second["snapshot_file"]).exists()
    assert p.exists()


def test_holdout_is_chronological_and_not_predictive(tmp_path):
    for i in range(20):
        _fixture(tmp_path, 3000 + i)
    report = analyze(tmp_path, 3020)
    assert report["learning_status"] == "OBSERVATION_HOLDOUT_AVAILABLE"
    assert report["training_contests"] == list(range(3000, 3015))
    assert report["holdout_contests"] == list(range(3015, 3020))
    assert report["predictive_evidence"] == "NOT_ESTABLISHED"
    assert report["technical_availability_posterior_mean"] is not None


def test_snapshot_tampering_aborts_publish(tmp_path):
    obs, store = tmp_path / "checkpoint", tmp_path / "memory"
    _fixture(obs, 3000)
    pointer = publish(obs, store, 3001)
    path = store / pointer["snapshot_file"]
    path.write_text('{"tampered":true}')
    with pytest.raises(ValueError, match="content changed"):
        publish(obs, store, 3001)


def test_learning_classifies_camera_artifact_without_false_candidate(tmp_path):
    p = _fixture(tmp_path, 3000)
    row = json.loads(p.read_text())
    row["limitations"] = [
        "motion pattern is spatially consistent with global motion/camera change",
        "recurrent region was not stable across spatial grid resolutions",
    ]
    p.write_text(json.dumps(row))
    report = analyze(tmp_path, 3001)
    assert report["failure_modes_counts"] == {
        "GLOBAL_CAMERA_MOTION": 1,
        "SPATIAL_GRID_DISAGREEMENT": 1,
    }
    assert report["candidate_observations"] == 0


def test_real_2978_failed_stream_is_consumed_only_as_negative_evidence(tmp_path):
    original = (
        Path(__file__).resolve().parents[1]
        / "release_evidence/VIDEO_OBSERVATION_20261009/CONTEST_2978_FAIL_CLOSED.json"
    )
    assert original.is_file()
    sample = tmp_path / "contest_2978.json"
    sample.write_bytes(original.read_bytes())
    report = analyze(tmp_path, 2979, "mega-visual-segment-guard-v131")
    assert report["eligible_observations"] == 1
    assert report["candidate_observations"] == 0
    assert report["status_counts"] == {"STREAM_FAILED": 1}
    assert report["failure_modes_counts"] == {"UNAVAILABLE_VISUAL_INPUT": 1}
    assert report["predictive_weight_authorized"] is False


def test_corrupt_candidate_structure_fails_closed(tmp_path):
    p = _fixture(tmp_path, 3000, status="CANDIDATE")
    row = json.loads(p.read_text())
    row["spatial_consensus"] = None
    p.write_text(json.dumps(row))
    report = analyze(tmp_path, 3001)
    assert report["eligible_observations"] == 0
    assert report["rejected_counts"] == {"CANDIDATE_UNVERIFIED": 1}
