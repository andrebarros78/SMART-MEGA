import hashlib
import json
from pathlib import Path

import pytest

import smart_full_process_pipeline as fp
import smart_operator as operator
from smart_learning_epoch_reset import SCHEMA as EPOCH_SCHEMA, write_active_epoch


def _ledger(events):
    return {"schema": "SMART_SIGNAL_LEDGER_1", "events": events, "rules": {}}


def test_operator_seeded_ledger_is_valid_pre_freeze_baseline(tmp_path):
    canonical = tmp_path / "SMART_SIGNAL_LEDGER.json"
    epoch = tmp_path / "runtime" / "learning_epochs" / "e1"
    epoch.mkdir(parents=True)
    ledger = epoch / "SMART_SIGNAL_LEDGER.json"
    payload = json.dumps(_ledger([{"event_type": "ADJUDICATION", "target_contest": 3055}])).encode()
    canonical.write_bytes(payload); ledger.write_bytes(payload)
    sha = fp.sha256_file(ledger)
    active = {"operator_selected_target": True, "canonical_ledger_seed_sha256": sha, "canonical_ledger_seed_event_count": 1}
    assert fp._pre_freeze_ledger_checks(tmp_path, active, ledger, fp.load_ledger(ledger), 3056) == {"ledger_baseline_integrity": True, "pre_freeze_target_events_absent": True}


def test_operator_seeded_ledger_fails_closed_on_drift_and_target_event(tmp_path):
    canonical = tmp_path / "SMART_SIGNAL_LEDGER.json"
    epoch = tmp_path / "runtime" / "learning_epochs" / "e1"; epoch.mkdir(parents=True)
    ledger = epoch / "SMART_SIGNAL_LEDGER.json"
    base = _ledger([{"event_type": "ADJUDICATION", "target_contest": 3055}])
    payload = json.dumps(base).encode(); canonical.write_bytes(payload); ledger.write_bytes(payload)
    sha = fp.sha256_file(ledger)
    active = {"operator_selected_target": True, "canonical_ledger_seed_sha256": sha, "canonical_ledger_seed_event_count": 1}
    contaminated = _ledger(base["events"] + [{"event_type": "FREEZE", "target_contest": 3056}])
    ledger.write_text(json.dumps(contaminated), encoding="utf-8")
    checks = fp._pre_freeze_ledger_checks(tmp_path, active, ledger, fp.load_ledger(ledger), 3056)
    assert checks == {"ledger_baseline_integrity": False, "pre_freeze_target_events_absent": False}


def _make_reset_ready(tmp_path, events):
    canonical = tmp_path / "SMART_SIGNAL_LEDGER.json"
    epoch = tmp_path / "runtime" / "learning_epochs" / "operator-3056-test"; epoch.mkdir(parents=True)
    ledger = epoch / "SMART_SIGNAL_LEDGER.json"; data = epoch / "Mega-Sena_cutoff_3055.xlsx"
    payload = json.dumps(_ledger(events)).encode(); canonical.write_bytes(payload); ledger.write_bytes(payload); data.write_bytes(b"snapshot")
    seed_sha = operator.sha256_file(ledger); active_path = tmp_path / "SMART_ACTIVE_EPOCH.json"
    write_active_epoch(active_path, {
        "schema": EPOCH_SCHEMA, "status": "RESET_READY", "project": "SMART-MEGA", "epoch_id": "operator-3056-test",
        "operator_selected_target": True,
        "state_paths": {"ledger": str(ledger.relative_to(tmp_path)), "state": str((epoch/'state.json').relative_to(tmp_path)), "activation_authority": str((epoch/'auth.json').relative_to(tmp_path)), "expansion_registry": str((epoch/'exp.json').relative_to(tmp_path)), "freeze": str((epoch/'freeze.json').relative_to(tmp_path))},
        "data_file": str(data.relative_to(tmp_path)), "data_sha256": operator.sha256_file(data), "immutable_history_snapshot": True,
        "cutoff_contest": 3055, "target_contest": 3056, "result_used": False, "freeze_authority": None,
        "canonical_ledger_seed_sha256": seed_sha, "canonical_ledger_seed_event_count": len(events),
    })
    return active_path, ledger, data


def test_withdraw_preserves_reset_ready_epoch_and_removes_only_pointer(tmp_path):
    active_path, ledger, data = _make_reset_ready(tmp_path, [{"event_type": "ADJUDICATION", "target_contest": 3055}])
    result = operator.withdraw_pre_freeze_operation(tmp_path, 3056)
    assert result["status"] == "WITHDRAWN_PRE_FREEZE"
    assert result["active_pointer_removed"] is True
    assert not active_path.exists()
    assert ledger.is_file() and data.is_file()
    proof = tmp_path / result["proof_file"]
    assert proof.is_file()
    doc = json.loads(proof.read_text(encoding="utf-8")); observed=doc.pop("sha256")
    assert observed == hashlib.sha256(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def test_withdraw_refuses_epoch_with_current_target_event(tmp_path):
    active_path, _, _ = _make_reset_ready(tmp_path, [{"event_type": "FREEZE", "target_contest": 3056}])
    with pytest.raises(RuntimeError, match="pre-freeze withdrawal blocked"):
        operator.withdraw_pre_freeze_operation(tmp_path, 3056)
    assert active_path.is_file()



def test_withdraw_rejects_non_operator_selected_epoch(tmp_path):
    active_path, _, _ = _make_reset_ready(tmp_path, [])
    doc = json.loads(active_path.read_text(encoding="utf-8"))
    doc.pop("sha256", None)
    doc["operator_selected_target"] = False
    write_active_epoch(active_path, doc)
    with pytest.raises(ValueError, match="limited to operator-selected epochs"):
        operator.withdraw_pre_freeze_operation(tmp_path, 3056)


def test_withdraw_rejects_target_mismatch(tmp_path):
    _make_reset_ready(tmp_path, [])
    with pytest.raises(ValueError, match="does not match withdrawal target"):
        operator.withdraw_pre_freeze_operation(tmp_path, 3057)


def test_withdraw_rejects_archive_hash_mismatch(tmp_path, monkeypatch):
    active_path, _, _ = _make_reset_ready(tmp_path, [])
    monkeypatch.setattr(operator, "_archive_active", lambda root, active_path: "0" * 64)
    with pytest.raises(RuntimeError, match="archive mismatch"):
        operator.withdraw_pre_freeze_operation(tmp_path, 3056)
    assert active_path.is_file()


def test_withdraw_fails_if_active_pointer_survives_unlink(tmp_path, monkeypatch):
    active_path, _, _ = _make_reset_ready(tmp_path, [])
    original_unlink = Path.unlink
    def guarded_unlink(self, *args, **kwargs):
        if self == active_path:
            return None
        return original_unlink(self, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", guarded_unlink)
    with pytest.raises(RuntimeError, match="active epoch pointer removal failed"):
        operator.withdraw_pre_freeze_operation(tmp_path, 3056)
    assert active_path.is_file()


def test_main_routes_withdraw_without_mutating_real_operation(monkeypatch, capsys):
    calls = {}
    def fake_withdraw(root, target):
        calls["root"] = root
        calls["target"] = target
        return {"status": "WITHDRAWN_PRE_FREEZE", "target_contest": target}
    monkeypatch.setattr(operator, "withdraw_pre_freeze_operation", fake_withdraw)
    operator.main(["withdraw", "--target", "3056"])
    assert calls["target"] == 3056
    assert calls["root"].name == "SMART-MEGA"
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "WITHDRAWN_PRE_FREEZE"
