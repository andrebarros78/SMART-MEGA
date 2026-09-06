from pathlib import Path

from smart_current_epoch_contract import resolve
from smart_prospective_authority_lock import build_lock, verify_lock
from smart_regression_evidence import sha256_file

ROOT = Path(__file__).resolve().parent
LEGACY_FREEZE = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"


def test_unresolved_legacy_3054_freeze_is_preserved_as_separate_scientific_attempt():
    lock = build_lock(ROOT)
    assert lock is not None
    auth = lock["experiment_authority"]
    policy = lock["current_engineering_policy"]
    assert auth["target_contest"] == 3054
    assert auth["cutoff_contest"] == 3053
    assert auth["freeze_sha256"] == LEGACY_FREEZE
    assert auth["eligible_for_scientific_adjudication"] is True
    assert auth["eligible_to_prove_post_freeze_engineering_version"] is False
    assert policy["role_for_locked_target"] == "PARALLEL_PRE_CURRENT_ENGINEERING_ATTEMPT_ONLY"
    assert policy["may_claim_generation_of_locked_freeze"] is False
    assert policy["may_generate_independent_current_epoch_prediction_same_target_before_result"] is True
    assert policy["parallel_attempts_must_be_counted_separately"] is True
    assert policy["first_possible_authoritative_target"] == 3054
    assert sha256_file(ROOT / auth["freeze_file"]) == LEGACY_FREEZE


def test_active_epoch_never_reassigns_legacy_freeze_to_current_engineering():
    current = resolve(ROOT)
    assert current["target_contest"] == 3054
    assert current["result_used"] is False
    if current["authority_mode"] == "CARRY_FORWARD_UNRESOLVED_PROSPECTIVE":
        assert current["freeze_sha256"] == LEGACY_FREEZE
        assert current["scientific_adjudication_authority"] is True
        assert current["current_engineering_generation_authority"] is False
        assert current["freeze_origin"] == "PRE_CURRENT_ENGINEERING_ACTIVATION"
    else:
        assert current["authority_mode"] == "NEW_ENGINEERING_EPOCH"
        if current["status"] == "RESET_READY":
            assert current["freeze_authority_present"] is False
        else:
            assert current["status"] == "FROZEN"
            assert current["freeze_authority_present"] is True
            assert current["current_engineering_generation_authority"] is True
            assert current["freeze_origin"] != "PRE_CURRENT_ENGINEERING_ACTIVATION"


def test_authority_lock_file_matches_live_pending_legacy_freeze():
    lock = verify_lock(ROOT / "SMART_PROSPECTIVE_AUTHORITY_LOCK.json", root=ROOT)
    assert lock["experiment_authority"]["freeze_sha256"] == LEGACY_FREEZE
    assert all(lock["rules"].values())
