"""Operator idempotency context builders, separated from lifecycle orchestration.

All authority lookups are injected by the operator facade to preserve exact
runtime state, immutable evidence, and monkeypatch compatibility.
"""
from __future__ import annotations

from pathlib import Path


def authorization_payload(root, target, args, kwargs, *, load_lifecycle, authority_path, authority_schema, load_hashed_doc, find_withdrawal):
    """Scope same-target reauthorization to its verified technical withdrawal.

    The ordinary first-authorization key is preserved. A consumed authority
    must never replay that prior success after a proven pre-freeze withdrawal.
    """
    payload = {"args": [str(x) for x in args],
               "kwargs": {k: str(v) for k, v in sorted(kwargs.items())}}
    root = Path(root).resolve()
    lifecycle = load_lifecycle(root)
    authority_path = root / authority_path
    if (lifecycle.get("state") != "HOLD"
            or int(lifecycle.get("target_contest") or -1) != int(target)
            or not authority_path.is_file()):
        return payload
    existing = load_hashed_doc(authority_path, authority_schema)
    if int(existing.get("target_contest", -1)) != int(target) or existing.get("consumed") is not True:
        return payload
    epoch_id = str(existing.get("prepared_epoch_id") or "")
    proof = find_withdrawal(root, int(target), epoch_id)
    if proof is None:
        raise FileExistsError("consumed next-cycle authority cannot be replayed without withdrawal proof")
    proof_path, evidence = proof
    payload["withdrawal_reauthorization"] = {
        "prior_consumed_authority_sha256": existing["sha256"],
        "withdrawal_proof_sha256": evidence["sha256"],
        "withdrawn_epoch_id": epoch_id,
        "withdrawal_proof_file": str(proof_path.relative_to(root)).replace("\\", "/"),
    }
    return payload



def prepare_payload(root, target, args, kwargs, *, load_lifecycle, authority_path, authority_schema, load_hashed_doc):
    """A new authorized cycle must not replay an old, withdrawn prepare."""
    payload = {"args": [str(x) for x in args],
               "kwargs": {k: str(v) for k, v in sorted(kwargs.items())}}
    root = Path(root).resolve()
    lifecycle = load_lifecycle(root)
    authority_path = root / authority_path
    if (lifecycle.get("state") != "AUTHORIZED"
            or int(lifecycle.get("target_contest") or -1) != int(target)
            or not authority_path.is_file()):
        return payload
    authority = load_hashed_doc(authority_path, authority_schema)
    if (authority.get("status") != "AUTHORIZED" or authority.get("consumed") is not False
            or int(authority.get("target_contest", -1)) != int(target)):
        return payload
    payload["authorized_cycle_sha256"] = authority["sha256"]
    return payload

