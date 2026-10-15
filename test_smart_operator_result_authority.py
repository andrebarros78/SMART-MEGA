"""Operator is the only runtime source for draw results; no HTTP is permitted."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
import smart_operator_result as authority


def _input(tmp_path: Path, *, target=3071, numbers=None):
    doc = {"schema": "SMART_OPERATOR_RESULT_INPUT_1", "target_contest": target,
           "draw_date": "17/10/2026", "numbers": numbers or [2, 13, 21, 32, 45, 60]}
    path = tmp_path / "operator_input.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_operator_registration_and_fetch_are_local_and_idempotent(tmp_path, monkeypatch):
    path = _input(tmp_path)
    monkeypatch.setattr("requests.get", lambda *a, **k: pytest.fail("HTTP forbidden"))
    first = authority.register(tmp_path, 3071, path)
    assert first["status"] == "OPERATOR_RESULT_REGISTERED"
    second = authority.register(tmp_path, 3071, path)
    assert second["sha256"] == first["sha256"]
    payload, evidence = authority.fetch(tmp_path, 3071)
    assert payload["numero"] == 3071
    assert payload["listaDezenas"] == ["02", "13", "21", "32", "45", "60"]
    assert evidence["primary"]["channel"] == "OPERATOR"
    assert evidence["primary"]["validated"] is True
    assert evidence["terminal_source_corroboration_authorized"] is False
    assert evidence["operational_adjudication_authorized"] is True
    assert evidence["predictive_weight_authorized"] is False


def test_operator_cannot_silently_change_result(tmp_path):
    path = _input(tmp_path)
    authority.register(tmp_path, 3071, path)
    path.write_text(json.dumps({"schema": "SMART_OPERATOR_RESULT_INPUT_1",
       "target_contest": 3071, "draw_date": "17/10/2026", "numbers": [3, 13, 21, 32, 45, 60]}))
    with pytest.raises(ValueError, match="conflict"):
        authority.register(tmp_path, 3071, path)


@pytest.mark.parametrize("numbers", [[1, 1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 61], [1, 2, 3]])
def test_bad_operator_numbers_fail_closed(tmp_path, numbers):
    path = _input(tmp_path, numbers=numbers)
    with pytest.raises(ValueError):
        authority.register(tmp_path, 3071, path)


def test_tampered_registration_fails_closed(tmp_path):
    path = _input(tmp_path)
    authority.register(tmp_path, 3071, path)
    target = tmp_path / "SMART_OPERATOR_RESULT_3071.json"
    obj = json.loads(target.read_text())
    obj["actual_numbers"] = [1,2,3,4,5,6]
    target.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="hash"):
        authority.fetch(tmp_path, 3071)
