"""Characterization tests for authority reservation, release, and consumption.

These helpers build detached documents: no filesystem writes, no lifecycle
transitions, and no promotion of a scientific model.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from smart_operator_authority_transitions import (
    reserve_document,
    release_document,
    verify_consumable_reservation,
    consume_document,
)

TARGET = 3079
TRANSACTION = "prepare-transaction-a"
EPOCH = "epoch-a"
SHA = "a" * 64
NOW = "2026-11-01T16:30:00+00:00"


def _authorized():
    return {
        "status": "AUTHORIZED",
        "target_contest": TARGET,
        "consumed": False,
        "sha256": SHA,
        "operator_evidence": "immutable",
    }


def _reserved():
    result = reserve_document(
        _authorized(), TARGET, TRANSACTION, EPOCH,
        schema="SMART_AUTH_TEST_1", utc_now=lambda: NOW,
    )
    result["sha256"] = "b" * 64
    return result


def _active():
    return {"target_contest": TARGET, "epoch_id": EPOCH, "sha256": "c" * 64}


def test_reserve_preserves_original_and_hash_lineage():
    original = _authorized()
    snapshot = deepcopy(original)
    out = reserve_document(
        original, TARGET, TRANSACTION, EPOCH,
        schema="SMART_AUTH_TEST_1", utc_now=lambda: NOW,
    )
    assert original == snapshot
    assert out == {
        **original,
        "schema": "SMART_AUTH_TEST_1",
        "status": "RESERVED",
        "consumed": False,
        "reservation_transaction_id": TRANSACTION,
        "reserved_utc": NOW,
        "prepared_epoch_id": EPOCH,
        "authority_sha256_before_reservation": SHA,
    }


def test_reserve_sets_missing_schema_and_target_but_does_not_replace_existing():
    source = {"sha256": SHA, "schema": "ALREADY_SET", "target_contest": TARGET + 1}
    out = reserve_document(source, TARGET, TRANSACTION, EPOCH, schema="FALLBACK", utc_now=lambda: NOW)
    assert out["schema"] == "ALREADY_SET"
    assert out["target_contest"] == TARGET + 1
    assert source == {"sha256": SHA, "schema": "ALREADY_SET", "target_contest": TARGET + 1}


@pytest.mark.parametrize("changed,reason", [
    ({"status": "AUTHORIZED"}, "not reserved"),
    ({"consumed": True}, "not reserved"),
    ({"target_contest": TARGET + 1}, "target mismatch"),
    ({"reservation_transaction_id": "someone-else"}, "transaction mismatch"),
])
def test_release_rejects_invalid_reservations_without_calling_clock(changed, reason):
    source = _reserved()
    source.update(changed)
    original = deepcopy(source)
    with pytest.raises(PermissionError, match=reason):
        release_document(source, TARGET, TRANSACTION, reason="rollback", utc_now=lambda: pytest.fail("clock called before validation"))
    assert source == original


def test_release_restores_authorized_and_retains_audit_lineage():
    original = _reserved()
    original_copy = deepcopy(original)
    out = release_document(original, TARGET, TRANSACTION, reason="recovery", utc_now=lambda: NOW)
    assert original == original_copy
    assert out["status"] == "AUTHORIZED"
    assert out["consumed"] is False
    assert out["reservation_transaction_id"] is None
    assert out["reserved_utc"] is None
    assert out["prepared_epoch_id"] is None
    assert out["reservation_released_utc"] == NOW
    assert out["reservation_release_reason"] == "recovery"
    assert out["authority_sha256_before_reservation_release"] == "b" * 64
    assert out["operator_evidence"] == "immutable"


@pytest.mark.parametrize("changed,reason", [
    ({"status": "AUTHORIZED"}, "not reserved for prepare"),
    ({"consumed": True}, "not reserved for prepare"),
    ({"target_contest": TARGET + 1}, "target mismatch"),
    ({"reservation_transaction_id": "other"}, "transaction mismatch"),
    ({"prepared_epoch_id": "other"}, "epoch mismatch"),
])
def test_consume_rejects_invalid_reservation(changed, reason):
    source = _reserved()
    source.update(changed)
    with pytest.raises(PermissionError, match=reason):
        verify_consumable_reservation(source, TARGET, TRANSACTION, EPOCH, _active())


@pytest.mark.parametrize("changed", [
    {"target_contest": TARGET + 1},
    {"epoch_id": "unknown-epoch"},
])
def test_consume_rejects_unbound_active_epoch(changed):
    active = _active()
    active.update(changed)
    with pytest.raises(PermissionError, match="active epoch does not prove reserved"):
        verify_consumable_reservation(_reserved(), TARGET, TRANSACTION, EPOCH, active)


def test_consume_document_records_verified_epoch_without_mutating_inputs():
    original = _reserved()
    active = _active()
    saved_original, saved_active = deepcopy(original), deepcopy(active)
    verify_consumable_reservation(original, TARGET, TRANSACTION, EPOCH, active)
    out = consume_document(original, TRANSACTION, EPOCH, active, utc_now=lambda: NOW)
    assert original == saved_original
    assert active == saved_active
    assert out["status"] == "CONSUMED"
    assert out["consumed"] is True
    assert out["consumed_utc"] == NOW
    assert out["consumption_transaction_id"] == TRANSACTION
    assert out["prepared_epoch_id"] == EPOCH
    assert out["active_epoch_sha256_at_consumption"] == "c" * 64
    assert out["authority_sha256_before_consumption"] == "b" * 64
    assert out["operator_evidence"] == "immutable"


def test_consume_does_not_rewrite_unrelated_authority_evidence():
    original = _reserved()
    original["extra_evidence"] = {"proofs": [1, 2, 3]}
    out = consume_document(original, TRANSACTION, EPOCH, _active(), utc_now=lambda: NOW)
    assert out["extra_evidence"] == original["extra_evidence"]
    assert original["status"] == "RESERVED"
