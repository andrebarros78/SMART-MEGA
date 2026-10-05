import hashlib
import json

import pytest

import smart_operator as op
import smart_operational_lifecycle as lifecycle
from smart_learning_epoch_reset import SCHEMA, write_active_epoch


def prepared_epoch(root, *, frozen=False):
    epoch = root / "runtime" / "learning_epochs" / "fixture-121"
    epoch.mkdir(parents=True)
    ledger = epoch / "SMART_SIGNAL_LEDGER.json"
    ledger.write_text(json.dumps({"schema": "SMART_SIGNAL_LEDGER_1", "events": []}), encoding="utf-8")
    paths = {"ledger": ledger.relative_to(root).as_posix(),
             "state": (epoch / "state.json").relative_to(root).as_posix(),
             "activation_authority": (epoch / "activation.json").relative_to(root).as_posix(),
             "expansion_registry": (epoch / "expansion.json").relative_to(root).as_posix(),
             "freeze": (epoch / "freeze.json").relative_to(root).as_posix()}
    freeze = epoch / "freeze.json"
    if frozen:
        freeze.write_bytes(b"immutable frozen forecast")
    active = write_active_epoch(root / "SMART_ACTIVE_EPOCH.json", {
        "schema": SCHEMA, "project": "SMART-MEGA", "status": "FROZEN" if frozen else "RESET_READY",
        "epoch_id": "fixture-121", "target_contest": 121, "cutoff_contest": 120, "result_used": False,
        "state_paths": paths, "canonical_ledger_seed_sha256": op.sha256_file(ledger),
        "freeze_authority": {"file": paths["freeze"], "sha256": op.sha256_file(freeze)} if frozen else None})
    lifecycle.initialize_from_legacy(root)
    return active, ledger, freeze


def test_real_interrupted_freeze_recovery_restores_prepared_without_mutating_seed(tmp_path):
    active, ledger, _ = prepared_epoch(tmp_path)
    before = ledger.read_bytes()
    lifecycle.transition(tmp_path, "PREPARED", "FREEZING", target_contest=121, actor="fixture")
    result = op.recover_interrupted_freeze_operation(tmp_path, 121)
    assert result["status"] == "RECOVERED_INTERRUPTED_FREEZE"
    assert lifecycle.load_lifecycle(tmp_path)["state"] == "PREPARED"
    assert ledger.read_bytes() == before
    assert op.verify_active_epoch(tmp_path / "SMART_ACTIVE_EPOCH.json") == active


def test_real_recovery_rejects_material_artifacts_and_preserves_freezing(tmp_path):
    _, ledger, _ = prepared_epoch(tmp_path)
    before = ledger.read_bytes()
    lifecycle.transition(tmp_path, "PREPARED", "FREEZING", target_contest=121, actor="fixture")
    (ledger.parent / "state.json").write_bytes(b"material state")
    with pytest.raises(RuntimeError, match="material artifacts exist"):
        op.recover_interrupted_freeze_operation(tmp_path, 121)
    assert lifecycle.load_lifecycle(tmp_path)["state"] == "FREEZING"
    assert ledger.read_bytes() == before


def test_real_frozen_replay_resolves_bound_path_and_preserves_freeze(tmp_path):
    active, _, freeze = prepared_epoch(tmp_path, frozen=True)
    before = freeze.read_bytes()
    result = op.freeze_operation(tmp_path, 121)
    assert result["status"] == "FROZEN" and result["idempotent_replay"] is True
    assert result["freeze_file"] == active["state_paths"]["freeze"]
    assert result["freeze_sha256"] == hashlib.sha256(before).hexdigest()
    assert freeze.read_bytes() == before


def test_real_frozen_replay_rejects_changed_artifact(tmp_path):
    _, _, freeze = prepared_epoch(tmp_path, frozen=True)
    freeze.write_bytes(b"changed forecast")
    with pytest.raises(ValueError, match="not bound"):
        op.freeze_operation(tmp_path, 121)
    assert freeze.read_bytes() == b"changed forecast"
