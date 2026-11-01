"""Preflight integrity extraction characterization (read-only and fail-closed)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from smart_operator_preflight_integrity import (
    active_epoch_integrity_checks,
    classify_active_epoch,
)


TARGET = 3079
SHA = "a" * 64


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ledger(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != "SMART_SIGNAL_LEDGER_1":
        raise ValueError("bad ledger schema")
    return doc


def _case(root: Path):
    runtime = root / "epoch"
    runtime.mkdir()
    data = runtime / "snapshot.xlsx"
    data.write_bytes(b"history")
    canonical = root / "Mega-Sena.xlsx"
    canonical.write_bytes(b"history")
    ledger = runtime / "ledger.json"
    ledger.write_text(json.dumps({"schema": "SMART_SIGNAL_LEDGER_1", "events": []}), encoding="utf-8")
    active = {
        "immutable_history_snapshot": True,
        "cutoff_contest": TARGET - 1,
        "result_used": False,
        "data_file": "epoch/snapshot.xlsx",
        "data_sha256": _sha(data),
        "canonical_source_file": "Mega-Sena.xlsx",
        "canonical_source_sha256_at_prepare": _sha(canonical),
        "canonical_ledger_seed_sha256": _sha(ledger),
        "state_paths": {"ledger": "epoch/ledger.json", "freeze": "epoch/freeze.json"},
        "freeze_authority": None,
        "product_certification_sha256": SHA,
        "status": "RESET_READY",
    }
    return active


def _checks(root, active, *, sha=_sha, loader=_ledger):
    return active_epoch_integrity_checks(root, active, TARGET, sha256_file=sha, load_ledger=loader)


def test_valid_active_epoch_passes_all_thirteen_integrity_checks(tmp_path):
    active = _case(tmp_path)
    checks = _checks(tmp_path, active)
    assert len(checks) == 13
    assert all(checks.values())


@pytest.mark.parametrize("field,invalid,check", [
    ("immutable_history_snapshot", False, "immutable_history_snapshot_declared"),
    ("cutoff_contest", TARGET - 2, "cutoff_matches_target_minus_one"),
    ("result_used", True, "result_not_used"),
    ("freeze_authority", {"sha256": "x"}, "freeze_authority_absent"),
])
def test_invalid_epoch_fields_fail_only_relevant_gate(tmp_path, field, invalid, check):
    active = _case(tmp_path)
    active[field] = invalid
    checks = _checks(tmp_path, active)
    assert checks[check] is False
    assert all(value for key, value in checks.items() if key != check)


@pytest.mark.parametrize("change,check", [
    ("remove_snapshot", "data_snapshot_present"),
    ("tamper_snapshot", "data_snapshot_hash_match"),
    ("remove_canonical", "canonical_source_present"),
    ("tamper_canonical", "canonical_source_unchanged_since_prepare"),
    ("remove_ledger", "ledger_present"),
    ("premature_freeze", "freeze_artifact_absent"),
])
def test_missing_or_mutated_artifacts_block_integrity(tmp_path, change, check):
    active = _case(tmp_path)
    paths = {
        "remove_snapshot": tmp_path / "epoch/snapshot.xlsx",
        "tamper_snapshot": tmp_path / "epoch/snapshot.xlsx",
        "remove_canonical": tmp_path / "Mega-Sena.xlsx",
        "tamper_canonical": tmp_path / "Mega-Sena.xlsx",
        "remove_ledger": tmp_path / "epoch/ledger.json",
        "premature_freeze": tmp_path / "epoch/freeze.json",
    }
    file = paths[change]
    if change.startswith("remove"):
        file.unlink()
    elif change.startswith("tamper"):
        file.write_bytes(b"modified")
    else:
        file.write_text("{}", encoding="utf-8")
    assert _checks(tmp_path, active)[check] is False


def test_ledger_loader_exception_is_swallowed_and_marks_ledger_invalid(tmp_path):
    active = _case(tmp_path)
    def broken(_):
        raise RuntimeError("invalid evidence")
    checks = _checks(tmp_path, active, loader=broken)
    assert checks["ledger_valid"] is False
    assert checks["target_events_absent"] is True


def test_non_list_ledger_events_fail_closed(tmp_path):
    active = _case(tmp_path)
    checks = _checks(tmp_path, active, loader=lambda _: {"events": {}})
    assert checks["ledger_valid"] is False


def test_current_target_event_is_forbidden_before_freeze(tmp_path):
    active = _case(tmp_path)
    checks = _checks(tmp_path, active, loader=lambda _: {"events": [{"target_contest": TARGET}]})
    assert checks["target_events_absent"] is False


def test_different_target_ledger_event_does_not_block(tmp_path):
    active = _case(tmp_path)
    checks = _checks(tmp_path, active, loader=lambda _: {"events": [{"target_contest": TARGET - 1}]})
    assert checks["target_events_absent"] is True


def test_stale_certification_overrides_integrity_failure(tmp_path):
    active = _case(tmp_path)
    checks = _checks(tmp_path, active)
    checks["ledger_valid"] = False
    result = classify_active_epoch(active, "b" * 64, checks)
    assert result == ("REPREPARE_REQUIRED", "ACTIVE_EPOCH_PRODUCT_CERTIFICATION_STALE", False, False)


def test_integrity_failure_blocks_even_matching_certification(tmp_path):
    active = _case(tmp_path)
    checks = _checks(tmp_path, active)
    checks["ledger_present"] = False
    assert classify_active_epoch(active, SHA, checks) == (
        "BLOCKED_INTEGRITY", "ACTIVE_EPOCH_INTEGRITY_CHECK_FAILED", True, False
    )


@pytest.mark.parametrize("active_status,expected_status", [
    ("RESET_READY", "READY_TO_FREEZE"),
    ("PREPARED", "PREPARED"),
    ("", "ACTIVE"),
])
def test_ready_active_epoch_status_is_preserved(tmp_path, active_status, expected_status):
    active = _case(tmp_path)
    active["status"] = active_status
    assert classify_active_epoch(active, SHA, _checks(tmp_path, active)) == (
        expected_status, None, True, True
    )
