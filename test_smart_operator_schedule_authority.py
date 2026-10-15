"""Operator target selection avoids CAIXA schedules without asserting a fabricated date."""
import json
from pathlib import Path
import pytest
from smart_target_schedule import resolve_target_schedule, assert_pre_draw_window, _sha256_json


def test_operator_target_needs_no_cronogram_or_scheduled_date(tmp_path):
    doc = {"schema":"SMART_NEXT_CYCLE_AUTHORITY_1", "target_contest":3071,
           "status":"AUTHORIZED", "authorized_by":"USER_EXPLICIT_APPLY_OR_GENERATE",
           "consumed":False}
    doc["sha256"] = _sha256_json(doc)
    (tmp_path/"SMART_NEXT_CYCLE_AUTHORITY.json").write_text(json.dumps(doc))
    result = resolve_target_schedule(tmp_path, 3071, archive="does-not-exist")
    assert result["authority"] == "OPERATOR_SELECTED_TARGET"
    assert result["scheduled_datetime"] is None
    assert result["target_date"] is None
    assert result["source_sha256"] == doc["sha256"]
    proof = assert_pre_draw_window(result)
    assert proof["status"] == "OPERATOR_UNVERIFIED_DRAW_TIME"
    assert proof["before_scheduled_draw"] is False
    assert proof["operator_selected"] is True


def test_operator_target_rejects_unrelated_target_and_tamper(tmp_path):
    doc = {"schema":"SMART_NEXT_CYCLE_AUTHORITY_1", "target_contest":3071,
           "status":"AUTHORIZED", "authorized_by":"USER_EXPLICIT_APPLY_OR_GENERATE",
           "consumed":False}
    doc["sha256"] = _sha256_json(doc)
    path = tmp_path/"SMART_NEXT_CYCLE_AUTHORITY.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(FileNotFoundError):
        resolve_target_schedule(tmp_path, 3072, archive="does-not-exist")
    doc["target_contest"] = 3072
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="hash"):
        resolve_target_schedule(tmp_path, 3072, archive="does-not-exist")
