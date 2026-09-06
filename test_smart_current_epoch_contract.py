from pathlib import Path
from smart_current_epoch_contract import resolve

ROOT = Path(__file__).resolve().parent
LEGACY_FREEZE = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"


def test_current_epoch_contract_is_causal_and_not_legacy_inferred():
    d = resolve(ROOT)
    assert d["target_contest"] == d["cutoff_contest"] + 1
    assert d["result_used"] is False
    assert d["terminal_authority"] is False
    if d["status"] == "RESET_READY":
        assert d["freeze_authority_present"] is False
        assert d["freeze_sha256"] is None
    else:
        assert d["status"] == "FROZEN"
        assert d["freeze_authority_present"] is True
        assert len(d["freeze_sha256"]) == 64
        assert len(set(d["top6"])) == 6


def test_legacy_locked_attempt_is_never_misattributed_to_current_engineering():
    d = resolve(ROOT)
    if d["authority_mode"] == "CARRY_FORWARD_UNRESOLVED_PROSPECTIVE":
        assert d["status"] == "FROZEN"
        assert d["freeze_sha256"] == LEGACY_FREEZE
        assert d["scientific_adjudication_authority"] is True
        assert d["current_engineering_generation_authority"] is False
        assert d["freeze_origin"] == "PRE_CURRENT_ENGINEERING_ACTIVATION"
        return
    assert d["authority_mode"] == "NEW_ENGINEERING_EPOCH"
    assert d["target_contest"] == 3054
    assert d["current_engineering_role"] == "AUTHORITATIVE_CURRENT_EPOCH"
    assert d["first_possible_authoritative_target_for_current_engineering"] == 3054
    assert d["parallel_locked_experiment"] is not None
    assert d["parallel_locked_experiment"]["freeze_sha256"] == LEGACY_FREEZE
    assert d["parallel_attempts_must_be_counted_separately"] is True
    if d["status"] == "RESET_READY":
        assert d["freeze_authority_present"] is False
    else:
        assert d["status"] == "FROZEN"
        assert d["current_engineering_generation_authority"] is True
        assert d["freeze_origin"] != "PRE_CURRENT_ENGINEERING_ACTIVATION"
