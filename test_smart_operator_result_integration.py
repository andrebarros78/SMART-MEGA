"""Operator source is honored by the real terminal executor and CLI consumer."""
import json
import pytest
import smart_terminal_executor as terminal
import smart_operator as op
from smart_github_operator import ACTIONS, command_args
from smart_operator_result import register


def _input(root):
    raw = {"schema": "SMART_OPERATOR_RESULT_INPUT_1",
           "target_contest": 3071, "draw_date": "17/10/2026",
           "numbers": [2, 13, 21, 32, 45, 60]}
    p = root / "SMART_OPERATOR_RESULT_INPUT_3071.json"
    p.write_text(json.dumps(raw))
    return p


def test_live_terminal_wrapper_uses_operator_without_network(tmp_path, monkeypatch):
    register(tmp_path, 3071, _input(tmp_path))
    def check(root, target, fetcher=None):
        assert fetcher is not None
        payload, evidence = fetcher(target)
        assert evidence["status"] == "OPERATOR_ATTESTED_RESULT"
        assert evidence["primary"]["channel"] == "OPERATOR"
        return {"status": "OFFICIAL_RESULT_AVAILABLE", "actual_numbers": evidence["primary"]["numbers"]}
    monkeypatch.setattr(terminal._engine, "probe_active_epoch", check)
    monkeypatch.setattr(terminal._engine.official_consensus, "fetch_consensus",
                        lambda *a, **k: pytest.fail("must not call CAIXA"))
    out = terminal.probe(tmp_path, 3071)
    assert out["actual_numbers"] == [2, 13, 21, 32, 45, 60]


def test_terminal_execute_consumes_same_operator_source(tmp_path, monkeypatch):
    register(tmp_path, 3071, _input(tmp_path))
    def execute(root, target, fetcher=None, allow_terminal_write=True):
        payload, evidence = fetcher(target)
        assert evidence["primary"]["channel"] == "OPERATOR"
        assert allow_terminal_write
        return {"status": "OPERATOR_FLOW", "numbers": evidence["primary"]["numbers"]}
    monkeypatch.setattr(terminal._engine, "execute_active_epoch", execute)
    assert terminal.execute(tmp_path, 3071)["status"] == "OPERATOR_FLOW"


def test_operator_result_registration_requires_frozen_epoch(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "canonical_root", lambda value=None: tmp_path)
    monkeypatch.setattr(op, "assert_lifecycle_state", lambda *a, **k: {"state": "FROZEN"})
    monkeypatch.setattr(op, "verify_active_epoch",
                        lambda *a, **k: {"status": "FROZEN", "target_contest": 3071})
    monkeypatch.setattr(op, "_existing_frozen_freeze_summary", lambda *a: {"status": "FROZEN"})
    raw = _input(tmp_path)
    # In an isolated test, execute the nested business logic without startup guards.
    method = op.register_result_operation
    while hasattr(method, "__wrapped__"):
        method = method.__wrapped__
    out = method(tmp_path, 3071, raw)
    assert out["source"] == "OPERATOR"
    assert (tmp_path / "SMART_OPERATOR_RESULT_3071.json").is_file()


def test_cli_and_github_actions_have_registration_route():
    assert "register-result" in ACTIONS
    assert command_args("register-result", "3071", "SMART_OPERATOR_RESULT_INPUT_3071.json")[-5:] == [
        "register-result", "--target", "3071", "--result-file", "SMART_OPERATOR_RESULT_INPUT_3071.json"]
