from __future__ import annotations

import hashlib
import json

from smart_startup_reconciler import _valid_withdrawn_cycle_hold


def _hashed(path, doc):
    body = dict(doc)
    body["sha256"] = hashlib.sha256(
        json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(root):
    proof_path = root / "SMART_STATE_ARCHIVE" / "withdraw-3068.json"
    proof = {
        "schema": "SMART_OPERATOR_PRE_FREEZE_WITHDRAWAL_1",
        "status": "WITHDRAWN_PRE_FREEZE",
        "target_contest": 3068,
        "epoch_id": "epoch-test-3068",
        "active_pointer_removed": True,
        "checks": {"freeze_authority_absent": True, "reset_ready": True,
                   "canonical_ledger_unchanged_since_prepare": True},
    }
    proof_digest = _hashed(proof_path, proof)
    lifecycle = {
        "state": "HOLD", "target_contest": 3068, "completed_contest": 3067,
        "previous_state": "PREPARED", "transition_actor": "operator_withdraw_pre_freeze",
        "evidence": {"pre_freeze_withdrawal": {
            "file": proof_path.relative_to(root).as_posix(), "sha256": proof_digest}},
    }
    authority = {"status": "CONSUMED_FOR_PREPARE", "target_contest": 3068,
                 "consumed": True, "prepared_epoch_id": "epoch-test-3068"}
    return lifecycle, authority


def test_same_target_consumed_authority_allowed_only_after_proved_withdrawal(tmp_path):
    lifecycle, authority = _fixture(tmp_path)
    assert _valid_withdrawn_cycle_hold(tmp_path, lifecycle, authority)


def test_wrong_epoch_or_missing_proof_fails_closed(tmp_path):
    lifecycle, authority = _fixture(tmp_path)
    authority["prepared_epoch_id"] = "different-epoch"
    assert not _valid_withdrawn_cycle_hold(tmp_path, lifecycle, authority)
    authority["prepared_epoch_id"] = "epoch-test-3068"
    lifecycle["evidence"]["pre_freeze_withdrawal"]["sha256"] = "0" * 64
    assert not _valid_withdrawn_cycle_hold(tmp_path, lifecycle, authority)


def test_unwithdrawn_active_epoch_is_not_hold(tmp_path):
    lifecycle, authority = _fixture(tmp_path)
    (tmp_path / "SMART_ACTIVE_EPOCH.json").write_text("{}", encoding="utf-8")
    assert not _valid_withdrawn_cycle_hold(tmp_path, lifecycle, authority)
