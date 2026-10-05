import json
from pathlib import Path

import pandas as pd
import pytest

import smart_repository_integrity as integrity
import smart_startup_reconciler as startup
from smart_operational_lifecycle import _sha_json


def test_repository_integrity_contract() -> None:
    evidence = integrity.validate_repository()
    assert evidence["status"] == "PASS"
    assert evidence["portable_identity"] is True
    epoch = evidence["epoch"]
    if epoch["target_contest"] is not None and epoch["cutoff_contest"] is not None:
        assert epoch["target_contest"] > epoch["cutoff_contest"]
    assert epoch["status"] in {"FROZEN", "RESET_READY", "NO_ACTIVE_EPOCH_IDLE",
                               "NO_ACTIVE_EPOCH_HOLD", "NO_ACTIVE_EPOCH_AUTHORIZED"}


def _hold_fixture(root: Path, monkeypatch, state="HOLD"):
    monkeypatch.setattr(integrity, "ROOT", root)
    monkeypatch.setattr(startup, "require_canonical_identity", lambda _: {"status": "PASS"})
    life = {"schema": "SMART_OPERATIONAL_LIFECYCLE_1", "state": state, "revision": 1,
            "project": "SMART-MEGA", "target_contest": 3, "completed_contest": 2}
    life["sha256"] = _sha_json(life)
    (root / "SMART_OPERATIONAL_LIFECYCLE.json").write_text(json.dumps(life), encoding="utf-8")
    hold = {"schema": "SMART_NEXT_CYCLE_HOLD_1", "status": "AWAITING_OPERATOR_APPLY_OR_GENERATE",
            "next_target": 3, "completed_contest": 2}
    hold["sha256"] = _sha_json(hold)
    (root / "SMART_NEXT_CYCLE_HOLD.json").write_text(json.dumps(hold), encoding="utf-8")
    rows = [{"Concurso": i, "Data do Sorteio": f"2020-01-0{i}",
             **{f"Bola{j}": j + i for j in range(1, 7)}} for i in (1, 2)]
    pd.DataFrame(rows).to_excel(root / "Mega-Sena.xlsx", index=False)


def test_integrity_accepts_valid_hold_without_active_prediction(tmp_path, monkeypatch):
    _hold_fixture(tmp_path, monkeypatch)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    evidence = integrity._check_operational_state()
    assert evidence["status"] == "NO_ACTIVE_EPOCH_HOLD"
    assert evidence["target_contest"] == 3
    assert evidence["epoch_id"] is None
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("fault", ["frozen_without_epoch", "missing_hold", "tampered_hold", "dataset_gap"])
def test_integrity_rejects_missing_or_inconsistent_operational_state(tmp_path, monkeypatch, fault):
    _hold_fixture(tmp_path, monkeypatch, "FROZEN" if fault == "frozen_without_epoch" else "HOLD")
    if fault == "missing_hold":
        (tmp_path / "SMART_NEXT_CYCLE_HOLD.json").unlink()
    elif fault == "tampered_hold":
        hold = tmp_path / "SMART_NEXT_CYCLE_HOLD.json"
        value = json.loads(hold.read_text(encoding="utf-8"))
        value["next_target"] = 4
        hold.write_text(json.dumps(value), encoding="utf-8")
    elif fault == "dataset_gap":
        pd.DataFrame([{"Concurso": 1}]).to_excel(tmp_path / "Mega-Sena.xlsx", index=False)
    with pytest.raises(integrity.RepositoryIntegrityError, match="requires recovery"):
        integrity._check_operational_state()
