"""Characterization of operator idempotency keys across reauthorization and prepare.

The helpers must not replay a consumed authority or bind an inactive authority
to a new prepare request. No real epoch is opened by these tests.
"""
from pathlib import Path
import pytest

from smart_operator_idempotency_context import (
    authorization_payload,
    prepare_payload,
)


AUTHORITY = "SMART_NEXT_CYCLE_AUTHORITY.json"
SCHEMA = "AUTHORITY_TEST_V1"


def _authorization(root, target, *, lifecycle, authority, proof=None, args=(), kwargs=None):
    return authorization_payload(
        root, target, args, kwargs or {},
        load_lifecycle=lambda _root: lifecycle,
        authority_path=AUTHORITY,
        authority_schema=SCHEMA,
        load_hashed_doc=lambda path, schema: authority,
        find_withdrawal=lambda _root, _target, _epoch: proof,
    )


def _prepare(root, target, *, lifecycle, authority, args=(), kwargs=None):
    return prepare_payload(
        root, target, args, kwargs or {},
        load_lifecycle=lambda _root: lifecycle,
        authority_path=AUTHORITY,
        authority_schema=SCHEMA,
        load_hashed_doc=lambda path, schema: authority,
    )


def test_authorization_base_payload_preserves_argument_order_and_sorts_keywords(tmp_path):
    payload = _authorization(
        tmp_path, 3078, lifecycle={"state": "PREPARED", "target_contest": 3078},
        authority={}, args=(10, "x"), kwargs={"z": 7, "a": None},
    )
    assert payload == {"args": ["10", "x"], "kwargs": {"a": "None", "z": "7"}}


def test_authorization_requires_existing_authority_before_adding_proof(tmp_path):
    payload = _authorization(
        tmp_path, 3078, lifecycle={"state": "HOLD", "target_contest": 3078},
        authority={"consumed": True}, proof=None,
    )
    assert payload == {"args": [], "kwargs": {}}


def test_authorization_cannot_replay_consumed_authority_without_withdrawal(tmp_path):
    (tmp_path / AUTHORITY).write_text("{}", encoding="utf-8")
    authority = {"target_contest": 3078, "consumed": True, "prepared_epoch_id": "epoch-a", "sha256": "a" * 64}
    with pytest.raises(FileExistsError, match="cannot be replayed without withdrawal proof"):
        _authorization(tmp_path, 3078, lifecycle={"state": "HOLD", "target_contest": 3078}, authority=authority)


def test_authorization_binds_withdrawal_to_exact_authority_and_proof(tmp_path):
    (tmp_path / AUTHORITY).write_text("{}", encoding="utf-8")
    proof_path = tmp_path / "archive" / "withdrawal.json"
    authority = {"target_contest": 3078, "consumed": True, "prepared_epoch_id": "epoch-a", "sha256": "a" * 64}
    payload = _authorization(
        tmp_path, 3078,
        lifecycle={"state": "HOLD", "target_contest": 3078},
        authority=authority,
        proof=(proof_path, {"sha256": "b" * 64}),
    )
    assert payload["withdrawal_reauthorization"] == {
        "prior_consumed_authority_sha256": "a" * 64,
        "withdrawal_proof_sha256": "b" * 64,
        "withdrawn_epoch_id": "epoch-a",
        "withdrawal_proof_file": "archive/withdrawal.json",
    }


def test_authorization_ignores_unconsumed_or_other_target_authority(tmp_path):
    (tmp_path / AUTHORITY).write_text("{}", encoding="utf-8")
    for authority in (
        {"target_contest": 3078, "consumed": False},
        {"target_contest": 3077, "consumed": True},
    ):
        assert _authorization(
            tmp_path, 3078, lifecycle={"state": "HOLD", "target_contest": 3078},
            authority=authority,
        ) == {"args": [], "kwargs": {}}


def test_prepare_requires_authorized_lifecycle_and_existing_authority(tmp_path):
    authority = {"target_contest": 3078, "status": "AUTHORIZED", "consumed": False, "sha256": "a" * 64}
    assert _prepare(tmp_path, 3078, lifecycle={"state": "AUTHORIZED", "target_contest": 3078}, authority=authority) == {
        "args": [], "kwargs": {},
    }
    (tmp_path / AUTHORITY).write_text("{}", encoding="utf-8")
    assert _prepare(tmp_path, 3078, lifecycle={"state": "HOLD", "target_contest": 3078}, authority=authority) == {
        "args": [], "kwargs": {},
    }


@pytest.mark.parametrize("changed", [
    {"status": "RESERVED"},
    {"consumed": True},
    {"target_contest": 3077},
])
def test_prepare_ignores_inactive_or_incompatible_authority(tmp_path, changed):
    (tmp_path / AUTHORITY).write_text("{}", encoding="utf-8")
    authority = {"target_contest": 3078, "status": "AUTHORIZED", "consumed": False, "sha256": "a" * 64}
    authority.update(changed)
    assert _prepare(tmp_path, 3078, lifecycle={"state": "AUTHORIZED", "target_contest": 3078}, authority=authority) == {
        "args": [], "kwargs": {},
    }


def test_prepare_key_binds_only_exact_authorized_cycle_sha(tmp_path):
    (tmp_path / AUTHORITY).write_text("{}", encoding="utf-8")
    authority = {"target_contest": 3078, "status": "AUTHORIZED", "consumed": False, "sha256": "a" * 64}
    payload = _prepare(
        tmp_path, 3078, lifecycle={"state": "AUTHORIZED", "target_contest": 3078},
        authority=authority, args=("prepare",), kwargs={"force": False},
    )
    assert payload == {
        "args": ["prepare"],
        "kwargs": {"force": "False"},
        "authorized_cycle_sha256": "a" * 64,
    }
