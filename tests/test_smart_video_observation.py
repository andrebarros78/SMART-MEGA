import json

import pytest

from smart_video_observation import (
    EXTRACTOR_VERSION,
    ObservationConfig,
    _is_youtube_source,
    _segment_from_caption_events,
    _validate_public_https,
    _atomic_json,
    analyze_contest,
    analyze_queue,
    cadence_metrics,
    coarse_timestamps,
    detect_events,
    select_promising_regions,
    should_reuse_checkpoint,
    spatial_classification,
)


def fake_resolver(_url, _timeout):
    return {
        "source_url": "https://example.org/video.mp4",
        "stream_url": "https://example.org/video.mp4",
        "video_id": "vid-1",
        "title": "synthetic",
        "duration_s": 120.0,
        "format_id": "low",
        "height": 360,
        "width": 640,
        "protocol": "https",
        "resolver": "test",
    }


def fake_sampler(spec, _timeout):
    start = float(spec["start_s"])
    duration = float(spec["duration_s"])
    hot = 35.0 <= start <= 75.0
    if duration <= 3.0:
        mean = 0.04 if hot else 0.002
        return {
            "status": "OK",
            "start_s": start,
            "duration_s": duration,
            "mean_motion": mean,
            "median_motion": mean,
            "max_motion": mean * 2,
            "read_frames": 20,
            "analyzed_frames": 10,
            "motion_scores": [mean] * 8,
            "sample_times": [start + i * 0.2 for i in range(8)],
            "grid_energy": [0.01] * 12,
            "grid_energy_alt": [0.01] * 16,
            "global_motion_fraction": 0.0,
        }

    scores = [0.01, 0.012, 0.08, 0.011, 0.09, 0.012, 0.085, 0.01]
    grid = [0.005] * 12
    grid[5] = 0.08
    grid_alt = [0.005] * 16
    grid_alt[6] = 0.08
    return {
        "status": "OK",
        "start_s": start,
        "duration_s": duration,
        "mean_motion": sum(scores) / len(scores),
        "median_motion": 0.012,
        "max_motion": max(scores),
        "read_frames": 60,
        "analyzed_frames": len(scores) + 1,
        "motion_scores": scores,
        "sample_times": [start + i * 0.5 for i in range(len(scores))],
        "grid_energy": grid,
        "grid_energy_alt": grid_alt,
        "global_motion_fraction": 0.0,
    }


def test_candidate_is_fail_closed_and_provenance_complete(tmp_path):
    result = analyze_contest(
        "3059",
        "https://example.org/video.mp4",
        tmp_path,
        ObservationConfig(coarse_points=8, workers=2, max_refined_regions=2),
        resolver=fake_resolver,
        sampler=fake_sampler,
    )
    assert result["status"] == "CANDIDATE"
    assert result["semantic_label"] == "MOTION_EVENT_CANDIDATE"
    assert "CONFIRMED_EJECTION" not in json.dumps(result)
    assert result["predictive_evidence"] == "NOT_ESTABLISHED"
    assert result["media_persisted_bytes"] == 0
    assert result["coverage_ratio"] < 0.5
    assert result["event_timestamps_s"]
    assert result["stream_provenance"]["format_id"] == "low"
    assert result["extractor_version"] == EXTRACTOR_VERSION
    assert (tmp_path / "contest_3059.json").exists()
    forbidden = {
        "drawn_numbers",
        "result_numbers",
        "winning_numbers",
        "dezenas_sorteadas",
    }
    assert not forbidden.intersection(result)


def test_valid_checkpoint_is_reused_without_resolver_call(tmp_path):
    cfg = ObservationConfig(coarse_points=8)
    first = analyze_contest(
        "x1", "https://example.org/v.mp4", tmp_path, cfg,
        resolver=fake_resolver, sampler=fake_sampler,
    )
    assert first["checkpoint_reused"] is False

    def resolver_must_not_run(*_args):
        raise AssertionError("resolver should not run for valid same-version checkpoint")

    second = analyze_contest(
        "x1", "https://example.org/v.mp4", tmp_path, cfg,
        resolver=resolver_must_not_run, sampler=fake_sampler,
    )
    assert second["checkpoint_reused"] is True


def test_failed_checkpoint_is_reprocessed(tmp_path):
    cp = tmp_path / "contest_x2.json"
    cp.write_text(json.dumps({
        "contest_id": "x2",
        "status": "STREAM_FAILED",
        "extractor_version": EXTRACTOR_VERSION,
        "hypothesis_id": None,
    }), encoding="utf-8")
    result = analyze_contest(
        "x2", "https://example.org/v.mp4", tmp_path,
        ObservationConfig(coarse_points=8),
        resolver=fake_resolver, sampler=fake_sampler,
    )
    assert result["status"] == "CANDIDATE"
    assert result["checkpoint_reused"] is False


def test_stream_failure_is_persisted_and_does_not_force_candidate(tmp_path):
    def bad_resolver(_url, _timeout):
        raise RuntimeError("blocked")

    result = analyze_contest(
        "x3", "https://example.org/v.mp4", tmp_path,
        resolver=bad_resolver, sampler=fake_sampler,
    )
    assert result["status"] == "STREAM_FAILED"
    assert result["semantic_label"] is None
    saved = json.loads((tmp_path / "contest_x3.json").read_text(encoding="utf-8"))
    assert saved["status"] == "STREAM_FAILED"


def test_timeout_is_terminal_for_contest_not_global_queue(tmp_path):
    def timeout_sampler(spec, _timeout):
        return {"status": "TIMEOUT", "start_s": spec["start_s"], "error": "sample timeout"}

    result = analyze_contest(
        "x4", "https://example.org/v.mp4", tmp_path,
        ObservationConfig(coarse_points=4),
        resolver=fake_resolver, sampler=timeout_sampler,
    )
    assert result["status"] == "TIMEOUT"
    assert (tmp_path / "contest_x4.json").exists()


def test_selector_limits_regions_and_avoids_near_duplicates():
    cfg = ObservationConfig(max_refined_regions=2, refine_window_s=6.0, coarse_sample_s=2.5)
    coarse = [
        {"status": "OK", "start_s": 10.0, "mean_motion": 0.08},
        {"status": "OK", "start_s": 11.0, "mean_motion": 0.07},
        {"status": "OK", "start_s": 50.0, "mean_motion": 0.06},
        {"status": "OK", "start_s": 80.0, "mean_motion": 0.05},
    ]
    selected = select_promising_regions(coarse, cfg, 120.0)
    assert len(selected) == 2
    assert abs(selected[0] - selected[1]) >= 4.5


def test_event_detection_and_cadence_are_structured():
    cfg = ObservationConfig(motion_floor=0.01, event_mad_multiplier=2.0, min_event_gap_s=0.2)
    sample = {
        "motion_scores": [0.01, 0.011, 0.09, 0.012, 0.095, 0.011, 0.08, 0.01],
        "sample_times": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
    }
    events = detect_events(sample, cfg)
    metrics = cadence_metrics(events)
    assert len(events) >= 2
    assert metrics["event_count"] == len(events)
    assert metrics["median_gap_s"] is not None
    assert 0.0 <= metrics["regularity"] <= 1.0


def test_spatial_global_motion_is_not_promoted_to_semantics():
    spatial = spatial_classification([{
        "status": "OK",
        "grid_energy": [0.1] * 12,
        "global_motion_fraction": 1.0,
    }])
    assert spatial["classification"] == "GLOBAL_MOTION_OR_CAMERA_CHANGE"


def test_checkpoint_reuse_contract_version_hypothesis_and_failure():
    base = {
        "contest_id": "x",
        "status": "CANDIDATE",
        "extractor_version": EXTRACTOR_VERSION,
        "hypothesis_id": "h1",
    }
    assert should_reuse_checkpoint(base, EXTRACTOR_VERSION, "h1", False)
    assert not should_reuse_checkpoint(base, "new", "h1", False)
    assert not should_reuse_checkpoint(base, EXTRACTOR_VERSION, "h2", False)
    assert not should_reuse_checkpoint(base, EXTRACTOR_VERSION, "h1", True)
    assert not should_reuse_checkpoint(dict(base, status="STREAM_FAILED"), EXTRACTOR_VERSION, "h1", False)


def test_private_and_local_sources_are_rejected_fail_closed():
    with pytest.raises(ValueError):
        _validate_public_https("https://127.0.0.1/video.mp4")
    with pytest.raises(ValueError):
        _validate_public_https("https://192.168.1.10/video.mp4")
    with pytest.raises(ValueError):
        _validate_public_https("https://localhost/video.mp4")
    with pytest.raises(ValueError):
        _validate_public_https("http://example.org/video.mp4")


def test_unobservable_checkpoint_is_reprocessed_by_contract():
    failed = {
        "contest_id": "x",
        "status": "UNOBSERVABLE",
        "extractor_version": EXTRACTOR_VERSION,
        "hypothesis_id": None,
    }
    assert not should_reuse_checkpoint(failed, EXTRACTOR_VERSION, None, False)


def test_global_motion_with_events_stays_insufficient_evidence(tmp_path):
    def global_sampler(spec, _timeout):
        start = float(spec["start_s"])
        duration = float(spec["duration_s"])
        scores = [0.05] * 8 if duration <= 3.0 else [0.01, 0.012, 0.08, 0.011, 0.09, 0.012, 0.085, 0.01]
        return {
            "status": "OK",
            "start_s": start,
            "duration_s": duration,
            "mean_motion": sum(scores) / len(scores),
            "median_motion": sorted(scores)[len(scores) // 2],
            "max_motion": max(scores),
            "read_frames": 40,
            "analyzed_frames": len(scores) + 1,
            "motion_scores": scores,
            "sample_times": [start + i * 0.5 for i in range(len(scores))],
            "grid_energy": [0.1] * 12,
            "grid_energy_alt": [0.1] * 16,
            "global_motion_fraction": 1.0,
        }

    result = analyze_contest(
        "global-motion", "https://example.org/v.mp4", tmp_path,
        ObservationConfig(coarse_points=4, max_refined_regions=1),
        resolver=fake_resolver, sampler=global_sampler,
    )
    assert result["event_timestamps_s"]
    assert result["spatial"]["classification"] == "GLOBAL_MOTION_OR_CAMERA_CHANGE"
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["confidence"] == 0.0


def test_too_few_events_stays_insufficient_evidence(tmp_path):
    def one_event_sampler(spec, _timeout):
        start = float(spec["start_s"])
        duration = float(spec["duration_s"])
        scores = [0.05] * 8 if duration <= 3.0 else [0.01, 0.011, 0.09, 0.012, 0.011, 0.012, 0.011, 0.01]
        grid = [0.002] * 12
        grid[4] = 0.1
        grid_alt = [0.002] * 16
        grid_alt[5] = 0.1
        return {
            "status": "OK",
            "start_s": start,
            "duration_s": duration,
            "mean_motion": sum(scores) / len(scores),
            "median_motion": 0.012,
            "max_motion": max(scores),
            "read_frames": 40,
            "analyzed_frames": len(scores) + 1,
            "motion_scores": scores,
            "sample_times": [start + i * 0.5 for i in range(len(scores))],
            "grid_energy": grid,
            "grid_energy_alt": grid_alt,
            "global_motion_fraction": 0.0,
        }

    result = analyze_contest(
        "few-events", "https://example.org/v.mp4", tmp_path,
        ObservationConfig(coarse_points=4, max_refined_regions=1, min_candidate_events=3),
        resolver=fake_resolver, sampler=one_event_sampler,
    )
    assert len(result["event_timestamps_s"]) < 3
    assert result["status"] == "INSUFFICIENT_EVIDENCE"


def test_queue_continues_after_one_stream_failure(tmp_path):
    seen = []

    def resolver(url, timeout):
        seen.append(url)
        if "bad" in url:
            raise RuntimeError("simulated resolver failure")
        return fake_resolver(url, timeout)

    results = analyze_queue(
        [
            {"contest_id": "bad-1", "source_url": "https://bad.example/video"},
            {"contest_id": "good-2", "source_url": "https://good.example/video"},
        ],
        tmp_path,
        ObservationConfig(coarse_points=4, max_refined_regions=1),
        resolver=resolver,
        sampler=fake_sampler,
    )
    assert [r["status"] for r in results] == ["STREAM_FAILED", "CANDIDATE"]
    assert seen == ["https://bad.example/video", "https://good.example/video"]


def test_selector_penalizes_global_camera_motion():
    cfg = ObservationConfig(max_refined_regions=1, refine_window_s=6.0, coarse_sample_s=2.5)
    coarse = [
        {
            "status": "OK",
            "start_s": 10.0,
            "mean_motion": 0.09,
            "global_motion_fraction": 0.95,
            "grid_energy": [0.01] * 12,
        },
        {
            "status": "OK",
            "start_s": 50.0,
            "mean_motion": 0.05,
            "global_motion_fraction": 0.10,
            "grid_energy": [0.001, 0.001, 0.001, 0.001, 0.08, 0.001, 0.001, 0.001, 0.001, 0.001, 0.001, 0.001],
        },
    ]
    selected = select_promising_regions(coarse, cfg, 120.0)
    assert len(selected) == 1
    assert selected[0] > 40.0


def test_high_global_motion_fraction_blocks_localized_false_candidate():
    grid = [0.001] * 12
    grid[5] = 0.1
    spatial = spatial_classification([{
        "status": "OK",
        "grid_energy": grid,
        "global_motion_fraction": 0.90,
    }])
    assert spatial["classification"] == "GLOBAL_MOTION_OR_CAMERA_CHANGE"
    assert spatial["global_motion_fraction"] == 0.9


def test_multigrid_disagreement_blocks_candidate(tmp_path):
    def disagree_sampler(spec, timeout):
        result = fake_sampler(spec, timeout)
        if float(spec["duration_s"]) > 3.0:
            result["grid_energy_alt"] = [0.1] * 16
        return result

    result = analyze_contest(
        "multigrid-disagree", "https://example.org/v.mp4", tmp_path,
        ObservationConfig(coarse_points=8, max_refined_regions=2),
        resolver=fake_resolver, sampler=disagree_sampler,
    )
    assert result["spatial"]["classification"] == "RECURRENT_SOURCE_REGION_CANDIDATE"
    assert result["spatial_consensus"]["recurrent"] is False
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["confidence"] == 0.0
    assert any("grid resolutions" in value for value in result["limitations"])


def test_cadence_excludes_unobserved_inter_window_gaps():
    metrics = cadence_metrics(
        [1.0, 2.0, 100.0, 101.0],
        [[1.0, 2.0], [100.0, 101.0]],
    )
    assert metrics["event_count"] == 4
    assert metrics["gap_count"] == 2
    assert metrics["median_gap_s"] == 1.0
    assert metrics["regularity"] == 1.0
    assert metrics["basis"] == "WITHIN_OBSERVED_WINDOWS_ONLY"


def test_segment_locator_selects_operational_mega_near_case_marker():
    events = [
        (90.0, "outras loterias"),
        (100.0, "agora iniciamos o sorteio da Mega Sena"),
        (112.0, "globo com bolas e lacre"),
        (125.0, "CJ60A auditor"),
        (500.0, "Mega Sena em breve"),
    ]
    result = _segment_from_caption_events(events)
    assert result["status"] == "PASS"
    assert result["candidate_eligible"] is True
    assert result["anchor_s"] == 100.0
    assert result["case_delta_s"] <= 45.0
    assert result["segment_start_s"] < result["anchor_s"] < result["segment_end_s"]


def test_segment_locator_is_ambiguous_when_equivalent_clusters_exist():
    events = [
        (100.0, "agora iniciamos sorteio Mega Sena globo bolas lacre"),
        (125.0, "CJ60A auditor"),
        (300.0, "agora iniciamos sorteio Mega Sena globo bolas lacre"),
        (325.0, "CJ60B auditor"),
    ]
    result = _segment_from_caption_events(events)
    assert result["status"] == "AMBIGUOUS"
    assert result["candidate_eligible"] is False


def test_coarse_timestamps_respect_segment_window():
    times = coarse_timestamps(1000.0, 5, 2.5, 400.0, 520.0)
    assert len(times) == 5
    assert min(times) >= 400.0
    assert max(times) <= 517.5


def test_youtube_candidate_is_blocked_without_segment_guard(tmp_path):
    result = analyze_contest(
        "guarded",
        "https://www.youtube.com/watch?v=example",
        tmp_path,
        ObservationConfig(coarse_points=8, max_refined_regions=2),
        resolver=fake_resolver,
        sampler=fake_sampler,
        segment_locator=lambda *_args: {
            "status": "UNAVAILABLE",
            "candidate_eligible": False,
        },
    )
    assert result["event_timestamps_s"]
    assert result["spatial_consensus"]["recurrent"] is True
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["confidence"] == 0.0
    assert result["analysis_scope"]["segment_guard_passed"] is False


def test_youtube_segment_guard_restricts_analysis_window(tmp_path):
    starts = []

    def recording_sampler(spec, timeout):
        starts.append(float(spec["start_s"]))
        return fake_sampler(spec, timeout)

    result = analyze_contest(
        "guard-pass",
        "https://www.youtube.com/watch?v=example",
        tmp_path,
        ObservationConfig(coarse_points=5, max_refined_regions=1),
        resolver=fake_resolver,
        sampler=recording_sampler,
        segment_locator=lambda *_args: {
            "status": "PASS",
            "candidate_eligible": True,
            "segment_start_s": 40.0,
            "segment_end_s": 80.0,
        },
    )
    assert result["analysis_scope"]["segment_guard_passed"] is True
    assert result["analysis_scope"]["start_s"] == 40.0
    assert result["analysis_scope"]["end_s"] == 80.0
    assert starts
    assert min(starts) >= 40.0
    assert max(starts) <= 80.0


def test_youtube_detection_does_not_depend_on_result_fields(tmp_path):
    result = analyze_contest(
        "leak-guard",
        "https://www.youtube.com/watch?v=example",
        tmp_path,
        ObservationConfig(coarse_points=4, max_refined_regions=1),
        resolver=fake_resolver,
        sampler=fake_sampler,
        segment_locator=lambda *_args: {
            "status": "PASS",
            "candidate_eligible": True,
            "segment_start_s": 35.0,
            "segment_end_s": 75.0,
        },
    )
    payload = json.dumps(result).lower()
    for token in ("drawn_numbers", "winning_numbers", "result_numbers", "dezenas_sorteadas"):
        assert token not in payload
    assert result["predictive_evidence"] == "NOT_ESTABLISHED"


def test_is_youtube_source_strict_host_matching():
    assert _is_youtube_source("https://www.youtube.com/watch?v=x")
    assert _is_youtube_source("https://youtu.be/x")
    assert not _is_youtube_source("https://youtube.com.evil.example/x")
    assert not _is_youtube_source("https://example.org/youtube.com/x")



def test_checkpoint_identity_invalidates_source_change(tmp_path):
    calls = []

    def recording_resolver(url, timeout):
        calls.append(url)
        return fake_resolver(url, timeout)

    cfg = ObservationConfig(coarse_points=6)
    first = analyze_contest(
        "same-contest", "https://example.org/video-one.mp4", tmp_path,
        cfg, resolver=recording_resolver, sampler=fake_sampler,
    )
    second = analyze_contest(
        "same-contest", "https://example.org/video-two.mp4", tmp_path,
        cfg, resolver=recording_resolver, sampler=fake_sampler,
    )
    assert first["checkpoint_reused"] is False
    assert second["checkpoint_reused"] is False
    assert second["source"] == "https://example.org/video-two.mp4"
    assert first["checkpoint_fingerprint"] != second["checkpoint_fingerprint"]
    assert len(calls) == 2


def test_checkpoint_identity_invalidates_extraction_config_change(tmp_path):
    calls = []

    def recording_resolver(url, timeout):
        calls.append(url)
        return fake_resolver(url, timeout)

    source = "https://example.org/video.mp4"
    old = analyze_contest(
        "same-contest", source, tmp_path,
        ObservationConfig(coarse_points=6),
        resolver=recording_resolver, sampler=fake_sampler,
    )
    new = analyze_contest(
        "same-contest", source, tmp_path,
        ObservationConfig(coarse_points=8),
        resolver=recording_resolver, sampler=fake_sampler,
    )
    assert old["checkpoint_fingerprint"] != new["checkpoint_fingerprint"]
    assert new["checkpoint_reused"] is False
    assert len(calls) == 2


def test_old_checkpoint_without_fingerprint_never_reused(tmp_path):
    cp = tmp_path / "contest_legacy.json"
    cp.write_text(json.dumps({
        "contest_id": "legacy", "status": "CANDIDATE",
        "extractor_version": EXTRACTOR_VERSION, "hypothesis_id": None,
    }), encoding="utf-8")
    result = analyze_contest(
        "legacy", "https://example.org/video.mp4", tmp_path,
        ObservationConfig(coarse_points=4),
        resolver=fake_resolver, sampler=fake_sampler,
    )
    assert result["checkpoint_reused"] is False
    assert result["checkpoint_fingerprint"]



def test_atomic_checkpoint_writer_survives_concurrent_calls(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = tmp_path / "shared.json"

    def writer(i):
        payload = {"writer": i, "large": str(i) * 4096}
        _atomic_json(path, payload)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(writer, range(24)))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(saved["writer"], int)
    assert saved["large"] == str(saved["writer"]) * 4096
    assert list(tmp_path.glob("*.tmp")) == []
