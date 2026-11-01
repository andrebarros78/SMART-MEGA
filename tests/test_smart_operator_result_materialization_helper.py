"""Isolated characterization for adjudicated result dataset materialization."""
from __future__ import annotations
import hashlib
from pathlib import Path
import pytest
from smart_operator_result_materialization import materialize_adjudicated_result_dataset


def _scenario(tmp_path, *, source_name="result.xlsx", events_override=None):
    epoch = tmp_path / "epoch"
    epoch.mkdir()
    (epoch / "ledger.json").write_text("{}", encoding="utf-8")
    source = tmp_path / "result.xlsx"
    source.write_bytes(b"verified-result-bytes")
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
    row = {"event_type": "ADJUDICATION", "target_contest": 3080,
           "result_data_file": source_name, "result_data_sha256": fingerprint}
    events = [row] if events_override is None else events_override
    active = {"state_paths": {"ledger": "epoch/ledger.json"}}
    def materialize():
        return materialize_adjudicated_result_dataset(
            tmp_path, active, 3080,
            load_ledger=lambda path: {"events": events},
            sha256_file=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        )
    return source, epoch / "Mega-Sena_through_3080.xlsx", materialize


def test_materialization_preserves_bytes_and_is_idempotent(tmp_path):
    source, destination, execute = _scenario(tmp_path)
    first = execute()
    assert first["status"] == "PASS"
    assert first["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert destination.read_bytes() == source.read_bytes()
    assert execute() == first


def test_materialization_rejects_existing_conflicting_file(tmp_path):
    _, destination, execute = _scenario(tmp_path)
    destination.write_bytes(b"conflict")
    with pytest.raises(ValueError, match="differs from adjudication"):
        execute()
    assert destination.read_bytes() == b"conflict"


@pytest.mark.parametrize("source_path", ["../escape.xlsx", "/tmp/untrusted.xlsx"])
def test_materialization_rejects_untrusted_source(tmp_path, source_path):
    _, destination, execute = _scenario(tmp_path, source_name=source_path)
    with pytest.raises(ValueError):
        execute()
    assert not destination.exists()


def test_materialization_requires_unique_adjudication(tmp_path):
    _, destination, execute = _scenario(tmp_path, events_override=[])
    with pytest.raises(ValueError, match="exactly one adjudication"):
        execute()
    assert not destination.exists()


def test_materialization_rejects_duplicate_adjudication(tmp_path):
    epoch = tmp_path / "epoch"
    epoch.mkdir()
    (epoch / "ledger.json").write_text("{}", encoding="utf-8")
    event = {"event_type": "ADJUDICATION", "target_contest": 3080}
    with pytest.raises(ValueError, match="exactly one adjudication"):
        materialize_adjudicated_result_dataset(
            tmp_path, {"state_paths": {"ledger": "epoch/ledger.json"}},
            3080,
            load_ledger=lambda path: {"events": [event, dict(event)]},
            sha256_file=lambda path: "",
        )
    assert not (epoch / "Mega-Sena_through_3080.xlsx").exists()


@pytest.mark.parametrize("failure", ["corrupt_copy", "racing_destination"])
def test_materialization_rejects_copy_failure_and_cleans_temporary(tmp_path, monkeypatch, failure):
    import smart_operator_result_materialization as helper

    source, destination, execute = _scenario(tmp_path)
    real_copy = helper.shutil.copyfile

    def adverse_copy(source_path, target_path):
        result = real_copy(source_path, target_path)
        if failure == "corrupt_copy":
            Path(target_path).write_bytes(b"corrupt transfer")
        else:
            destination.write_bytes(b"other process")
        return result

    monkeypatch.setattr(helper.shutil, "copyfile", adverse_copy)
    with pytest.raises(ValueError, match="copy failed integrity or exclusivity"):
        execute()
    assert source.read_bytes() == b"verified-result-bytes"
    assert not list(destination.parent.glob(".result-*.xlsx"))
    if failure == "racing_destination":
        assert destination.read_bytes() == b"other process"
    else:
        assert not destination.exists()