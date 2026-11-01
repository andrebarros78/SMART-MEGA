"""Characterization tests for the extracted operator authority-document boundary."""
from __future__ import annotations

import json

import pytest

from smart_crash_safe_io import atomic_write_text
from smart_operator_authority_documents import (
    find_valid_pre_freeze_withdrawal,
    load_hashed_doc,
    sha256_json,
    write_hashed_doc,
)


def test_hashed_document_round_trip_and_cas_revision(tmp_path):
    path = tmp_path / "authority.json"
    first = write_hashed_doc(path, {"schema": "TEST", "value": 1}, atomic_write_text=atomic_write_text)
    assert load_hashed_doc(path, "TEST") == first
    second = write_hashed_doc(
        path, {"schema": "TEST", "value": 2},
        expected_sha256=first["sha256"], atomic_write_text=atomic_write_text,
    )
    assert second["revision"] == 2
    assert second["previous_document_sha256"] == first["sha256"]
    assert load_hashed_doc(path, "TEST") == second


@pytest.mark.parametrize("damage", ["schema", "hash", "non_object"])
def test_hashed_document_rejects_corruption(tmp_path, damage):
    path = tmp_path / "authority.json"
    original = write_hashed_doc(path, {"schema": "TEST", "value": 1}, atomic_write_text=atomic_write_text)
    if damage == "schema":
        document = {**original, "schema": "WRONG"}
    elif damage == "hash":
        document = {**original, "value": 999}
    else:
        document = ["not-an-object"]
    path.write_text(json.dumps(document), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        load_hashed_doc(path, "TEST")
    assert path.read_bytes() == before


@pytest.mark.parametrize("race", ["create", "overwrite"])
def test_cas_conflict_never_overwrites_a_concurrent_document(tmp_path, race):
    path = tmp_path / "authority.json"
    first = None
    if race == "overwrite":
        first = write_hashed_doc(path, {"schema": "TEST", "value": 1}, atomic_write_text=atomic_write_text)

    concurrent = {"schema": "TEST", "value": "other", "revision": 9}
    concurrent["sha256"] = sha256_json(concurrent)
    concurrent_bytes = json.dumps(concurrent).encode("utf-8")

    def concurrent_write(temp, contents):
        atomic_write_text(temp, contents)
        path.write_bytes(concurrent_bytes)

    with pytest.raises(RuntimeError, match="CAS"):
        write_hashed_doc(
            path, {"schema": "TEST", "value": 2},
            expected_sha256=first["sha256"] if first else None,
            atomic_write_text=concurrent_write,
        )
    assert path.read_bytes() == concurrent_bytes
    assert not path.with_suffix(".json.tmp").exists()


def test_pre_freeze_withdrawal_requires_valid_proof_and_target(tmp_path):
    archive = tmp_path / "SMART_STATE_ARCHIVE"
    archive.mkdir()
    path = archive / "operator_pre_freeze_withdrawal_fixture.json"
    proof = {
        "schema": "SMART_OPERATOR_PRE_FREEZE_WITHDRAWAL_1",
        "status": "WITHDRAWN_PRE_FREEZE",
        "target_contest": 4,
        "epoch_id": "epoch",
        "active_pointer_removed": True,
        "reason": "PRE_FREEZE_TECHNICAL_CORRECTION",
        "checks": {"verified": True},
    }
    proof["sha256"] = sha256_json(proof)
    path.write_text(json.dumps(proof), encoding="utf-8")
    assert find_valid_pre_freeze_withdrawal(archive, 4, "epoch") == (path, proof)
    assert find_valid_pre_freeze_withdrawal(archive, 5, "epoch") is None
    proof["checks"]["verified"] = False
    path.write_text(json.dumps(proof), encoding="utf-8")
    assert find_valid_pre_freeze_withdrawal(archive, 4, "epoch") is None
