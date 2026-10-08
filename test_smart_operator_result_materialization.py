from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import smart_operator as operator


def _fixture(tmp_path: Path, monkeypatch, source_path: str = "Mega-Sena_through_3067.xlsx"):
    ledger = tmp_path / "runtime" / "learning_epochs" / "epoch3067" / "SMART_SIGNAL_LEDGER.json"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("{}", encoding="utf-8")
    data = tmp_path / "Mega-Sena_through_3067.xlsx"
    data.write_bytes(b"immutable-3067-result-bytes")
    digest = hashlib.sha256(data.read_bytes()).hexdigest()
    event = {
        "event_type": "ADJUDICATION",
        "target_contest": 3067,
        "result_data_file": source_path,
        "result_data_sha256": digest,
    }
    monkeypatch.setattr(operator, "load_ledger", lambda path: {"events": [event]})
    active = {"state_paths": {"ledger": str(ledger.relative_to(tmp_path))}}
    return active, data, ledger.parent / "Mega-Sena_through_3067.xlsx"


def test_result_materialization_is_byte_exact_and_idempotent(tmp_path, monkeypatch):
    active, source, target = _fixture(tmp_path, monkeypatch)
    output = operator._materialize_adjudicated_result_dataset(tmp_path, active, 3067)
    assert output["status"] == "PASS"
    assert target.read_bytes() == source.read_bytes()
    assert output["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert operator._materialize_adjudicated_result_dataset(tmp_path, active, 3067) == output


def test_result_materialization_rejects_conflicting_existing_file(tmp_path, monkeypatch):
    active, source, target = _fixture(tmp_path, monkeypatch)
    target.write_bytes(b"conflict")
    with pytest.raises(ValueError, match="differs from adjudication"):
        operator._materialize_adjudicated_result_dataset(tmp_path, active, 3067)
    assert source.read_bytes() == b"immutable-3067-result-bytes"


def test_result_materialization_rejects_untrusted_path(tmp_path, monkeypatch):
    active, _source, _target = _fixture(tmp_path, monkeypatch, "../outside.xlsx")
    with pytest.raises(ValueError):
        operator._materialize_adjudicated_result_dataset(tmp_path, active, 3067)
