"""Regression: a predictive card command cannot silently downgrade to random contingency."""
import pytest
import smart_operator as operator


@pytest.mark.parametrize("state", ["FROZEN", "ADJUDICATED", "REVIEWED"])
def test_next_contest_predictive_request_never_emits_contingency(tmp_path, monkeypatch, state):
    monkeypatch.setattr(operator, "canonical_root", lambda supplied=None: tmp_path)
    monkeypatch.setattr(operator, "load_lifecycle", lambda root: {
        "state": state, "target_contest": 3081, "sha256": "a" * 64
    })
    with pytest.raises(ValueError, match="PREDICTIVE_CARD_BLOCKED"):
        operator.generate_card_operation(tmp_path, 3082)
    assert not (tmp_path / "runtime" / "contingency_cards").exists()


def test_predictive_request_rejects_unrelated_target_without_random_choice(tmp_path, monkeypatch):
    monkeypatch.setattr(operator, "canonical_root", lambda supplied=None: tmp_path)
    monkeypatch.setattr(operator, "load_lifecycle", lambda root: {
        "state": "ADJUDICATED", "target_contest": 3081, "sha256": "b" * 64
    })
    with pytest.raises(ValueError, match="PREDICTIVE_CARD_BLOCKED"):
        operator.generate_card_operation(tmp_path, 3083)
    assert not (tmp_path / "runtime" / "contingency_cards").exists()


def test_operator_contract_disallows_implicit_contingency():
    from smart_operator_contract import contract
    assert contract()["implicit_contingency_fallback_forbidden"] is True


@pytest.mark.parametrize("invalid", [
    {"status": "CONTINGENCY_NOT_CERTIFIED", "target_contest": 3082,
     "numbers": [6, 16, 31, 32, 49, 54]},
    {"schema": "SMART_FREEZE_OPERATION_1", "status": "FROZEN",
     "target_contest": 3082, "model_certified": False},
    {"schema": "SMART_FREEZE_OPERATION_1", "status": "FROZEN",
     "target_contest": 3081, "idempotent_replay": True,
     "freeze_file": "wrong", "freeze_sha256": "a" * 64},
    {"schema": "SMART_FREEZE_OPERATION_1", "status": "FROZEN",
     "target_contest": 3082, "idempotent_replay": True},
])
def test_last_boundary_rejects_non_predictive_or_unbound_card(invalid):
    from smart_operator_contract import require_predictive_card_result
    with pytest.raises(ValueError, match="PREDICTIVE_CARD_ONLY"):
        require_predictive_card_result(invalid, 3082)


def test_last_boundary_accepts_audited_prospective_card():
    from smart_operator_contract import require_predictive_card_result
    result = {
        "proof": {"status": "PASS", "target_contest": 3082, "result_used": False,
                  "freeze_sha256": "a" * 64, "freeze_file": "runtime/freeze.json"},
        "freeze": {"status": "FROZEN", "freeze_sha256": "a" * 64},
        "consumer_integration": {"status": "PASS"}
    }
    assert require_predictive_card_result(result, 3082) == result


def test_last_boundary_accepts_verified_historical_replay_only():
    from smart_operator_contract import require_predictive_card_result
    result = {
        "schema": "SMART_FREEZE_OPERATION_1",
        "status": "FROZEN", "target_contest": 3082,
        "idempotent_replay": True,
        "freeze_file": "runtime/learning_epochs/proven/freeze.json",
        "freeze_sha256": "a" * 64, "result_used": False,
        "consumer_integration": {"status": "PASS"}
    }
    assert require_predictive_card_result(result, 3082) == result
