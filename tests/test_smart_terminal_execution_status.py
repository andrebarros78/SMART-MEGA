"""Post-result terminal status is an observation, never independent proof."""
from __future__ import annotations

import copy
import pytest

from smart_terminal_execution_status import build_terminal_execution_status


def _state():
    return dict(
        schema="SMART_TERMINAL_EXECUTOR_ACTIVE_EPOCH_1",
        target=3080,
        created_at_utc="2026-11-01T23:46:00+00:00",
        normalized={"numbers":[1,2,3,4,5,6],"draw_date":"2026-11-01"},
        consensus={"status":"CORROBORATED",
                   "terminal_source_corroboration_authorized":True},
        ingest={"schema":"SMART_OFFICIAL_RESULT_INGEST_1"},
        adjudication={"champion_hits":"4","challenger_hits":"2"},
        learned={"last_contest":"3080"},
        sequence_validation={"valid":True},
        audit={"status":"PASS","prospective_ledger":{"pair_count":13}},
        result_store={"status":"PASS"},
        evaluation={"status":"NOT_PROVEN","eligible_for_mission_proven":False},
        mission={"status":"MISSION_ACTIVE","terminal_6of6_proven":False},
    )


def test_exact_field_contract_for_unproven_result():
    result=build_terminal_execution_status(**_state())
    assert result=={
        "schema":"SMART_TERMINAL_EXECUTOR_ACTIVE_EPOCH_1",
        "created_at_utc":"2026-11-01T23:46:00+00:00",
        "target_contest":3080,
        "status":"NOT_PROVEN",
        "official_result_available":True,
        "actual_numbers":[1,2,3,4,5,6],
        "official_evidence_status":"CORROBORATED",
        "terminal_source_corroboration_authorized":True,
        "ingest_status":"SMART_OFFICIAL_RESULT_INGEST_1",
        "adjudication_status":"ADJUDICATED",
        "champion_hits":4,
        "challenger_hits":2,
        "learned_state_last_contest":3080,
        "sequence_valid":True,
        "independent_audit_status":"PASS",
        "audited_pair_count":13,
        "canonical_result_store_status":"PASS",
        "terminal_evaluation":{"status":"NOT_PROVEN","eligible_for_mission_proven":False},
        "mission_state":"MISSION_ACTIVE",
        "terminal_6of6_proven":False,
    }


def test_only_exact_boolean_true_on_mission_changes_terminal_status():
    args=_state()
    args["mission"]={"status":"MISSION_PROVEN","terminal_6of6_proven":True}
    assert build_terminal_execution_status(**args)["status"]=="MISSION_PROVEN"
    assert build_terminal_execution_status(**args)["terminal_6of6_proven"] is True


@pytest.mark.parametrize("claimed",[False,None,0,1,"true","True"])
def test_truthy_unproven_values_cannot_fake_mission_proof(claimed):
    args=_state()
    args["mission"]={"status":"MISSION_ACTIVE","terminal_6of6_proven":claimed}
    actual=build_terminal_execution_status(**args)
    assert actual["status"]=="NOT_PROVEN"
    assert actual["terminal_6of6_proven"] is False


@pytest.mark.parametrize("claimed",[False,None,0,1,"yes"])
def test_sequence_validity_requires_boolean_true(claimed):
    args=_state()
    args["sequence_validation"]={"valid":claimed}
    assert build_terminal_execution_status(**args)["sequence_valid"] is False


@pytest.mark.parametrize("claimed",[False,None,0,1,"true"])
def test_source_corroboration_requires_boolean_true(claimed):
    args=_state()
    args["consensus"]["terminal_source_corroboration_authorized"]=claimed
    assert build_terminal_execution_status(**args)["terminal_source_corroboration_authorized"] is False


def test_degraded_independent_audit_preserves_missing_pair_count():
    args=_state()
    args["audit"]={"status":"DEGRADED_HISTORICAL_EVIDENCE_MISSING"}
    result=build_terminal_execution_status(**args)
    assert result["independent_audit_status"]=="DEGRADED_HISTORICAL_EVIDENCE_MISSING"
    assert result["audited_pair_count"] is None
    assert result["status"]=="NOT_PROVEN"


def test_result_status_falls_back_to_evaluation_when_mission_unproven():
    args=_state()
    args["evaluation"]["status"]="REQUIRES_MORE_EVIDENCE"
    args["adjudication"]["status"]="ALREADY_ADJUDICATED_EVENT_PRESERVED"
    assert build_terminal_execution_status(**args)["status"]=="REQUIRES_MORE_EVIDENCE"
    assert build_terminal_execution_status(**args)["adjudication_status"]=="ALREADY_ADJUDICATED_EVENT_PRESERVED"


def test_input_documents_are_never_mutated():
    args=_state()
    before=copy.deepcopy(args)
    build_terminal_execution_status(**args)
    assert args==before


@pytest.mark.parametrize("invalid,field",[
    ("missing_champion","champion_hits"),
    ("bad_champion","champion_hits"),
    ("missing_learned","last_contest"),
])
def test_missing_required_numeric_evidence_fails_closed(invalid,field):
    args=_state()
    if invalid=="missing_champion":
        args["adjudication"].pop(field)
    elif invalid=="bad_champion":
        args["adjudication"][field]="not-an-integer"
    else:
        args["learned"].pop(field)
    with pytest.raises((KeyError,ValueError)):
        build_terminal_execution_status(**args)