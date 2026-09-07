import pytest
from smart_procedural_actionability_gate import ACTIONABLE,SCIENTIFIC,evaluate,evaluate_freeze_window

def test_actionable_before_close_passes():
    r=evaluate(scheduled_datetime='2026-09-06T11:00:00-03:00',bet_close_datetime='2026-09-06T10:00:00-03:00',evidence_timestamp='2026-09-06T09:30:00-03:00',evidence_scope=ACTIONABLE)
    assert r.status=='PASS_ACTIONABLE' and r.same_contest_weight_allowed

def test_actionable_after_close_rejected():
    r=evaluate(scheduled_datetime='2026-09-06T11:00:00-03:00',bet_close_datetime='2026-09-06T10:00:00-03:00',evidence_timestamp='2026-09-06T10:30:00-03:00',evidence_scope=ACTIONABLE)
    assert r.status=='REJECT' and not r.same_contest_weight_allowed

def test_scientific_after_close_is_scientific_only():
    r=evaluate(scheduled_datetime='2026-09-06T11:00:00-03:00',bet_close_datetime='2026-09-06T10:00:00-03:00',evidence_timestamp='2026-09-06T10:50:00-03:00',evidence_scope=SCIENTIFIC)
    assert r.status=='PASS_SCIENTIFIC_ONLY' and not r.same_contest_weight_allowed

def test_after_draw_rejected():
    r=evaluate(scheduled_datetime='2026-09-06T11:00:00-03:00',bet_close_datetime='2026-09-06T10:00:00-03:00',evidence_timestamp='2026-09-06T11:01:00-03:00',evidence_scope=SCIENTIFIC)
    assert r.status=='REJECT'

def test_requires_timezone():
    with pytest.raises(ValueError,match='timezone'): evaluate(scheduled_datetime='2026-09-06T11:00:00',bet_close_datetime='2026-09-06T10:00:00-03:00',evidence_timestamp='2026-09-06T09:00:00-03:00',evidence_scope=ACTIONABLE)


def test_freeze_window_strictly_before_draw_passes():
    r=evaluate_freeze_window(
        scheduled_datetime='2026-09-06T11:00:00-03:00',
        observed_at='2026-09-06T10:59:59-03:00',
    )
    assert r.status=='PASS' and r.before_draw and r.freeze_authority_allowed

def test_freeze_window_exact_draw_time_rejected():
    r=evaluate_freeze_window(
        scheduled_datetime='2026-09-06T11:00:00-03:00',
        observed_at='2026-09-06T11:00:00-03:00',
    )
    assert r.status=='REJECT' and not r.before_draw and not r.freeze_authority_allowed

def test_freeze_window_after_draw_rejected():
    r=evaluate_freeze_window(
        scheduled_datetime='2026-09-06T11:00:00-03:00',
        observed_at='2026-09-06T11:00:01-03:00',
    )
    assert r.status=='REJECT' and not r.freeze_authority_allowed

def test_freeze_window_requires_timezone():
    with pytest.raises(ValueError,match='timezone'):
        evaluate_freeze_window(
            scheduled_datetime='2026-09-06T11:00:00',
            observed_at='2026-09-06T10:00:00-03:00',
        )
