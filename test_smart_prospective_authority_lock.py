from pathlib import Path

from smart_current_epoch_contract import resolve
from smart_prospective_authority_lock import (
    adjudicated_lock_evidence,
    build_lock,
    verify_closure,
    verify_lock,
)
from smart_regression_evidence import sha256_file

ROOT = Path(__file__).resolve().parent
LEGACY_FREEZE = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"


def test_legacy_3054_attempt_is_no_longer_live_unresolved_after_adjudication():
    assert build_lock(ROOT) is None
    live = ROOT / "SMART_PROSPECTIVE_AUTHORITY_LOCK.json"
    closure = ROOT / "SMART_PROSPECTIVE_AUTHORITY_CLOSURE_3054.json"
    if live.is_file():
        evidence = adjudicated_lock_evidence(live, root=ROOT)
        assert evidence["target_contest"] == 3054
        assert evidence["cutoff_contest"] == 3053
        assert evidence["freeze_sha256"] == LEGACY_FREEZE
        assert len(evidence["actual_numbers"]) == 6
        assert sha256_file(ROOT / "SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json") == LEGACY_FREEZE
    else:
        closed = verify_closure(closure, root=ROOT)
        assert closed["target_contest"] == 3054
        assert closed["freeze_sha256"] == LEGACY_FREEZE
        assert closed["live_unresolved_lock_removed"] is True


def test_active_epoch_never_reassigns_legacy_freeze_to_current_engineering():
    current = resolve(ROOT)
    mode = current["authority_mode"]
    if mode == "POST_ADJUDICATION_ROLLOVER_PENDING":
        assert current["target_contest"] == 3054
        assert current["parallel_experiment_adjudicated"] is True
        assert current["rollover_required"] is True
        assert current["freeze_authority_present"] is False
        assert current["current_engineering_generation_authority"] is False
        assert current["parallel_locked_experiment"]["freeze_sha256"] == LEGACY_FREEZE
        return
    if mode == "CARRY_FORWARD_UNRESOLVED_PROSPECTIVE":
        assert current["freeze_sha256"] == LEGACY_FREEZE
        assert current["scientific_adjudication_authority"] is True
        assert current["current_engineering_generation_authority"] is False
        assert current["freeze_origin"] == "PRE_CURRENT_ENGINEERING_ACTIVATION"
        return
    if mode == "OPERATOR_SELECTED_TARGET":
        assert current["target_contest"] >= 3055
        assert current["current_engineering_role"] == "PRODUCT_CERTIFIED_OPERATION"
        assert current["parallel_locked_experiment"] is None
        assert current["parallel_attempts_must_be_counted_separately"] is False
        if current["status"] == "FROZEN":
            assert current["freeze_sha256"] != LEGACY_FREEZE
            assert current["freeze_origin"] == "CURRENT_ENGINEERING_EPOCH"
            assert current["current_engineering_generation_authority"] is True
        return
    assert mode == "NEW_ENGINEERING_EPOCH"
    assert current["target_contest"] >= 3055
    assert current["parallel_locked_experiment"] is None
    if current["status"] == "FROZEN":
        assert current["freeze_sha256"] != LEGACY_FREEZE
        assert current["freeze_origin"] != "PRE_CURRENT_ENGINEERING_ACTIVATION"


def test_authority_lock_lifecycle_is_verifiable_before_or_after_closure():
    live = ROOT / "SMART_PROSPECTIVE_AUTHORITY_LOCK.json"
    closure = ROOT / "SMART_PROSPECTIVE_AUTHORITY_CLOSURE_3054.json"
    if live.is_file():
        static_lock = verify_lock(live, root=None)
        assert static_lock["experiment_authority"]["freeze_sha256"] == LEGACY_FREEZE
        evidence = adjudicated_lock_evidence(live, root=ROOT)
        assert evidence["freeze_sha256"] == LEGACY_FREEZE
    else:
        closed = verify_closure(closure, root=ROOT)
        assert closed["archived_lock_sha256"] == closed["lock_sha256"]
        assert closed["retroactive_rewrite"] is False
