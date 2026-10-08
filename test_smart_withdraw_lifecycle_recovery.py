from __future__ import annotations

import hashlib
import json

import pytest

from smart_operational_lifecycle import LifecycleError, load_lifecycle, transition


def _write_hashed(path, document):
    body = dict(document)
    body["sha256"] = hashlib.sha256(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(root):
    doc = {
        "schema": "SMART_OPERATIONAL_LIFECYCLE_1", "state": "PREPARED", "revision": 4,
        "project": "SMART-MEGA", "effective_version": "6.3.2",
        "target_contest": 3068, "completed_contest": 3067, "previous_state": "PREPARING",
        "transition": "PREPARING_TO_PREPARED", "authority": "SINGLE_OPERATIONAL_LIFECYCLE",
        "evidence": {},
    }
    _write_hashed(root / "SMART_OPERATIONAL_LIFECYCLE.json", doc)
    proof_path = root / "SMART_STATE_ARCHIVE" / "withdraw.json"
    proof = {
        "schema": "SMART_OPERATOR_PRE_FREEZE_WITHDRAWAL_1",
        "status": "WITHDRAWN_PRE_FREEZE", "target_contest": 3068,
        "active_pointer_removed": True,
        "checks": {"reset_ready": True, "freeze_authority_absent": True,
                   "no_generated_freeze_artifacts": True},
    }
    digest = _write_hashed(proof_path, proof)
    return {"pre_freeze_withdrawal": {"file": proof_path.relative_to(root).as_posix(),
                                     "sha256": digest}}


def test_prepared_to_hold_requires_valid_withdrawal_and_preserves_target(tmp_path):
    evidence = _fixture(tmp_path)
    lifecycle = transition(tmp_path, "PREPARED", "HOLD", target_contest=3068,
                           completed_contest=3067, actor="operator_withdraw_pre_freeze",
                           evidence=evidence)
    assert lifecycle["state"] == "HOLD"
    assert lifecycle["target_contest"] == 3068
    assert lifecycle["completed_contest"] == 3067
    assert load_lifecycle(tmp_path)["state"] == "HOLD"


@pytest.mark.parametrize("actor,valid_proof", [
    ("some_other_actor", True),
    ("operator_withdraw_pre_freeze", False),
])
def test_unproven_withdrawal_fails_closed(tmp_path, actor, valid_proof):
    evidence = _fixture(tmp_path)
    if not valid_proof:
        evidence["pre_freeze_withdrawal"]["sha256"] = "0" * 64
    with pytest.raises(LifecycleError):
        transition(tmp_path, "PREPARED", "HOLD", target_contest=3068,
                   completed_contest=3067, actor=actor, evidence=evidence)
    assert load_lifecycle(tmp_path)["state"] == "PREPARED"


def test_cannot_withdraw_if_active_pointer_still_exists(tmp_path):
    evidence = _fixture(tmp_path)
    (tmp_path / "SMART_ACTIVE_EPOCH.json").write_text("{}", encoding="utf-8")
    with pytest.raises(LifecycleError):
        transition(tmp_path, "PREPARED", "HOLD", target_contest=3068,
                   completed_contest=3067, actor="operator_withdraw_pre_freeze",
                   evidence=evidence)
