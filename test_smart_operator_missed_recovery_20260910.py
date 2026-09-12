from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import pandas as pd
import pytest

import smart_operator as operator
from smart_learning_epoch_reset import SCHEMA as EPOCH_SCHEMA, write_active_epoch


def _ledger(events=None):
    return {"schema": "SMART_SIGNAL_LEDGER_1", "events": list(events or []), "rules": {}}


def _payload(target=3):
    return {"numero": target, "listaDezenas": ["10", "11", "12", "13", "14", "15"], "dataApuracao": "10/09/2026", "acumulado": False}


def _make_root(tmp_path, *, target=3, schedule="2026-09-10T21:00:00-03:00", events=None):
    root = tmp_path
    root.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([
        {"Concurso": 1, "Data do Sorteio": "01/09/2026", "Bola1": 1, "Bola2": 2, "Bola3": 3, "Bola4": 4, "Bola5": 5, "Bola6": 6},
        {"Concurso": 2, "Data do Sorteio": "03/09/2026", "Bola1": 7, "Bola2": 8, "Bola3": 9, "Bola4": 10, "Bola5": 11, "Bola6": 12},
    ])
    canonical = root / "Mega-Sena.xlsx"
    frame.to_excel(canonical, index=False)
    epoch = root / "runtime" / "learning_epochs" / f"operator-{target}-test"
    epoch.mkdir(parents=True)
    snapshot = epoch / f"Mega-Sena_cutoff_{target-1}.xlsx"
    shutil.copy2(canonical, snapshot)
    ledger = epoch / "SMART_SIGNAL_LEDGER.json"
    ledger.write_text(json.dumps(_ledger(events)), encoding="utf-8")
    active = root / "SMART_ACTIVE_EPOCH.json"
    seed_sha = operator.sha256_file(ledger)
    write_active_epoch(active, {
        "schema": EPOCH_SCHEMA,
        "status": "RESET_READY",
        "project": "SMART-MEGA",
        "epoch_id": f"operator-{target}-test",
        "operator_selected_target": True,
        "state_paths": {
            "ledger": str(ledger.relative_to(root)),
            "state": str((epoch / "state.json").relative_to(root)),
            "activation_authority": str((epoch / "auth.json").relative_to(root)),
            "expansion_registry": str((epoch / "exp.json").relative_to(root)),
            "freeze": str((epoch / f"SMART_{target}_CHAMPION_CHALLENGER_FREEZE.json").relative_to(root)),
        },
        "data_file": str(snapshot.relative_to(root)),
        "data_sha256": operator.sha256_file(snapshot),
        "canonical_source_file": "Mega-Sena.xlsx",
        "canonical_source_sha256_at_prepare": operator.sha256_file(canonical),
        "immutable_history_snapshot": True,
        "cutoff_contest": target - 1,
        "target_contest": target,
        "authority_mode": "OPERATOR_SELECTED_TARGET",
        "current_engineering_role": "PRODUCT_CERTIFIED_OPERATION",
        "first_possible_authoritative_target_for_current_engineering": target,
        "target_schedule": {"scheduled_datetime": schedule},
        "temporal_guard": {"status": "PASS", "result_used": False},
        "result_used": False,
        "freeze_authority": None,
        "learning_state_authority": None,
        "canonical_ledger_seed_sha256": seed_sha,
        "canonical_ledger_seed_event_count": len(events or []),
    })
    return root, active, canonical, epoch, snapshot, ledger


def _after_draw():
    return datetime(2026, 9, 11, 1, 0, tzinfo=timezone.utc)


def test_recover_missed_unfrozen_advances_history_without_prediction_authority(tmp_path):
    root, active, canonical, _, _, _ = _make_root(tmp_path)
    before = operator.sha256_file(canonical)
    out = operator.recover_missed_unfrozen_operation(root, 3, payload=_payload(), now_utc=_after_draw())
    assert out["status"] == "RECOVERED_NO_VALID_FREEZE"
    assert out["prediction_authority_created"] is False
    assert out["prospective_attempt_counted"] is False
    assert out["result_used_for_prediction"] is False
    assert out["ready_for_next_target"] == 4
    assert not active.exists()
    frame = pd.read_excel(canonical)
    assert frame["Concurso"].astype(int).tolist() == [1, 2, 3]
    assert sorted(int(frame.iloc[-1][f"Bola{i}"]) for i in range(1, 7)) == [10, 11, 12, 13, 14, 15]
    proof_path = root / out["proof_file"]
    proof = json.loads(proof_path.read_text(encoding="utf-8")); observed = proof.pop("sha256")
    assert observed == hashlib.sha256(json.dumps(proof, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert out["canonical_sha256_before"] == before
    assert (root / out["canonical_backup"]).is_file()
    assert (root / out["active_epoch_archive"]).is_file()


def test_recover_missed_refuses_before_draw(tmp_path):
    root, active, canonical, _, _, _ = _make_root(tmp_path)
    before = operator.sha256_file(canonical)
    with pytest.raises(ValueError, match="forbidden before"):
        operator.recover_missed_unfrozen_operation(root, 3, payload=_payload(), now_utc=datetime(2026, 9, 10, 23, 0, tzinfo=timezone.utc))
    assert active.is_file() and operator.sha256_file(canonical) == before


def test_recover_missed_refuses_wrong_epoch_target_and_invalid_state(tmp_path):
    root, active, _, _, _, _ = _make_root(tmp_path)
    doc = json.loads(active.read_text(encoding="utf-8")); doc.pop("sha256", None); doc["operator_selected_target"] = False; write_active_epoch(active, doc)
    with pytest.raises(ValueError, match="operator-selected"):
        operator.recover_missed_unfrozen_operation(root, 3, payload=_payload(), now_utc=_after_draw())
    root2, _, _, _, _, _ = _make_root(tmp_path / "b")
    with pytest.raises(ValueError, match="does not match missed target"):
        operator.recover_missed_unfrozen_operation(root2, 4, payload=_payload(4), now_utc=_after_draw())
    root3, active3, _, _, _, _ = _make_root(tmp_path / "c")
    doc = json.loads(active3.read_text(encoding="utf-8")); doc.pop("sha256", None); doc["freeze_authority"] = {"file": "x"}; write_active_epoch(active3, doc)
    with pytest.raises(ValueError, match="RESET_READY"):
        operator.recover_missed_unfrozen_operation(root3, 3, payload=_payload(), now_utc=_after_draw())


def test_recover_missed_requires_valid_schedule_and_aware_clock(tmp_path):
    root, active, _, _, _, _ = _make_root(tmp_path)
    doc = json.loads(active.read_text(encoding="utf-8")); doc.pop("sha256", None); doc["target_schedule"] = {}; write_active_epoch(active, doc)
    with pytest.raises(ValueError, match="scheduled draw authority"):
        operator.recover_missed_unfrozen_operation(root, 3, payload=_payload(), now_utc=_after_draw())
    root2, _, _, _, _, _ = _make_root(tmp_path / "b", schedule="2026-09-10T21:00:00")
    with pytest.raises(ValueError, match="timezone-aware"):
        operator.recover_missed_unfrozen_operation(root2, 3, payload=_payload(), now_utc=_after_draw())
    root3, _, _, _, _, _ = _make_root(tmp_path / "c")
    with pytest.raises(ValueError, match="clock must be timezone-aware"):
        operator.recover_missed_unfrozen_operation(root3, 3, payload=_payload(), now_utc=datetime(2026, 9, 11, 1, 0))


def test_recover_missed_refuses_target_events_freeze_and_snapshot_drift(tmp_path):
    root, _, _, _, _, _ = _make_root(tmp_path, events=[{"event_type": "FREEZE", "target_contest": 3}])
    with pytest.raises(ValueError, match="target events"):
        operator.recover_missed_unfrozen_operation(root, 3, payload=_payload(), now_utc=_after_draw())
    root2, _, _, epoch2, _, _ = _make_root(tmp_path / "b")
    (epoch2 / "SMART_3_CHAMPION_CHALLENGER_FREEZE.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="freeze artifact"):
        operator.recover_missed_unfrozen_operation(root2, 3, payload=_payload(), now_utc=_after_draw())
    root3, _, _, _, snapshot3, _ = _make_root(tmp_path / "c")
    snapshot3.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="snapshot integrity"):
        operator.recover_missed_unfrozen_operation(root3, 3, payload=_payload(), now_utc=_after_draw())


def test_recover_missed_refuses_canonical_drift_and_existing_outputs(tmp_path):
    root, _, canonical, _, _, _ = _make_root(tmp_path)
    canonical.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="canonical history changed"):
        operator.recover_missed_unfrozen_operation(root, 3, payload=_payload(), now_utc=_after_draw())
    root2, _, _, _, _, _ = _make_root(tmp_path / "b")
    (root2 / "SMART_MISSED_TARGET_RECOVERY_3.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError, match="overwrite missed-target"):
        operator.recover_missed_unfrozen_operation(root2, 3, payload=_payload(), now_utc=_after_draw())
    root3, _, _, epoch3, _, _ = _make_root(tmp_path / "c")
    (epoch3 / "Mega-Sena_through_3.xlsx").write_bytes(b"exists")
    with pytest.raises(FileExistsError, match="output already exists"):
        operator.recover_missed_unfrozen_operation(root3, 3, payload=_payload(), now_utc=_after_draw())


def test_recover_missed_refuses_ingest_archive_and_backup_integrity_failures(tmp_path, monkeypatch):
    root, _, _, _, _, _ = _make_root(tmp_path)
    def bad_ingest(source, output, proof, target, payload=None):
        output.write_bytes(b"x"); proof.write_text("{}", encoding="utf-8")
        return {"source_sha256": "0" * 64, "output_sha256": operator.sha256_file(output), "actual_numbers": [1,2,3,4,5,6]}
    monkeypatch.setattr(operator, "ingest_official_result", bad_ingest)
    with pytest.raises(RuntimeError, match="official ingest integrity"):
        operator.recover_missed_unfrozen_operation(root, 3, payload=_payload(), now_utc=_after_draw())
    root2, _, _, _, _, _ = _make_root(tmp_path / "b")
    monkeypatch.setattr(operator, "ingest_official_result", __import__("smart_official_result_ingest").ingest)
    monkeypatch.setattr(operator, "_archive_active", lambda root, active_path: "0" * 64)
    with pytest.raises(RuntimeError, match="active archive mismatch"):
        operator.recover_missed_unfrozen_operation(root2, 3, payload=_payload(), now_utc=_after_draw())


def test_recover_missed_rolls_back_when_pointer_or_proof_finalization_fails(tmp_path, monkeypatch):
    root, active, canonical, _, _, _ = _make_root(tmp_path)
    before = operator.sha256_file(canonical)
    original_unlink = Path.unlink
    def keep_active(self, *args, **kwargs):
        if self == active:
            return None
        return original_unlink(self, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", keep_active)
    with pytest.raises(RuntimeError, match="pointer removal failed"):
        operator.recover_missed_unfrozen_operation(root, 3, payload=_payload(), now_utc=_after_draw())
    assert active.is_file() and operator.sha256_file(canonical) == before

    root2, active2, canonical2, _, _, _ = _make_root(tmp_path / "b")
    before2 = operator.sha256_file(canonical2)
    original_replace = Path.replace
    def fail_proof_replace(self, target):
        if self.name == "SMART_MISSED_TARGET_RECOVERY_3.json.tmp":
            raise OSError("proof replace failure")
        return original_replace(self, target)
    monkeypatch.setattr(Path, "replace", fail_proof_replace)
    with pytest.raises(OSError, match="proof replace failure"):
        operator.recover_missed_unfrozen_operation(root2, 3, payload=_payload(), now_utc=_after_draw())
    assert active2.is_file() and operator.sha256_file(canonical2) == before2


def test_recover_missed_rejects_bad_backup_and_temporary_copy(tmp_path, monkeypatch):
    root, _, canonical, _, _, _ = _make_root(tmp_path)
    before = operator.sha256_file(canonical)
    archive = root / "SMART_STATE_ARCHIVE"; archive.mkdir()
    (archive / f"Mega-Sena_before_missed_3_{before}.xlsx").write_bytes(b"bad")
    with pytest.raises(RuntimeError, match="backup hash mismatch"):
        operator.recover_missed_unfrozen_operation(root, 3, payload=_payload(), now_utc=_after_draw())

    root2, _, _, _, _, _ = _make_root(tmp_path / "b")
    original_copy2 = shutil.copy2
    def corrupt_temp(src, dst, *args, **kwargs):
        result = original_copy2(src, dst, *args, **kwargs)
        if "Mega-Sena.missed.3." in str(dst):
            Path(dst).write_bytes(b"corrupt")
        return result
    monkeypatch.setattr(operator.shutil, "copy2", corrupt_temp)
    with pytest.raises(RuntimeError, match="temporary canonical hash mismatch"):
        operator.recover_missed_unfrozen_operation(root2, 3, payload=_payload(), now_utc=_after_draw())


def test_recover_missed_restores_on_canonical_postcondition_failure(tmp_path, monkeypatch):
    root, active, canonical, _, _, _ = _make_root(tmp_path)
    before = operator.sha256_file(canonical)
    original_replace = operator.os.replace
    def skip_canonical_replace(src, dst):
        if "Mega-Sena.missed.3." in str(src) and Path(dst) == canonical:
            return None
        return original_replace(src, dst)
    monkeypatch.setattr(operator.os, "replace", skip_canonical_replace)
    with pytest.raises(RuntimeError, match="advance postcondition"):
        operator.recover_missed_unfrozen_operation(root, 3, payload=_payload(), now_utc=_after_draw())
    assert active.is_file() and operator.sha256_file(canonical) == before


def test_main_routes_recover_missed_without_live_fetch(monkeypatch, capsys):
    calls = {}
    def fake(root, target):
        calls["root"] = root; calls["target"] = target
        return {"status": "RECOVERED_NO_VALID_FREEZE", "target_contest": target}
    monkeypatch.setattr(operator, "recover_missed_unfrozen_operation", fake)
    operator.main(["recover-missed", "--target", "3056"])
    assert calls["target"] == 3056 and calls["root"].name == "SMART-MEGA"
    assert json.loads(capsys.readouterr().out)["status"] == "RECOVERED_NO_VALID_FREEZE"


def test_recover_missed_refuses_result_used_contamination_direct_guard(tmp_path, monkeypatch):
    active = {
        "operator_selected_target": True,
        "target_contest": 3,
        "status": "RESET_READY",
        "result_used": True,
        "freeze_authority": None,
    }
    monkeypatch.setattr(operator, "verify_active_epoch", lambda path: active)
    with pytest.raises(ValueError, match="unresolved RESET_READY state without freeze authority"):
        operator.recover_missed_unfrozen_operation(tmp_path, 3, payload=_payload(), now_utc=_after_draw())
