"""Pure state transitions for operator-controlled next-cycle authority.

The caller owns lifecycle authorization, epoch verification, CAS persistence,
and timestamp sourcing. These functions never write evidence or state.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


def reserve_document(
    authority: dict[str, Any],
    target: int,
    transaction_id: str,
    prepared_epoch_id: str,
    *,
    schema: str,
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    original_sha = authority["sha256"]
    updated = dict(authority)
    updated.setdefault("schema", schema)
    updated.setdefault("target_contest", int(target))
    updated.update({
        "status": "RESERVED",
        "consumed": False,
        "reservation_transaction_id": str(transaction_id),
        "reserved_utc": utc_now(),
        "prepared_epoch_id": str(prepared_epoch_id),
        "authority_sha256_before_reservation": original_sha,
    })
    return updated


def release_document(
    authority: dict[str, Any],
    target: int,
    transaction_id: str,
    *,
    reason: str,
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    if authority.get("status") != "RESERVED" or authority.get("consumed") is not False:
        raise PermissionError("next-cycle authority is not reserved")
    if int(authority.get("target_contest", -1)) != int(target):
        raise PermissionError("reserved authority target mismatch")
    if authority.get("reservation_transaction_id") != str(transaction_id):
        raise PermissionError("reserved authority transaction mismatch")
    reservation_sha = authority["sha256"]
    updated = dict(authority)
    updated.update({
        "status": "AUTHORIZED",
        "reservation_transaction_id": None,
        "reserved_utc": None,
        "prepared_epoch_id": None,
        "reservation_released_utc": utc_now(),
        "reservation_release_reason": str(reason),
        "authority_sha256_before_reservation_release": reservation_sha,
    })
    return updated


def verify_consumable_reservation(
    authority: dict[str, Any],
    target: int,
    transaction_id: str,
    prepared_epoch_id: str,
    active: dict[str, Any],
) -> None:
    if authority.get("status") != "RESERVED" or authority.get("consumed") is not False:
        raise PermissionError("next-cycle authority is not reserved for prepare")
    if int(authority.get("target_contest", -1)) != int(target):
        raise PermissionError("reserved authority target mismatch")
    if authority.get("reservation_transaction_id") != str(transaction_id):
        raise PermissionError("reserved authority transaction mismatch")
    if authority.get("prepared_epoch_id") != str(prepared_epoch_id):
        raise PermissionError("reserved authority epoch mismatch")
    if int(active.get("target_contest", -1)) != int(target) or active.get("epoch_id") != str(prepared_epoch_id):
        raise PermissionError("active epoch does not prove reserved authority materialization")


def consume_document(
    authority: dict[str, Any],
    transaction_id: str,
    prepared_epoch_id: str,
    active: dict[str, Any],
    *,
    utc_now: Callable[[], str],
) -> dict[str, Any]:
    reservation_sha = authority["sha256"]
    updated = dict(authority)
    updated.update({
        "status": "CONSUMED",
        "consumed": True,
        "consumed_utc": utc_now(),
        "consumption_transaction_id": str(transaction_id),
        "prepared_epoch_id": str(prepared_epoch_id),
        "active_epoch_sha256_at_consumption": active["sha256"],
        "authority_sha256_before_consumption": reservation_sha,
    })
    return updated
