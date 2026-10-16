"""Source access gate and quality ledger, no real YouTube access in tests."""
import json
import pytest

from smart_video_official_queue import run_official_queue, _read_state
from smart_video_source_access import block_source, read_source_gate
from smart_video_observation_quality import quality_snapshot, save_quality_snapshot
from test_smart_video_official_queue import official, options, resolver, sampler, bad

PROOF = "netcmd_0739bd7d2f9a4361ac97e674d841397e"


def setup_blocked(tmp_path, n=2):
    cat = official(tmp_path, n)
    opts = options(tmp_path, cat)
    state = run_official_queue(**opts, sync_only=True)
    gate = block_source(opts["queue_dir"], "YOUTUBE_SIGN_IN_REQUIRED", PROOF)
    return opts, state, gate


def test_official_source_block_prevents_every_media_call(tmp_path):
    opts, first, gate = setup_blocked(tmp_path, 3)
    r = run_official_queue(**opts, max_items=3, resolver=bad, sampler=bad,
                           segment_locator=bad)
    assert r["source_access"] == "BLOCKED"
    assert r["source_access_reason"] == "YOUTUBE_SIGN_IN_REQUIRED"
    assert r["attempted_this_run"] == 0
    assert r["pending"] == 3
    assert r["queue_state_sha256"] == first["queue_state_sha256"]
    assert gate["state"] == "BLOCKED"
    assert not opts["checkpoint_dir"].exists()
    for _ in range(2):
        again = run_official_queue(**opts, resolver=bad, sampler=bad)
        assert again["attempted_this_run"] == 0
    assert len(list((opts["queue_dir"]/"source_gate_history").glob("*.json"))) == 1


def test_repeated_block_is_idempotent_and_conflicting_reason_denied(tmp_path):
    opts, _, gate = setup_blocked(tmp_path)
    again = block_source(opts["queue_dir"], "YOUTUBE_SIGN_IN_REQUIRED", PROOF)
    assert again["sha256"] == gate["sha256"]
    with pytest.raises(ValueError, match="SOURCE_ALREADY_BLOCKED"):
        block_source(opts["queue_dir"], "HTTP_429", PROOF)
    with pytest.raises(ValueError, match="EVIDENCE_ID_INVALID"):
        block_source(opts["queue_dir"], "HTTP_429", "not-a-real-proof")


def test_quality_ledger_50_blocked_contests_has_no_fabricated_frames(tmp_path):
    opts, _, gate = setup_blocked(tmp_path, 50)
    report = save_quality_snapshot(**opts)
    assert report["official_contests_in_queue"] == 50
    assert report["source_gate_sha256"] == gate["sha256"]
    assert report["source_access_state"] == "BLOCKED"
    assert report["count_by_quality"] == {"SOURCE_ACCESS_BLOCKED":50}
    assert report["checkpoints_reporting_decoded_frames"] == 0
    assert report["predictive_weight"] == 0.0
    assert not report["predictive_weight_authorized"]
    assert all(r["frames_analyzed"] == 0 and r["checkpoint_sha256"] is None
               for r in report["records"])
    again = save_quality_snapshot(**opts)
    assert again["sha256"] == report["sha256"]
    assert len(list((opts["queue_dir"]/"quality_history").glob("*.json"))) == 1


def test_quality_from_real_observer_synthetic_sampler_never_claims_real_media(tmp_path):
    cat = official(tmp_path, 2)
    opts = options(tmp_path, cat)
    done = run_official_queue(**opts, resolver=resolver, sampler=sampler)
    assert done["verified_checkpoints"] == 2
    report = save_quality_snapshot(**opts)
    assert report["official_contests_in_queue"] == 2
    assert report["count_by_quality"] == {"NO_DECODED_FRAME_PROOF":2}
    assert report["checkpoints_reporting_decoded_frames"] == 0
    assert report["real_media_verified"] is False
    assert report["predictive_weight"] == 0.0


def test_quality_detects_mutated_checkpoint_against_immutable_sha(tmp_path):
    cat = official(tmp_path, 1)
    opts = options(tmp_path, cat)
    done = run_official_queue(**opts, resolver=resolver, sampler=sampler)
    assert done["verified_checkpoints"] == 1
    cp = next(opts["checkpoint_dir"].glob("contest_*.json"))
    doc = json.loads(cp.read_text("utf-8"))
    doc["semantic_label"] = "WINNING_NUMBER_GUESS"
    cp.write_text(json.dumps(doc), encoding="utf-8")
    report = quality_snapshot(**opts)
    assert report["count_by_quality"] == {"CHECKPOINT_CORRUPT_OR_MISSING":1}
    with pytest.raises(ValueError, match="COMPLETED_CHECKPOINT_LOST_OR_CHANGED"):
        run_official_queue(**opts, resolver=bad, sampler=bad)


def test_corrupt_media_gate_archive_stops_queue_not_bypass(tmp_path):
    opts, _, gate = setup_blocked(tmp_path, 1)
    history = opts["queue_dir"]/"source_gate_history"/(gate["sha256"]+".json")
    history.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="SOURCE_GATE_HISTORY_INVALID"):
        run_official_queue(**opts, resolver=bad, sampler=bad)


def test_quality_pointer_tamper_refused(tmp_path):
    opts, _, _ = setup_blocked(tmp_path, 1)
    first = save_quality_snapshot(**opts)
    pointer = opts["queue_dir"]/"SMART_CAIXA_OBSERVATIONAL_QUALITY_CURRENT.json"
    value = json.loads(pointer.read_text("utf-8"))
    value["count_by_quality"]["SOURCE_ACCESS_BLOCKED"] = 0
    pointer.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="QUALITY_PREVIOUS_SHA_INVALID"):
        save_quality_snapshot(**opts)


def test_source_gate_is_not_a_prediction(tmp_path):
    opts, _, gate = setup_blocked(tmp_path, 1)
    assert gate["predictive_weight"] == 0.0
    assert gate["release_policy"] == "REQUIRES_AUTHORIZED_SOURCE_ACCESS_PROOF"
    assert read_source_gate(opts["queue_dir"])["state"] == "BLOCKED"
    assert not any("winning_numbers" in json.dumps(r) for r in _read_state(opts["queue_dir"])["records"].values())
