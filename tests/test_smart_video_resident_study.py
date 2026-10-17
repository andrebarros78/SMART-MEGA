"""15-hour resident supervisor: durable state, source-policy pause and recovery."""
import sqlite3
from datetime import datetime, timezone

import pytest

from smart_video_resident_study import tick, read_status, SCHEMA
from smart_video_source_access import block_source
from smart_video_official_queue import run_official_queue
from test_smart_video_official_queue import official, options

PROOF = "netcmd_0739bd7d2f9a4361ac97e674d841397e"


def fixture(tmp_path, n=4, *, blocked=True):
    catalog = official(tmp_path, n)
    config = options(tmp_path, catalog)
    run_official_queue(**config, sync_only=True)
    if blocked:
        block_source(config["queue_dir"], "YOUTUBE_SIGN_IN_REQUIRED", PROOF)
    return config, tmp_path / "resident"


def call(config, root, now, hours=15):
    return tick(root, config["catalog_dir"], config["checkpoint_dir"],
                config["queue_dir"], window_hours=hours, now=now)


def test_first_tick_persists_clock_and_never_fetches_network(tmp_path, monkeypatch):
    config, root = fixture(tmp_path)
    r = call(config, root, 10000)
    assert r["schema"] == SCHEMA
    assert r["state"] == "PAUSED_SOURCE_ACCESS"
    assert r["started_at_epoch"] == 10000
    assert r["deadline_epoch"] == 10000 + 15 * 3600
    assert r["contests_in_queue"] == 4
    assert r["media_requests_this_tick"] == 0
    assert r["frames_analyzed"] == 0
    assert r["predictive_weight"] == 0.0
    assert (root/"SMART_CAIXA_RESIDENT.sqlite3").exists()


def test_resume_after_reboot_keeps_original_deadline_and_catalog(tmp_path):
    cfg, root = fixture(tmp_path)
    one = call(cfg, root, 5000)
    two = call(cfg, root, 5500)
    assert two["started_at_epoch"] == one["started_at_epoch"]
    assert two["deadline_epoch"] == one["deadline_epoch"]
    assert two["heartbeat_count"] == 2
    assert two["queue_sha256"] == one["queue_sha256"]
    assert two["state"] == "PAUSED_SOURCE_ACCESS"


def test_window_expires_at_15_hours_without_restart_or_extension(tmp_path):
    cfg, root = fixture(tmp_path)
    started = call(cfg, root, 100)
    done = call(cfg, root, 100 + 15 * 3600)
    replay = call(cfg, root, 100 + 16 * 3600)
    assert done["state"] == replay["state"] == "WINDOW_FINISHED"
    assert replay["started_at_epoch"] == started["started_at_epoch"]
    assert replay["deadline_epoch"] == started["deadline_epoch"]
    assert replay["media_requests_this_tick"] == 0


def test_source_unblocked_does_not_auto_start_media_without_authorization(tmp_path):
    cfg, root = fixture(tmp_path, blocked=False)
    report = call(cfg, root, 3000)
    assert report["state"] == "PAUSED_AWAITING_MEDIA_AUTHORIZATION"
    assert report["media_requests_this_tick"] == 0
    assert not cfg["checkpoint_dir"].exists()


def test_mismatched_queue_hash_quarantines_not_restarts(tmp_path):
    cfg, root = fixture(tmp_path)
    one = call(cfg, root, 4000)
    # A valid new queue snapshot is still different from the running session.
    from smart_video_official_catalog import enrich, CHANNEL
    enrich([{"id":"v0000000001","channel_id":CHANNEL,
             "description":"Mega-Sena concurso 4501 - metadata revised"}], cfg["catalog_dir"])
    with pytest.raises(ValueError, match="RESIDENT_CATALOG_OR_QUEUE_DRIFT"):
        call(cfg, root, 4100)
    assert read_status(root)["deadline_epoch"] == one["deadline_epoch"]


def test_quality_snapshot_from_block_is_stable(tmp_path):
    cfg, root = fixture(tmp_path, n=50)
    one = call(cfg, root, 20000)
    two = call(cfg, root, 20300)
    assert one["contests_in_queue"] == 50
    assert one["quality_classification"] == {"SOURCE_ACCESS_BLOCKED": 50}
    assert two["quality_sha256"] == one["quality_sha256"]
    assert two["heartbeat_count"] == 2
    assert len(list((cfg["queue_dir"]/"quality_history").glob("*.json"))) == 1


def test_source_gate_tamper_fails_closed(tmp_path):
    cfg, root = fixture(tmp_path)
    p=cfg["queue_dir"]/"SMART_CAIXA_MEDIA_SOURCE_CURRENT.json"
    p.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        call(cfg, root, 1200)
    assert read_status(root)["state"] == "QUARANTINED_SOURCE_GATE"


def test_bound_windows_and_disallow_same_root(tmp_path):
    cfg, root = fixture(tmp_path)
    with pytest.raises(ValueError, match="WINDOW_HOURS"):
        call(cfg, root, 1200, hours=16)
    with pytest.raises(ValueError, match="ROOT_COLLISION"):
        tick(cfg["queue_dir"], cfg["catalog_dir"], cfg["checkpoint_dir"],
             cfg["queue_dir"], now=1200)


def test_sqlite_integrity_survives_fresh_connections(tmp_path):
    cfg, root = fixture(tmp_path)
    one = call(cfg, root, 11000)
    with sqlite3.connect(root/"SMART_CAIXA_RESIDENT.sqlite3") as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert read_status(root)["heartbeat_count"] == one["heartbeat_count"]


def test_no_pretend_learning_on_blocked_source(tmp_path):
    cfg, root = fixture(tmp_path)
    r = call(cfg, root, 12000, hours=10)
    assert r["official_frames_decoded_verified"] == 0
    assert r["learning_complete"] is False
    assert r["source_gate_blocked"] is True
