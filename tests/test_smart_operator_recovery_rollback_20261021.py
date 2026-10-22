"""Injected I/O failures must not turn a missed result into predictive authority."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

import smart_operator as op
import smart_product_certification as certification
from test_smart_operator_failure_boundaries_20261021 import original, snapshot


@pytest.fixture
def missed_epoch(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "canonical_root", lambda root: tmp_path)
    active_path = tmp_path / op.ACTIVE_PATH
    active_path.write_bytes(b"completed prior epoch")
    canonical = tmp_path / "Mega-Sena.xlsx"
    canonical.write_bytes(b"history-through-three")
    ledger = tmp_path / "previous-ledger.json"
    ledger.write_text("{}")
    active = {"target_contest": 3, "operator_selected_target": True, "epoch_id": "prior", "state_paths": {"ledger": ledger.name}}
    previous = {"events": [{"event_type": "ADJUDICATION", "target_contest": 3}]}
    current = {"events": []}
    schedule = {"scheduled_datetime": "2026-01-01T21:00:00-03:00"}
    monkeypatch.setattr(certification, "verify_product_certification", lambda *a, **k: {"sha256": "c" * 64})
    monkeypatch.setattr(op, "verify_active_epoch", lambda path: active)
    monkeypatch.setattr(op, "load_ledger", lambda path: previous if Path(path) == ledger else current)
    monkeypatch.setattr(op, "reconcile_completed_epoch_ledger", lambda *a, **k: {"status": "ALREADY_RECONCILED"})
    monkeypatch.setattr(op, "advance_completed_epoch", lambda *a, **k: {"status": "ALREADY_CURRENT"})
    monkeypatch.setattr(op, "validate_target_against_history", lambda path, target: {"cutoff_contest": int(target) - 1})
    monkeypatch.setattr(op, "resolve_target_schedule", lambda *a: schedule)

    def ingest(source, through, proof, target, payload=None):
        Path(through).write_bytes(b"history-through-four")
        Path(proof).write_text(json.dumps({"target": target}))
        return {"source_sha256": op.sha256_file(source), "output_sha256": op.sha256_file(through), "actual_numbers": [1, 2, 3, 4, 5, 6]}

    monkeypatch.setattr(op, "ingest_official_result", ingest)
    return {"root": tmp_path, "canonical": canonical, "active_path": active_path, "active": active,
            "previous": previous, "current": current, "schedule": schedule,
            "now": datetime(2026, 1, 3, tzinfo=timezone.utc)}


@pytest.mark.parametrize("failure", ["missing_active", "wrong_prior", "not_operator", "no_adjudication", "proof_exists", "target_epoch", "target_events", "no_schedule", "naive_schedule", "naive_clock", "before_draw", "backup_changed", "output_exists", "archive_mismatch"])
def test_missed_recovery_refuses_unverified_inputs_without_consuming_epoch(missed_epoch, monkeypatch, failure):
    fixture = missed_epoch
    root, canonical, active_path = fixture["root"], fixture["canonical"], fixture["active_path"]
    now = fixture["now"]
    if failure == "missing_active":
        active_path.unlink()
    elif failure == "wrong_prior":
        fixture["active"]["target_contest"] = 2
    elif failure == "not_operator":
        fixture["active"]["operator_selected_target"] = False
    elif failure == "no_adjudication":
        fixture["previous"]["events"] = []
    elif failure == "proof_exists":
        (root / "SMART_MISSED_TARGET_RECOVERY_4.json").write_bytes(b"prior proof")
    elif failure == "target_epoch":
        (root / "runtime/learning_epochs/operator-4-existing").mkdir(parents=True)
    elif failure == "target_events":
        (root / "SMART_SIGNAL_LEDGER.json").write_text("{}")
        fixture["current"]["events"] = [{"event_type": "FREEZE", "target_contest": 4}]
    elif failure == "no_schedule":
        fixture["schedule"].clear()
    elif failure == "naive_schedule":
        fixture["schedule"]["scheduled_datetime"] = "2026-01-01T21:00:00"
    elif failure == "naive_clock":
        now = now.replace(tzinfo=None)
    elif failure == "before_draw":
        now = datetime(2025, 12, 31, tzinfo=timezone.utc)
    elif failure in {"backup_changed", "output_exists"}:
        archive = root / "SMART_STATE_ARCHIVE/missed-unprepared-4"
        archive.mkdir(parents=True)
        path = archive / (f"Mega-Sena.before.{op.sha256_file(canonical)}.xlsx" if failure == "backup_changed" else "Mega-Sena_through_4.xlsx")
        path.write_bytes(b"prior evidence must survive")
    else:
        monkeypatch.setattr(op, "_archive_active", lambda *a: "0" * 64)
    before = snapshot(root)
    with pytest.raises((ValueError, RuntimeError, FileExistsError)):
        original(op.recover_missed_unprepared_operation)(root, 4, now_utc=now)
    assert canonical.read_bytes() == b"history-through-three"
    if failure != "missing_active":
        assert active_path.read_bytes() == b"completed prior epoch"
    after = snapshot(root)
    assert all(after.get(name) == value for name, value in before.items())
    assert not (root / "SMART_NEXT_CYCLE_AUTHORITY.json").exists()


@pytest.mark.parametrize("failure", ["ingest_hash", "temporary_copy", "post_replace", "proof_commit", "active_pointer_race"])
def test_missed_recovery_rolls_back_canonical_and_active_on_partial_io_failure(missed_epoch, monkeypatch, failure):
    fixture = missed_epoch
    root, canonical, active_path = fixture["root"], fixture["canonical"], fixture["active_path"]
    copy2, replace, path_replace, unlink = op.shutil.copy2, op.os.replace, Path.replace, Path.unlink
    ingest = op.ingest_official_result

    def fault_ingest(*args, **kwargs):
        result = ingest(*args, **kwargs)
        if failure == "ingest_hash":
            result["source_sha256"] = "0" * 64
        return result

    def fault_copy(source, destination, *args, **kwargs):
        result = copy2(source, destination, *args, **kwargs)
        if failure == "temporary_copy" and Path(destination).name.startswith("Mega-Sena.missed-unprepared."):
            Path(destination).write_bytes(b"transfer corruption")
        return result

    def fault_replace(source, destination, *args, **kwargs):
        result = replace(source, destination, *args, **kwargs)
        if failure == "post_replace" and Path(destination) == canonical:
            canonical.write_bytes(b"corrupted final write")
        return result

    def fault_path_replace(source, destination):
        if failure == "proof_commit" and Path(destination).name == "SMART_MISSED_TARGET_RECOVERY_4.json":
            raise OSError("proof persistence unavailable")
        return path_replace(source, destination)

    def fault_unlink(path, *args, **kwargs):
        result = unlink(path, *args, **kwargs)
        if failure == "active_pointer_race" and path == active_path:
            active_path.write_bytes(b"completed prior epoch")
        return result

    monkeypatch.setattr(op, "ingest_official_result", fault_ingest)
    monkeypatch.setattr(op.shutil, "copy2", fault_copy)
    monkeypatch.setattr(op.os, "replace", fault_replace)
    monkeypatch.setattr(Path, "replace", fault_path_replace)
    monkeypatch.setattr(Path, "unlink", fault_unlink)
    with pytest.raises((OSError, RuntimeError)):
        original(op.recover_missed_unprepared_operation)(root, 4, now_utc=fixture["now"])
    assert canonical.read_bytes() == b"history-through-three"
    assert active_path.read_bytes() == b"completed prior epoch"
    assert not (root / "SMART_MISSED_TARGET_RECOVERY_4.json").exists()
    assert not (root / "SMART_MISSED_TARGET_RECOVERY_4.json.tmp").exists()
    assert not list(root.glob("Mega-Sena.missed-unprepared.*.tmp.xlsx"))
    archive = root / "SMART_STATE_ARCHIVE/missed-unprepared-4"
    assert not (archive / "Mega-Sena_through_4.xlsx").exists()
    assert not (archive / "SMART_OFFICIAL_RESULT_4_MISSED_UNPREPARED.json").exists()
    assert not (root / "SMART_NEXT_CYCLE_AUTHORITY.json").exists()


def test_missed_recovery_accepts_prior_canonical_events_without_creating_a_forecast(missed_epoch):
    fixture = missed_epoch
    root = fixture["root"]
    (root / "SMART_SIGNAL_LEDGER.json").write_text("{}")
    fixture["current"]["events"] = [{"event_type": "ADJUDICATION", "target_contest": 3}]
    result = original(op.recover_missed_unprepared_operation)(root, 4, now_utc=fixture["now"])
    assert result["status"] == "RECOVERED_NO_PREPARED_EPOCH"
    assert result["prediction_authority_created"] is False and result["prospective_attempt_counted"] is False
    assert result["result_used_for_prediction"] is False and result["generation_authority_created"] is False
    assert fixture["canonical"].read_bytes() == b"history-through-four"
    assert not fixture["active_path"].exists() and not (root / "SMART_NEXT_CYCLE_AUTHORITY.json").exists()
