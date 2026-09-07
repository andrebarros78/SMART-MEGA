from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect
import pytest
import smart_champion_challenger as cc
import smart_full_process_pipeline as fp
from smart_target_schedule import MIN_OPERATIONAL_FREEZE_LEAD_SECONDS, SCHEMA, assert_pre_draw_window


def _schedule(draw: datetime, target: int = 9999) -> dict:
    return {"schema": SCHEMA, "target_contest": target, "scheduled_datetime": draw.isoformat()}


def test_temporal_guard_accepts_only_a_safely_future_draw():
    now = datetime(2026, 9, 6, 14, 0, tzinfo=timezone.utc)
    draw = now + timedelta(seconds=MIN_OPERATIONAL_FREEZE_LEAD_SECONDS + 120)
    proof = assert_pre_draw_window(_schedule(draw), now=now)
    assert proof["status"] == "PASS" and proof["before_scheduled_draw"] is True
    assert proof["seconds_until_draw"] > MIN_OPERATIONAL_FREEZE_LEAD_SECONDS


def test_temporal_guard_rejects_post_draw_and_safety_margin():
    now = datetime(2026, 9, 6, 14, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="window closed"):
        assert_pre_draw_window(_schedule(now - timedelta(seconds=1)), now=now)
    with pytest.raises(ValueError, match="safety margin"):
        assert_pre_draw_window(_schedule(now + timedelta(seconds=MIN_OPERATIONAL_FREEZE_LEAD_SECONDS)), now=now)


def test_production_freeze_defaults_fail_closed_and_pipeline_binds_schedule():
    sig = inspect.signature(cc.freeze_champion_challenger)
    assert sig.parameters["enforce_temporal_guard"].default is True
    source = inspect.getsource(fp.run_full_process)
    assert "freeze_window = evaluate_freeze_window(" in source
    assert "freeze_window_open" in source
    assert "schedule_authority=schedule" in source


def test_freeze_artifact_records_authoritative_temporal_evidence():
    source = inspect.getsource(cc.freeze_champion_challenger)
    assert "temporal_guard_enforced" in source and "target_schedule" in source
    assert source.count("assert_pre_draw_window(schedule_authority)") >= 2
