from pathlib import Path
from smart_current_epoch_contract import resolve

ROOT = Path(__file__).resolve().parent
LEGACY_FREEZE = "503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816"


def test_current_epoch_contract_is_causal_and_not_legacy_inferred():
    d = resolve(ROOT)
    assert d["target_contest"] == d["cutoff_contest"] + 1
    assert d["result_used"] is False
    assert d["terminal_authority"] is False
    if d["status"] == "POST_RESULT_HOLD":
        assert d["post_result_hold"] is True
        assert d["authority_mode"] == "POST_RESULT_HOLD"
        assert d["freeze_authority_present"] is False
        assert d["freeze_sha256"] is None
        assert d["current_engineering_generation_authority"] is False
        assert d["generation_proof_valid"] is False
        assert d["prepare_allowed"] is False
        assert d["generation_allowed"] is False
        assert d["operator_command_required"] is True
        return
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
    mode = d["authority_mode"]
    if mode == "POST_RESULT_HOLD":
        assert d["status"] == "POST_RESULT_HOLD"
        assert d["target_contest"] >= 3055
        assert d["current_engineering_role"] == "POST_RESULT_ANALYSIS_HOLD"
        assert d["freeze_authority_present"] is False
        assert d["scientific_adjudication_authority"] is False
        assert d["current_engineering_generation_authority"] is False
        assert d["parallel_locked_experiment"] is None
        return
    if mode == "POST_ADJUDICATION_ROLLOVER_PENDING":
        assert d["status"] == "RESET_READY"
        assert d["target_contest"] == 3054
        assert d["current_engineering_role"] == "NON_AUTHORITATIVE_RECOVERY_STAGING"
        assert d["first_possible_authoritative_target_for_current_engineering"] == 3055
        assert d["freeze_authority_present"] is False
        assert d["scientific_adjudication_authority"] is False
        assert d["current_engineering_generation_authority"] is False
        assert d["parallel_experiment_adjudicated"] is True
        assert d["rollover_required"] is True
        assert d["parallel_locked_experiment"]["freeze_sha256"] == LEGACY_FREEZE
        return
    if mode == "CARRY_FORWARD_UNRESOLVED_PROSPECTIVE":
        assert d["status"] == "FROZEN"
        assert d["freeze_sha256"] == LEGACY_FREEZE
        assert d["scientific_adjudication_authority"] is True
        assert d["current_engineering_generation_authority"] is False
        assert d["freeze_origin"] == "PRE_CURRENT_ENGINEERING_ACTIVATION"
        return
    assert mode in {"NEW_ENGINEERING_EPOCH", "OPERATOR_SELECTED_TARGET"}
    assert d["target_contest"] >= 3055
    expected_role = "PRODUCT_CERTIFIED_OPERATION" if mode == "OPERATOR_SELECTED_TARGET" else "AUTHORITATIVE_CURRENT_EPOCH"
    assert d["current_engineering_role"] == expected_role
    assert d["first_possible_authoritative_target_for_current_engineering"] == d["target_contest"]
    assert d["parallel_locked_experiment"] is None
    if d["status"] == "RESET_READY":
        assert d["freeze_authority_present"] is False
        assert d["freeze_sha256"] is None
    else:
        assert d["freeze_sha256"] != LEGACY_FREEZE
        assert d["freeze_origin"] != "PRE_CURRENT_ENGINEERING_ACTIVATION"

import hashlib
import json
import shutil

import pytest

from smart_operational_lifecycle import _sha_json, initialize_from_legacy, transition


def _write_contract_evidence(path, payload):
    doc = dict(payload)
    doc["sha256"] = _sha_json(doc)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


@pytest.fixture
def authorized_without_epoch(tmp_path):
    shutil.copyfile(ROOT / "Mega-Sena.xlsx", tmp_path / "Mega-Sena.xlsx")
    data_sha = hashlib.sha256((tmp_path / "Mega-Sena.xlsx").read_bytes()).hexdigest()
    review_path = tmp_path / "SMART_POST_RESULT_REVIEW_3066.json"
    review = _write_contract_evidence(review_path, {
        "schema": "SMART_POST_RESULT_REVIEW_1",
        "status": "POST_RESULT_REVIEW_COMPLETE",
        "target_contest": 3066,
        "next_target": 3067,
        "stop_required": True,
        "terminal_state": "AWAITING_OPERATOR_APPLY_OR_GENERATE",
    })
    review_file_sha = hashlib.sha256(review_path.read_bytes()).hexdigest()
    _write_contract_evidence(tmp_path / "SMART_NEXT_CYCLE_HOLD.json", {
        "schema": "SMART_NEXT_CYCLE_HOLD_1",
        "status": "AWAITING_OPERATOR_APPLY_OR_GENERATE",
        "completed_contest": 3066,
        "next_target": 3067,
        "automatic_prepare_forbidden": True,
        "prepare_allowed": False,
        "generation_allowed": False,
        "operator_command_required": True,
        "required_command_semantics": "USER_EXPLICIT_APPLY_OR_GENERATE",
        "canonical_sha256_at_review": data_sha,
        "review_file": review_path.name,
        "review_file_sha256": review_file_sha,
        "review_sha256": review["sha256"],
    })
    initialize_from_legacy(tmp_path)
    authority = _write_contract_evidence(tmp_path / "SMART_NEXT_CYCLE_AUTHORITY.json", {
        "schema": "SMART_NEXT_CYCLE_AUTHORITY_1",
        "status": "AUTHORIZED",
        "target_contest": 3067,
        "completed_contest": 3066,
        "review_file": review_path.name,
        "review_file_sha256": review_file_sha,
        "review_sha256": review["sha256"],
        "canonical_sha256": data_sha,
        "authorized_by": "USER_EXPLICIT_APPLY_OR_GENERATE",
        "consumed": False,
        "prepared_epoch_id": None,
        "reservation_transaction_id": None,
        "consumption_transaction_id": None,
    })
    lifecycle = transition(tmp_path, "HOLD", "AUTHORIZED", target_contest=3067,
                           actor="test_authorized_epoch_contract")
    return tmp_path, authority, lifecycle


def test_authorized_cycle_resolves_before_preparation_without_granting_agent_authority(authorized_without_epoch):
    root, authority, lifecycle = authorized_without_epoch
    before = {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}
    current = resolve(root)
    assert current["lifecycle_state"] == "AUTHORIZED"
    assert current["lifecycle_sha256"] == lifecycle["sha256"]
    assert current["operator_prepare_authorized"] is True
    assert current["next_cycle_authority_sha256"] == authority["sha256"]
    assert current["status"] == "POST_RESULT_HOLD"
    assert current["current_engineering_role"] == "POST_RESULT_ANALYSIS_HOLD"
    assert current["epoch_id"] is None
    assert current["target_contest"] == 3067
    assert current["cutoff_contest"] == 3066
    for flag in ("prepare_allowed", "generation_allowed", "freeze_authority_present",
                 "current_engineering_generation_authority", "generation_proof_valid",
                 "scientific_adjudication_authority", "terminal_authority", "result_used"):
        assert current[flag] is False
    assert before == {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}


@pytest.mark.parametrize("field,value", [
    ("schema", "OTHER_SCHEMA"), ("status", "CONSUMED"), ("consumed", True),
    ("authorized_by", "AUTOMATIC_AGENT"), ("target_contest", 3068),
    ("completed_contest", 3065), ("canonical_sha256", "0" * 64),
    ("review_file", "../outside.json"), ("review_file_sha256", "0" * 64),
    ("review_sha256", "0" * 64), ("prepared_epoch_id", "old-epoch"),
    ("reservation_transaction_id", "unfinished-transaction"),
    ("consumption_transaction_id", "old-transaction"),
])
def test_authorized_cycle_rejects_incompatible_or_consumed_authority(authorized_without_epoch, field, value):
    root, authority, _ = authorized_without_epoch
    authority.pop("sha256")
    authority[field] = value
    _write_contract_evidence(root / "SMART_NEXT_CYCLE_AUTHORITY.json", authority)
    with pytest.raises(ValueError, match="next-cycle authority"):
        resolve(root)


@pytest.mark.parametrize("invalidity", ["missing", "tampered", "active_epoch", "lifecycle_target"])
def test_authorized_cycle_requires_bound_authority_and_no_premature_epoch(authorized_without_epoch, invalidity):
    root, _, lifecycle = authorized_without_epoch
    path = root / "SMART_NEXT_CYCLE_AUTHORITY.json"
    if invalidity == "missing":
        path.unlink()
    elif invalidity == "tampered":
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["target_contest"] = 3068
        path.write_text(json.dumps(doc), encoding="utf-8")
    elif invalidity == "active_epoch":
        (root / "SMART_ACTIVE_EPOCH.json").write_text("{}", encoding="utf-8")
    else:
        lifecycle.pop("sha256")
        lifecycle["target_contest"] = 3068
        _write_contract_evidence(root / "SMART_OPERATIONAL_LIFECYCLE.json", lifecycle)
    with pytest.raises(ValueError):
        resolve(root)


@pytest.mark.parametrize("state", ["PREPARING", "PREPARED", "FREEZING", "FROZEN"])
def test_prepared_or_frozen_lifecycle_still_requires_active_epoch(authorized_without_epoch, state):
    root, _, lifecycle = authorized_without_epoch
    lifecycle.pop("sha256")
    lifecycle["state"] = state
    _write_contract_evidence(root / "SMART_OPERATIONAL_LIFECYCLE.json", lifecycle)
    with pytest.raises(ValueError, match="requires an active operational epoch"):
        resolve(root)
