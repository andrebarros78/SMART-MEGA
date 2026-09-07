import inspect
import json
from datetime import datetime, timezone

import pytest
from pathlib import Path

from smart_champion_challenger import freeze_champion_challenger
from smart_engineering_activation import SCHEMA as ACTIVATION_SCHEMA, _sha256_json as activation_sha, _code_fingerprint, _target_draw_has_passed, verify_activation
from smart_learning_epoch_reset import reset_learning_epoch, verify_active_epoch
from smart_regression_evidence import sha256_file


def _activation(root: Path, data: Path) -> dict:
    doc = {
        "schema": ACTIVATION_SCHEMA,
        "status": "FULL_ENGINEERING_ACTIVATION",
        "phase": "PRE_FREEZE",
        "checks": {"synthetic_contract": True},
        "current_freeze_authority": None,
        "current_learning_state_authority": None,
        "code_fingerprint": _code_fingerprint(root),
        "pre_freeze_context": {
            "data_file": data.name,
            "data_sha256": sha256_file(data),
            "cutoff_contest": 100,
            "target_contest": 101,
        },
    }
    doc["sha256"] = activation_sha(doc)
    return doc


def test_new_engineering_epoch_is_isolated_when_no_unresolved_freeze_exists(tmp_path: Path):
    data = tmp_path / "Mega-Sena.xlsx"
    data.write_bytes(b"canonical-history-placeholder")
    activation = _activation(tmp_path, data)
    (tmp_path / "SMART_FULL_ACTIVATION_EPOCH.json").write_text(json.dumps(activation), encoding="utf-8")
    legacy = tmp_path / "SMART_SIGNAL_LEDGER.json"
    legacy.write_text("legacy-ledger-must-survive", encoding="utf-8")

    result = reset_learning_epoch(tmp_path)
    active = verify_active_epoch(tmp_path / "SMART_ACTIVE_EPOCH.json")
    epoch_ledger = tmp_path / active["state_paths"]["ledger"]

    assert result["reset_proof"]["status"] == "PASS"
    assert result["reset_proof"]["mode"] == "NEW_ENGINEERING_EPOCH"
    assert active["status"] == "RESET_READY"
    assert active["authority_mode"] == "NEW_ENGINEERING_EPOCH"
    assert json.loads(epoch_ledger.read_text(encoding="utf-8"))["events"] == []
    assert legacy.read_text(encoding="utf-8") == "legacy-ledger-must-survive"
    assert active["freeze_authority"] is None
    assert active["learning_state_authority"] is None
    snapshot = tmp_path / active["data_file"]
    assert snapshot.is_file()
    assert sha256_file(snapshot) == sha256_file(data)
    assert active["immutable_history_snapshot"] is True


def test_freeze_engine_accepts_epoch_isolated_authority_and_registry_paths():
    params = inspect.signature(freeze_champion_challenger).parameters
    assert "activation_authority_path" in params
    assert "expansion_registry_path" in params


def test_current_code_verification_rejects_post_activation_mutation(tmp_path: Path):
    data = tmp_path / "Mega-Sena.xlsx"
    data.write_bytes(b"canonical-history-placeholder")
    activation = _activation(tmp_path, data)
    path = tmp_path / "SMART_FULL_ACTIVATION_EPOCH.json"
    path.write_text(json.dumps(activation), encoding="utf-8")
    verify_activation(path, root=tmp_path, require_current_code=True)
    (tmp_path / "smart_late_change.py").write_text("VALUE = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint stale"):
        verify_activation(path, root=tmp_path, require_current_code=True)


def test_pre_freeze_activation_rejects_imported_prior_prediction_authority(tmp_path: Path):
    data = tmp_path / "Mega-Sena.xlsx"
    data.write_bytes(b"history")
    activation = _activation(tmp_path, data)
    activation["current_freeze_authority"] = {"sha256": "a" * 64}
    activation["sha256"] = activation_sha({k: v for k, v in activation.items() if k != "sha256"})
    path = tmp_path / "SMART_FULL_ACTIVATION_EPOCH.json"
    path.write_text(json.dumps(activation), encoding="utf-8")
    with pytest.raises(ValueError, match="cannot import prior freeze"):
        verify_activation(path)


def test_pre_freeze_activation_can_preserve_parallel_old_experiment_without_importing_it(tmp_path: Path):
    data = tmp_path / "Mega-Sena.xlsx"
    data.write_bytes(b"history")
    activation = _activation(tmp_path, data)
    activation["parallel_locked_experiment"] = {
        "target_contest": 101,
        "eligible_to_prove_post_freeze_engineering_version": False,
    }
    activation["parallel_attempts_must_be_counted_separately"] = True
    activation["sha256"] = activation_sha({k: v for k, v in activation.items() if k != "sha256"})
    path = tmp_path / "SMART_FULL_ACTIVATION_EPOCH.json"
    path.write_text(json.dumps(activation), encoding="utf-8")
    verified = verify_activation(path)
    assert verified["current_freeze_authority"] is None
    assert verified["parallel_locked_experiment"]["target_contest"] == 101


def test_target_draw_time_predicate_is_timezone_aware_and_fail_closed_after_deadline():
    schedule = {"scheduled_datetime": "2026-09-06T11:00:00-03:00"}
    before = datetime(2026, 9, 6, 13, 59, 59, tzinfo=timezone.utc)
    at_deadline = datetime(2026, 9, 6, 14, 0, 0, tzinfo=timezone.utc)
    assert _target_draw_has_passed(schedule, now_utc=before) is False
    assert _target_draw_has_passed(schedule, now_utc=at_deadline) is True
