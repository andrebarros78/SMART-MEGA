"""Post-result operator target must keep time provenance unverified."""
import copy
import pytest
from smart_terminal_engine import _validate_post_result_temporal_guard


def operator_case():
    guard={"schema":"SMART_PRE_DRAW_TEMPORAL_GUARD_1",
           "status":"OPERATOR_UNVERIFIED_DRAW_TIME",
           "target_contest":3071,"before_scheduled_draw":False,
           "result_used":False,"operator_selected":True}
    schedule={"schema":"SMART_TARGET_SCHEDULE_AUTHORITY_3",
              "authority":"OPERATOR_SELECTED_TARGET",
              "target_contest":3071,"target_date":None,
              "operator_selected_target":True,
              "draw_time_independently_verified":False,
              "result_used":False}
    active={"operator_selected_target":True,"target_contest":3071,
            "temporal_guard":guard,"target_schedule":schedule}
    freeze={"target_contest":3071,"cutoff_contest":3070,
            "frozen_before_result":True,"causal_cutoff":True,
            "temporal_guard":dict(guard),"target_schedule":dict(schedule)}
    return active,freeze


def test_operator_selected_target_3071_can_recover_for_audit_without_time_proof():
    active,freeze=operator_case()
    result=_validate_post_result_temporal_guard(active,freeze,3071)
    assert result=="OPERATOR_TIME_UNVERIFIED_AUDIT_ONLY"
    assert active["temporal_guard"]["before_scheduled_draw"] is False
    assert active["target_schedule"]["draw_time_independently_verified"] is False


@pytest.mark.parametrize("field,value",[
    ("target_contest",3072),
    ("result_used",True),
    ("operator_selected",False),
    ("before_scheduled_draw",True),
    ("status","PASS"),
])
def test_operator_guard_rejects_inconsistent_metadata(field,value):
    active,freeze=operator_case()
    active["temporal_guard"][field]=value
    with pytest.raises(ValueError,match="temporal|operator|causal"):
        _validate_post_result_temporal_guard(active,freeze,3071)


@pytest.mark.parametrize("field,value",[
    ("authority","CAIXA_ARCHIVED_CRONOGRAM_PDF"),
    ("target_contest",3072),
    ("target_date","18/10/2026"),
    ("draw_time_independently_verified",True),
    ("result_used",True),
])
def test_operator_schedule_rejects_fake_official_clock(field,value):
    active,freeze=operator_case()
    active["target_schedule"][field]=value
    with pytest.raises(ValueError,match="temporal|operator|causal"):
        _validate_post_result_temporal_guard(active,freeze,3071)


def test_operator_recovery_rejects_rewritten_freeze():
    active,freeze=operator_case()
    freeze["frozen_before_result"]=False
    with pytest.raises(ValueError,match="temporal|operator|causal"):
        _validate_post_result_temporal_guard(active,freeze,3071)


def test_verified_clock_contract_stays_strict():
    active,freeze=operator_case()
    active["temporal_guard"].update(status="PASS",before_scheduled_draw=True,operator_selected=False)
    freeze["temporal_guard"]=copy.deepcopy(active["temporal_guard"])
    active["target_schedule"].update(authority="CAIXA_ARCHIVED_CRONOGRAM_PDF",
        target_date="18/10/2026",draw_time_independently_verified=True,
        operator_selected_target=False)
    active["operator_selected_target"]=False
    freeze["target_schedule"]=copy.deepcopy(active["target_schedule"])
    assert _validate_post_result_temporal_guard(active,freeze,3071)=="VERIFIED_PRE_DRAW_WINDOW"
    active["temporal_guard"]["before_scheduled_draw"]=False
    with pytest.raises(ValueError,match="temporal|operator|causal"):
        _validate_post_result_temporal_guard(active,freeze,3071)
