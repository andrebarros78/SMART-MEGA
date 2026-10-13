"""Security and non-regression tests for the real post-result consumer path."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import smart_post_result_report as report
import smart_operator as operator
from test_smart_post_result_report import _fixture as minimal_freeze
from test_smart_operator_result_materialization import _fixture as result_fixture


def _alter_primary_card(root: Path, active: dict, numbers) -> None:
    ledger = root / active['state_paths']['ledger']
    payload = json.loads(ledger.read_text(encoding='utf-8'))
    payload['events'][0]['primary_card'] = {'numbers': numbers}
    ledger.write_text(json.dumps(payload), encoding='utf-8')


@pytest.mark.parametrize('invalid', [
    [1.99, 2, 3, 4, 5, 6],
    [True, 2, 3, 4, 5, 6],
    ['1.5', 2, 3, 4, 5, 6],
    [None, 2, 3, 4, 5, 6],
])
def test_primary_card_rejects_fraction_boolean_and_nonnumeric_without_report(tmp_path, invalid):
    active = minimal_freeze(tmp_path, reported_hits=2)
    _alter_primary_card(tmp_path, active, invalid)
    with pytest.raises(ValueError, match='frozen primary card evidence invalid'):
        report.emit_post_result_report(tmp_path, active)
    assert not (tmp_path / 'SMART_POST_RESULT_REPORT_999.json').exists()
    assert not (tmp_path / 'SMART_POST_RESULT_REPORT_999.md').exists()


def test_primary_card_digit_strings_preserve_legacy_compatibility(tmp_path):
    active = minimal_freeze(tmp_path, reported_hits=2)
    _alter_primary_card(tmp_path, active, ['01', '2', '3', '4', '5', '6'])
    out = report.emit_post_result_report(tmp_path, active)
    assert out['status'] == 'EMITTED'
    assert out['report']['generated_card'] == [1, 2, 3, 4, 5, 6]
    assert out['report']['hit_count'] == 2


def test_immutable_ledger_witness_refuses_symlink_and_modified_source(tmp_path):
    ledger = tmp_path / 'SMART_SIGNAL_LEDGER.json'
    ledger.write_bytes(b'{"events":[]}')
    sha = hashlib.sha256(ledger.read_bytes()).hexdigest()
    outside = tmp_path.parent / (tmp_path.name + '-external.json')
    outside.write_bytes(ledger.read_bytes())
    link = tmp_path / 'ledger-link.json'
    link.symlink_to(outside)
    with pytest.raises(ValueError, match='regular file'):
        report._preserve_ledger_evidence(tmp_path, 999, link, sha)
    assert not (tmp_path / 'SMART_STATE_ARCHIVE').exists()
    with pytest.raises(ValueError, match='changed while capturing'):
        report._preserve_ledger_evidence(tmp_path, 999, ledger, 'f' * 64)
    assert list((tmp_path / 'SMART_STATE_ARCHIVE').rglob('*.tmp')) == []
    assert not list((tmp_path / 'SMART_STATE_ARCHIVE').rglob('SMART_SIGNAL_LEDGER.*.json'))


def test_result_materialization_refuses_duplicate_adjudication(tmp_path, monkeypatch):
    active, source, destination = result_fixture(tmp_path, monkeypatch)
    valid_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    events = [{
        'event_type': 'ADJUDICATION', 'target_contest': 3067,
        'result_data_file': 'Mega-Sena_through_3067.xlsx',
        'result_data_sha256': valid_sha,
    }] * 2
    monkeypatch.setattr(operator, 'load_ledger', lambda path: {'events': events})
    with pytest.raises(ValueError, match='exactly one adjudication'):
        operator._materialize_adjudicated_result_dataset(tmp_path, active, 3067)
    assert not destination.exists()
    assert source.read_bytes() == b'immutable-3067-result-bytes'


def test_result_materialization_refuses_corrupted_sha_without_destination(tmp_path, monkeypatch):
    active, source, destination = result_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(operator, 'load_ledger', lambda path: {'events': [{
        'event_type':'ADJUDICATION', 'target_contest':3067,
        'result_data_file':'Mega-Sena_through_3067.xlsx',
        'result_data_sha256':'a'*64,
    }]})
    with pytest.raises(ValueError, match='integrity mismatch'):
        operator._materialize_adjudicated_result_dataset(tmp_path, active, 3067)
    assert not destination.exists()
    assert source.read_bytes() == b'immutable-3067-result-bytes'


def test_report_atomic_write_replaces_document_without_residual_files(tmp_path):
    location = tmp_path / 'SMART_POST_RESULT_REPORT_999.json'
    location.write_text('old',encoding='utf-8')
    report._atomic_write(location, 'new')
    assert location.read_text(encoding='utf-8') == 'new'
    assert sorted(item.name for item in tmp_path.iterdir()) == [location.name]
