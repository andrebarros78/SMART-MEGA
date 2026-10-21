import pytest
import smart_operator as op
from smart_github_operator import command_args, ACTIONS


def test_generate_card_is_one_operator_command_without_secondary_confirmation(tmp_path, monkeypatch):
    state = {"value": "HOLD"}
    monkeypatch.setattr(op, "canonical_root", lambda value=None: tmp_path)
    monkeypatch.setattr(op, "load_lifecycle", lambda root: {"target_contest":3071, "state":state["value"]})
    calls = []
    def authorize(*args):
        calls.append("authorize-next-cycle")
        state["value"]="AUTHORIZED"
    def prepare(*args):
        calls.append("prepare")
        state["value"]="PREPARED"
    def authorize_generation(*args):
        calls.append("authorize-generation")
    def freeze(*args):
        calls.append("freeze")
        return {"status":"FROZEN","proof":{"status":"PASS","target_contest":3071}}
    monkeypatch.setattr(op,"authorize_next_cycle_operation",authorize)
    monkeypatch.setattr(op,"prepare_operation",prepare)
    monkeypatch.setattr(op,"authorize_generation_operation",authorize_generation)
    monkeypatch.setattr(op,"freeze_operation",freeze)
    result=op.generate_card_operation(tmp_path,3071)
    assert result["status"]=="FROZEN"
    assert calls==["authorize-next-cycle","prepare","authorize-generation","freeze"]


def test_generate_card_rejects_unrelated_or_invalid_lifecycle(tmp_path,monkeypatch):
    monkeypatch.setattr(op,"canonical_root",lambda value=None:tmp_path)
    monkeypatch.setattr(op,"load_lifecycle",lambda root:{"target_contest":3071,"state":"ADJUDICATED"})
    with pytest.raises(ValueError,match="requires"):
        op.generate_card_operation(tmp_path,3071)
    # A next-contest contingency still needs authenticated preceding lifecycle
    # evidence; this intentionally incomplete fixture must fail closed.
    with pytest.raises(ValueError,match="prior operational lifecycle SHA-256 invalid"):
        op.generate_card_operation(tmp_path,3072)


def test_workflow_exposes_operator_card_command():
    assert "generate-card" in ACTIONS
    assert command_args("generate-card","3071")[-3:]==["generate-card","--target","3071"]
