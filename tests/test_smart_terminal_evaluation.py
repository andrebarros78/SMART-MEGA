"""Terminal policy characterization: independent of I/O and model predictions."""
from __future__ import annotations

import copy

import pytest

from smart_terminal_evaluation import evaluate_terminal_evidence


TARGET = 9001
CUTOFF = TARGET - 1
TOP6 = [1, 2, 3, 4, 5, 6]
SHA = "a" * 64


def _case():
    freeze_event = {
        "event_type": "FREEZE",
        "target_contest": TARGET,
        "cutoff_contest": CUTOFF,
        "frozen_before_result": True,
        "freeze_sha256": SHA,
    }
    freeze = {
        "frozen_before_result": True,
        "cutoff_contest": CUTOFF,
        "champion": {"top6": TOP6},
        "champion_remains_active": True,
        "production_switch_performed": False,
    }
    adjudication = {
        "event_type": "ADJUDICATION",
        "target_contest": TARGET,
        "actual_numbers": TOP6,
        "champion_hits": 6,
        "retroactive_rewrite": False,
    }
    ledger = {"events": [freeze_event, adjudication]}
    consensus = {
        "primary": {"validated": True, "numbers": TOP6},
        "terminal_source_corroboration_authorized": True,
    }
    audit = {
        "status": "PASS",
        "prospective_ledger": {
            "status": "PASS",
            "pair_count": 1,
            "no_future_leakage": True,
        },
    }
    sequence = {"valid": True, "proof_recorded": True}
    return {
        "freeze_event": freeze_event,
        "freeze": freeze,
        "adjudications": [adjudication],
        "ledger": ledger,
        "consensus": consensus,
        "audit": audit,
        "sequence_validation": sequence,
        "target": TARGET,
        "cutoff": CUTOFF,
        "expected_freeze_sha256": SHA,
    }


def _evaluate(case):
    return evaluate_terminal_evidence(**case)


def test_exact_prospective_six_of_six_is_only_eligible_with_all_checks():
    result = _evaluate(_case())
    assert result["status"] == "MISSION_PROVEN_ELIGIBLE"
    assert result["eligible_for_mission_proven"] is True
    assert result["target_contest"] == TARGET
    assert result["recomputed_hits"] == 6
    assert all(result["checks"].values())


def test_absent_source_corroboration_blocks_even_exact_six_of_six():
    case = _case()
    case["consensus"]["terminal_source_corroboration_authorized"] = False
    result = _evaluate(case)
    assert result["status"] == "MISSION_ACTIVE_6OF6_PENDING_SOURCE_CORROBORATION"
    assert result["eligible_for_mission_proven"] is False
    assert result["checks"]["source_corroborated"] is False


def test_source_missing_with_other_failed_guard_is_not_pending_only_source():
    case = _case()
    case["consensus"]["terminal_source_corroboration_authorized"] = False
    case["sequence_validation"]["valid"] = False
    result = _evaluate(case)
    assert result["status"] == "MISSION_ACTIVE_6OF6_BLOCKED_BY_TERMINAL_GUARD"
    assert result["eligible_for_mission_proven"] is False


def test_recomputed_miss_does_not_promote_even_when_reported_hits_is_six():
    case = _case()
    case["adjudications"][0]["actual_numbers"] = [7, 8, 9, 10, 11, 12]
    case["consensus"]["primary"]["numbers"] = [7, 8, 9, 10, 11, 12]
    result = _evaluate(case)
    assert result["status"] == "MISSION_ACTIVE_RESULT_ADJUDICATED_NO_6OF6"
    assert result["recomputed_hits"] == 0
    assert result["checks"]["exact_6of6"] is False


@pytest.mark.parametrize("pair_count", [0, True, 2, None])
def test_incorrect_pair_count_cannot_promote(pair_count):
    case = _case()
    case["audit"]["prospective_ledger"]["pair_count"] = pair_count
    result = _evaluate(case)
    assert result["status"] == "MISSION_ACTIVE_6OF6_BLOCKED_BY_TERMINAL_GUARD"
    assert result["checks"]["all_attempts_counted"] is False
    assert result["eligible_for_mission_proven"] is False


def test_historical_attempts_count_toward_prospective_audit():
    case = _case()
    case["ledger"]["events"].append({
        "event_type": "ADJUDICATION",
        "target_contest": TARGET - 1,
    })
    case["audit"]["prospective_ledger"]["pair_count"] = 2
    result = _evaluate(case)
    assert result["adjudication_count"] == 1
    assert result["total_adjudication_count"] == 2
    assert result["audited_pair_count"] == 2
    assert result["eligible_for_mission_proven"] is True


@pytest.mark.parametrize("failed_path", [
    ("freeze_event", "freeze_sha256", "b" * 64),
    ("freeze_event", "cutoff_contest", CUTOFF - 1),
    ("freeze", "production_switch_performed", True),
    ("adjudications", "retroactive_rewrite", True),
])
def test_material_guard_failures_reject_promotion(failed_path):
    case = _case()
    group, field, value = failed_path
    if group == "adjudications":
        case[group][0][field] = value
    else:
        case[group][field] = value
    assert _evaluate(case)["eligible_for_mission_proven"] is False


@pytest.mark.parametrize("count", [0, 2])
def test_multiple_or_missing_target_adjudications_fail_closed(count):
    case = _case()
    case["adjudications"] = [copy.deepcopy(case["adjudications"][0]) for _ in range(count)]
    with pytest.raises(ValueError, match="exactly one"):
        _evaluate(case)
