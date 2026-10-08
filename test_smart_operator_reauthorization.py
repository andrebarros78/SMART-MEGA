from pathlib import Path
import json
import smart_operator as op


def _hashed(path: Path, payload: dict) -> dict:
    obj = dict(payload); obj["sha256"] = op._operator_sha256_json(obj)
    path.write_text(json.dumps(obj), encoding="utf-8")
    return obj


def _base(tmp_path: Path):
    (tmp_path / "SMART_STATE_ARCHIVE").mkdir()
    (tmp_path / "Mega-Sena.xlsx").write_bytes(b"history")
    review = tmp_path / "SMART_POST_RESULT_REVIEW_3059.json"; review.write_bytes(b"review")
    hold = _hashed(tmp_path / op.POST_RESULT_HOLD_PATH, {
        "schema": op.NEXT_CYCLE_HOLD_SCHEMA, "status": "AWAITING_OPERATOR_APPLY_OR_GENERATE",
        "completed_contest": 3059, "next_target": 3060, "review_file": review.name,
        "review_file_sha256": op.sha256_file(review), "review_sha256": "r"*64,
        "canonical_sha256_at_review": op.sha256_file(tmp_path / "Mega-Sena.xlsx"),
        "automatic_prepare_forbidden": True, "prepare_allowed": False,
    })
    return review, hold


def test_consumed_authority_reauthorizes_only_after_valid_withdrawal(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(op, "canonical_root", lambda root=None: Path(root).resolve())
    monkeypatch.setattr(op, "assert_lifecycle_state", lambda *a, **k: {"status": "PASS"})
    monkeypatch.setattr(op, "transition_lifecycle", lambda *a, **k: {"status": "AUTHORIZED", "sha256": "l" * 64})
    review, hold = _base(tmp_path)
    existing = _hashed(tmp_path / op.NEXT_CYCLE_AUTHORITY_PATH, {
        "schema": op.NEXT_CYCLE_AUTHORITY_SCHEMA, "status": "CONSUMED_FOR_PREPARE",
        "target_contest": 3060, "completed_contest": 3059, "review_file": review.name,
        "review_file_sha256": op.sha256_file(review), "review_sha256": hold["review_sha256"],
        "canonical_sha256": op.sha256_file(tmp_path / "Mega-Sena.xlsx"),
        "authorized_by": "USER_EXPLICIT_APPLY_OR_GENERATE", "authorized_utc": "x",
        "consumed": True, "consumed_utc": "y", "prepared_epoch_id": "e3060",
    })
    proof_payload = {
        "schema": "SMART_OPERATOR_PRE_FREEZE_WITHDRAWAL_1", "status": "WITHDRAWN_PRE_FREEZE",
        "target_contest": 3060, "epoch_id": "e3060", "active_pointer_removed": True,
        "reason": "PRE_FREEZE_TECHNICAL_CORRECTION", "checks": {"reset_ready": True, "freeze_authority_absent": True},
    }
    proof = _hashed(tmp_path / "SMART_STATE_ARCHIVE" / "operator_pre_freeze_withdrawal_x.json", proof_payload)
    out = op.authorize_next_cycle_operation.__wrapped__.__wrapped__(tmp_path, 3060)
    assert out["status"] == "AUTHORIZED" and out["consumed"] is False
    assert out["reauthorized_after_withdrawal"] is True
    assert out["prior_consumed_authority_sha256"] == existing["sha256"]
    assert out["withdrawal_proof_sha256"] == proof["sha256"]


def test_consumed_authority_without_withdrawal_proof_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(op, "canonical_root", lambda root=None: Path(root).resolve())
    monkeypatch.setattr(op, "assert_lifecycle_state", lambda *a, **k: {"status": "PASS"})
    monkeypatch.setattr(op, "transition_lifecycle", lambda *a, **k: {"status": "AUTHORIZED", "sha256": "l" * 64})
    import pytest
    review, hold = _base(tmp_path)
    _hashed(tmp_path / op.NEXT_CYCLE_AUTHORITY_PATH, {
        "schema": op.NEXT_CYCLE_AUTHORITY_SCHEMA, "status": "CONSUMED_FOR_PREPARE",
        "target_contest": 3060, "completed_contest": 3059, "review_file": review.name,
        "review_file_sha256": op.sha256_file(review), "review_sha256": hold["review_sha256"],
        "canonical_sha256": op.sha256_file(tmp_path / "Mega-Sena.xlsx"),
        "authorized_by": "USER_EXPLICIT_APPLY_OR_GENERATE", "authorized_utc": "x",
        "consumed": True, "consumed_utc": "y", "prepared_epoch_id": "e3060",
    })
    with pytest.raises(FileExistsError, match="withdrawal proof"):
        op.authorize_next_cycle_operation.__wrapped__.__wrapped__(tmp_path, 3060)


def test_operator_contract_declares_proof_bound_reauthorization() -> None:
    assert op.contract()["technical_withdrawal_allows_same_target_reauthorization_with_proof"] is True


def test_consumed_previous_authorization_replay_cannot_block_proven_reauthorization(tmp_path: Path, monkeypatch) -> None:
    """A prior idempotency record is not valid after a hash-bound withdrawal."""
    from smart_idempotency import make_key, commit, load

    monkeypatch.setattr(op, "canonical_root", lambda root=None: Path(root).resolve())
    monkeypatch.setattr(op, "assert_lifecycle_state", lambda *a, **k: {"status": "PASS"})
    monkeypatch.setattr(op, "transition_lifecycle", lambda *a, **k: {"status": "AUTHORIZED"})
    monkeypatch.setattr(op, "load_lifecycle", lambda root: {"state": "HOLD", "target_contest": 3060})
    review, hold = _base(tmp_path)
    existing = _hashed(tmp_path / op.NEXT_CYCLE_AUTHORITY_PATH, {
        "schema": op.NEXT_CYCLE_AUTHORITY_SCHEMA, "status": "CONSUMED_FOR_PREPARE",
        "target_contest": 3060, "completed_contest": 3059, "review_file": review.name,
        "review_file_sha256": op.sha256_file(review), "review_sha256": hold["review_sha256"],
        "canonical_sha256": op.sha256_file(tmp_path / "Mega-Sena.xlsx"),
        "authorized_by": "USER_EXPLICIT_APPLY_OR_GENERATE", "authorized_utc": "x",
        "consumed": True, "consumed_utc": "y", "prepared_epoch_id": "e3060",
    })
    old_key = make_key("AUTHORIZE", 3060, {"args": [], "kwargs": {}})
    commit(tmp_path, "AUTHORIZE", old_key, 3060,
           {"status": "AUTHORIZED", "consumed": False, "stale_old_authorization": True})
    proof = _hashed(tmp_path / "SMART_STATE_ARCHIVE" / "operator_pre_freeze_withdrawal_valid.json", {
        "schema": "SMART_OPERATOR_PRE_FREEZE_WITHDRAWAL_1", "status": "WITHDRAWN_PRE_FREEZE",
        "target_contest": 3060, "epoch_id": "e3060", "active_pointer_removed": True,
        "reason": "PRE_FREEZE_TECHNICAL_CORRECTION",
        "checks": {"reset_ready": True, "freeze_authority_absent": True},
    })
    out = op.authorize_next_cycle_operation.__wrapped__.__wrapped__(tmp_path, 3060)
    assert out["status"] == "AUTHORIZED" and out["consumed"] is False
    assert out["reauthorized_after_withdrawal"] is True
    assert out["prior_consumed_authority_sha256"] == existing["sha256"]
    assert out["withdrawal_proof_sha256"] == proof["sha256"]
    assert not out.get("stale_old_authorization")
    assert load(tmp_path, "AUTHORIZE", old_key)["result"]["stale_old_authorization"] is True


def test_consumed_replay_without_withdrawal_proof_must_fail_closed(tmp_path: Path, monkeypatch) -> None:
    import pytest
    from smart_idempotency import make_key, commit

    monkeypatch.setattr(op, "load_lifecycle", lambda root: {"state": "HOLD", "target_contest": 3060})
    review, hold = _base(tmp_path)
    _hashed(tmp_path / op.NEXT_CYCLE_AUTHORITY_PATH, {
        "schema": op.NEXT_CYCLE_AUTHORITY_SCHEMA, "status": "CONSUMED_FOR_PREPARE",
        "target_contest": 3060, "completed_contest": 3059, "review_file": review.name,
        "review_file_sha256": op.sha256_file(review), "review_sha256": hold["review_sha256"],
        "canonical_sha256": op.sha256_file(tmp_path / "Mega-Sena.xlsx"),
        "authorized_by": "USER_EXPLICIT_APPLY_OR_GENERATE", "authorized_utc": "x",
        "consumed": True, "consumed_utc": "y", "prepared_epoch_id": "e3060",
    })
    old_key = make_key("AUTHORIZE", 3060, {"args": [], "kwargs": {}})
    commit(tmp_path, "AUTHORIZE", old_key, 3060, {"status": "AUTHORIZED", "consumed": False})
    with pytest.raises(FileExistsError, match="withdrawal proof"):
        op.authorize_next_cycle_operation.__wrapped__.__wrapped__(tmp_path, 3060)


def test_reauthorized_prepare_uses_new_authority_not_withdrawn_previous_replay(tmp_path: Path, monkeypatch) -> None:
    from smart_idempotency import make_key, commit, load
    monkeypatch.setattr(op, "load_lifecycle", lambda root: {"state": "AUTHORIZED", "target_contest": 3060})
    original_key = make_key("PREPARE", 3060, {"args": [], "kwargs": {}})
    commit(tmp_path, "PREPARE", original_key, 3060,
           {"status": "RESET_READY", "stale_withdrawn_epoch": "operator-old"})
    authority = _hashed(tmp_path / op.NEXT_CYCLE_AUTHORITY_PATH, {
        "schema": op.NEXT_CYCLE_AUTHORITY_SCHEMA, "status": "AUTHORIZED",
        "target_contest": 3060, "consumed": False,
        "reauthorized_after_withdrawal": True,
    })
    payload = op._prepare_idempotency_payload(tmp_path, 3060, (), {})
    assert payload["authorized_cycle_sha256"] == authority["sha256"]
    new_key = make_key("PREPARE", 3060, payload)
    assert new_key != original_key
    assert load(tmp_path, "PREPARE", new_key) is None
    assert load(tmp_path, "PREPARE", original_key)["result"]["stale_withdrawn_epoch"] == "operator-old"
