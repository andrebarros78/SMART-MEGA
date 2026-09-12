from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import smart_champion_challenger as cc
import smart_independent_audit as ia
import smart_sequential_prospective_proof as sp
from test_smart_independent_audit import _pair_fixture
from test_smart_b2_evolution_20260909 import _completed


@pytest.mark.parametrize(
    ("selected_label", "pattern"),
    [
        ("frozen artifact", "frozen artifact hash mismatch"),
        ("frozen input data", "frozen input data hash mismatch"),
        ("result data", "result data missing"),
    ],
)
def test_d012_post_resolution_race_checks_remain_fail_closed(
    tmp_path: Path, monkeypatch, selected_label: str, pattern: str
):
    ledger, *_ = _pair_fixture(tmp_path, target=11)
    real = ia._resolve_hash_bound_evidence
    vanished = tmp_path / "vanished-after-resolution.bin"

    def fake(root, value, expected_sha256, label, **kwargs):
        if label == selected_label:
            return vanished
        return real(root, value, expected_sha256, label, **kwargs)

    monkeypatch.setattr(ia, "_resolve_hash_bound_evidence", fake)
    with pytest.raises(ValueError, match=pattern):
        ia.audit_prospective_ledger(tmp_path, ledger)


def test_d013_seed_refuses_overwrite_and_supports_missing_empty_canonical(tmp_path: Path):
    existing = tmp_path / "existing.json"
    existing.write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        cc.seed_ledger_from_canonical(tmp_path / "missing.json", existing)

    destination = tmp_path / "seeded.json"
    out = cc.seed_ledger_from_canonical(tmp_path / "missing.json", destination)
    assert out["status"] == "SEEDED"
    assert out["event_count"] == 0
    assert cc.load_ledger(destination)["events"] == []


def test_d013_seed_verification_mismatch_removes_destination(tmp_path: Path, monkeypatch):
    destination = tmp_path / "seeded.json"
    canonical = {"schema": cc.LEDGER_SCHEMA, "events": []}
    calls = {"n": 0}

    def fake_load(path):
        calls["n"] += 1
        if calls["n"] == 1:
            return canonical
        return {"schema": cc.LEDGER_SCHEMA, "events": [{"unexpected": True}]}

    monkeypatch.setattr(cc, "load_ledger", fake_load)
    with pytest.raises(RuntimeError, match="seed verification failed"):
        cc.seed_ledger_from_canonical(tmp_path / "missing.json", destination)
    assert not destination.exists()


def _write_json(path: Path, value: dict):
    path.write_text(json.dumps(value), encoding="utf-8")



def test_d013_reconcile_rejects_invalid_or_empty_completed_epoch(tmp_path: Path, monkeypatch):
    canonical = tmp_path / "canonical.json"
    epoch = tmp_path / "epoch.json"
    _write_json(canonical, {"schema": cc.LEDGER_SCHEMA, "events": []})
    _write_json(epoch, {"schema": cc.LEDGER_SCHEMA, "events": []})

    monkeypatch.setattr(
        sp, "validate_target_sequence",
        lambda *args, **kwargs: {"valid": False, "adjudicated": False},
     )
    with pytest.raises(ValueError, match="not a completed prospective attempt"):
        cc.reconcile_completed_epoch_ledger(canonical, epoch, 11, root=tmp_path)

    monkeypatch.setattr(
        sp, "validate_target_sequence",
        lambda *args, **kwargs: {"valid": True, "adjudicated": True},
    )
    with pytest.raises(ValueError, match="contains no target events"):
        cc.reconcile_completed_epoch_ledger(canonical, epoch, 11, root=tmp_path)


def test_d013_reconcile_rejects_existing_target_divergence(tmp_path: Path, monkeypatch):
    canonical = tmp_path / "canonical.json"
    epoch = tmp_path / "epoch.json"
    base = _completed(11)
    other = copy.deepcopy(base)
    other["events"][0]["migration_note"] = "different-but-still-target-scoped"
    _write_json(canonical, base)
    _write_json(epoch, other)
    monkeypatch.setattr(
        sp, "validate_target_sequence",
        lambda *args, **kwargs: {"valid": True, "adjudicated": True},
     )
    with pytest.raises(ValueError, match="canonical ledger target differs"):
        cc.reconcile_completed_epoch_ledger(canonical, epoch, 11, root=tmp_path)


def test_d013_reconcile_works_when_canonical_file_is_initially_missing(tmp_path: Path):
    canonical = tmp_path / "canonical.json"
    epoch = tmp_path / "epoch.json"
    _write_json(epoch, _completed(11))
    out = cc.reconcile_completed_epoch_ledger(canonical, epoch, 11, root=tmp_path)
    assert out["status"] == "PASS"
    assert out["canonical_backup"] is None
    assert canonical.is_file()


def test_d013_reconcile_reuses_preexisting_correct_backup(tmp_path: Path):
    canonical = tmp_path / "canonical.json"
    epoch = tmp_path / "epoch.json"
    _write_json(canonical, {"schema": cc.LEDGER_SCHEMA, "events": []})
    _write_json(epoch, _completed(11))
    before = cc.sha256(canonical)
    archive = tmp_path / "SMART_STATE_ARCHIVE" / "canonical-ledger" / f"SMART_SIGNAL_LEDGER.{before}.json"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(canonical.read_bytes())
    out = cc.reconcile_completed_epoch_ledger(canonical, epoch, 11, root=tmp_path)
    assert out["status"] == "PASS"
    assert out["canonical_backup"] == archive.relative_to(tmp_path).as_posix()


def test_d013_reconcile_rejects_corrupt_preexisting_backup(tmp_path: Path):
    canonical = tmp_path / "canonical.json"
    epoch = tmp_path / "epoch.json"
    _write_json(canonical, {"schema": cc.LEDGER_SCHEMA, "events": []})
    _write_json(epoch, _completed(11))
    before = cc.sha256(canonical)
    archive = tmp_path / "SMART_STATE_ARCHIVE" / "canonical-ledger" / f"SMART_SIGNAL_LEDGER.{before}.json"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"corrupt")
    with pytest.raises(RuntimeError, match="backup hash mismatch"):
        cc.reconcile_completed_epoch_ledger(canonical, epoch, 11, root=tmp_path)


def test_d013_reconcile_detects_post_replace_hash_race(tmp_path: Path, monkeypatch):
    canonical = tmp_path / "canonical.json"
    epoch = tmp_path / "epoch.json"
    _write_json(canonical, {"schema": cc.LEDGER_SCHEMA, "events": []})
    _write_json(epoch, _completed(11))
    real_sha = cc.sha256
    state = {"temp_seen": False}

    def fake_sha(path):
        p = Path(path)
        if p.name.endswith(".reconcile.tmp"):
            state["temp_seen"] = True
            return real_sha(p)
        if state["temp_seen"] and p == canonical:
            return "0" * 64
        return real_sha(p)

    monkeypatch.setattr(cc, "sha256", fake_sha)
    with pytest.raises(RuntimeError, match="write verification failed"):
        cc.reconcile_completed_epoch_ledger(canonical, epoch, 11, root=tmp_path)
