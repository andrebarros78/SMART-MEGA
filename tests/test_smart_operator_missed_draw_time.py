"""Characterization tests for the pre-draw exclusion used by missed recovery.

This module must not fetch a result, issue authority, or write a proof.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pytest

from smart_operator_missed_draw_time import assert_missed_draw_elapsed


SCHEDULE = {"scheduled_datetime": "2026-11-01T21:00:00-03:00"}
DRAW_UTC = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)


def _check(schedule=SCHEDULE, now=None, *, mode="unprepared", clock=None):
    return assert_missed_draw_elapsed(
        schedule,
        now,
        mode=mode,
        clock_now=clock or (lambda: DRAW_UTC + timedelta(minutes=1)),
    )


@pytest.mark.parametrize("mode", ["unprepared", "unfrozen"])
def test_rejects_recovery_exactly_at_draw_time(mode):
    with pytest.raises(ValueError, match="missed-target recovery is forbidden before the scheduled draw"):
        _check(now=DRAW_UTC, mode=mode)


@pytest.mark.parametrize("mode", ["unprepared", "unfrozen"])
def test_rejects_recovery_before_draw_time(mode):
    with pytest.raises(ValueError, match="missed-target recovery is forbidden before the scheduled draw"):
        _check(now=DRAW_UTC - timedelta(seconds=1), mode=mode)


@pytest.mark.parametrize("mode", ["unprepared", "unfrozen"])
def test_allows_explicit_post_draw_time_without_returning_authority(mode):
    assert _check(now=DRAW_UTC + timedelta(microseconds=1), mode=mode) is None


@pytest.mark.parametrize("mode", ["unprepared", "unfrozen"])
def test_allows_equivalent_offset_aware_timezones(mode):
    local_now = datetime(2026, 11, 1, 22, 1, tzinfo=timezone(timedelta(hours=-3)))
    assert _check(now=local_now, mode=mode) is None


@pytest.mark.parametrize("mode,message", [
    ("unprepared", "unprepared missed-target recovery requires scheduled draw authority"),
    ("unfrozen", "missed-target recovery requires scheduled draw authority"),
])
def test_rejects_missing_draw_schedule_with_existing_specific_errors(mode, message):
    with pytest.raises(ValueError, match=message):
        _check({}, now=DRAW_UTC + timedelta(days=1), mode=mode)


@pytest.mark.parametrize("mode", ["unprepared", "unfrozen"])
def test_rejects_non_string_scheduled_datetime(mode):
    with pytest.raises(ValueError, match="requires scheduled draw authority"):
        _check({"scheduled_datetime": DRAW_UTC}, mode=mode)


@pytest.mark.parametrize("mode", ["unprepared", "unfrozen"])
def test_rejects_naive_scheduled_datetime(mode):
    with pytest.raises(ValueError, match="scheduled draw authority must be timezone-aware"):
        _check({"scheduled_datetime": "2026-11-01T21:00:00"}, mode=mode)


@pytest.mark.parametrize("mode", ["unprepared", "unfrozen"])
def test_rejects_naive_observed_clock(mode):
    with pytest.raises(ValueError, match="missed-target recovery clock must be timezone-aware"):
        _check(now=datetime(2026, 11, 2, 1, 0), mode=mode)


@pytest.mark.parametrize("mode", ["unprepared", "unfrozen"])
def test_propagates_bad_schedule_text_as_value_error(mode):
    with pytest.raises(ValueError):
        _check({"scheduled_datetime": "not-a-date"}, mode=mode)


def test_unfrozen_requires_dict_schedule():
    with pytest.raises(ValueError, match="missed-target recovery requires scheduled draw authority"):
        _check(None, mode="unfrozen")


@pytest.mark.parametrize("mode", ["unprepared", "unfrozen"])
def test_clock_is_read_exactly_once_when_not_explicit(mode):
    reads = []
    def clock():
        reads.append("called")
        return DRAW_UTC + timedelta(seconds=1)
    assert _check(now=None, mode=mode, clock=clock) is None
    assert reads == ["called"]


@pytest.mark.parametrize("mode", ["unprepared", "unfrozen"])
def test_explicit_clock_does_not_consult_system_time(mode):
    def forbidden():
        pytest.fail("unexpected call to system clock")
    assert _check(now=DRAW_UTC + timedelta(minutes=1), mode=mode, clock=forbidden) is None


@pytest.mark.parametrize("mode", ["unprepared", "unfrozen"])
def test_recovery_does_not_change_schedule(mode):
    schedule = dict(SCHEDULE)
    _check(schedule, now=DRAW_UTC + timedelta(seconds=1), mode=mode)
    assert schedule == SCHEDULE
