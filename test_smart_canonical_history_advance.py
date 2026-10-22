from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

import smart_canonical_history_advance as cha


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frame(n: int) -> pd.DataFrame:
    rows = []
    for contest in range(1, n + 1):
        nums = [contest, contest + 1, contest + 2, contest + 3, contest + 4, contest + 5]
        rows.append({
            'Concurso': contest,
            'Data do Sorteio': pd.Timestamp('2026-01-01') + pd.Timedelta(days=contest),
            **{f'Bola{i}': nums[i-1] for i in range(1, 7)},
            'Ganhadores 6 acertos': None,
        })
    return pd.DataFrame(rows)


def _fixture(tmp_path: Path, monkeypatch, *, target: int = 4):
    canonical = tmp_path / 'Mega-Sena.xlsx'
    through_dir = tmp_path / 'runtime' / 'learning_epochs' / 'e1'
    through_dir.mkdir(parents=True)
    through = through_dir / f'Mega-Sena_through_{target}.xlsx'
    _frame(target - 1).to_excel(canonical, index=False)
    _frame(target).to_excel(through, index=False)
    result = through_dir / f'Mega-Sena_result_{target}.xlsx'
    pd.DataFrame([{'Concurso': target, **{f'Bola{i}': target + i - 1 for i in range(1, 7)}}]).to_excel(result, index=False)
    actual = list(range(target, target + 6))
    ledger = {
        'schema': 'SMART_CHAMPION_CHALLENGER_LEDGER_1',
        'events': [{
            'event_type': 'ADJUDICATION', 'target_contest': target,
            'result_data_file': str(result.relative_to(tmp_path)).replace('\\','/'),
            'result_data_sha256': _sha(result), 'actual_numbers': actual,
        }],
    }
    ledger_path = through_dir / 'SMART_SIGNAL_LEDGER.json'
    ledger_path.write_text(json.dumps(ledger), encoding='utf-8')
    active = {'project': 'SMART-MEGA', 'target_contest': target,
              'state_paths': {'ledger': str(ledger_path.relative_to(tmp_path)).replace('\\','/')}}
    monkeypatch.setattr(cha, 'load_ledger', lambda path: ledger)
    monkeypatch.setattr(cha, 'validate_target_sequence', lambda *a, **k: {
        'valid': True, 'adjudicated': True, 'sequence_sha256': 'a'*64,
    })
    return canonical, through, result, ledger, active


def test_advance_completed_epoch_is_atomic_and_idempotent(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    before = _sha(canonical)
    out = cha.advance_completed_epoch(tmp_path, active)
    assert out['status'] == 'PASS'
    assert out['target_contest'] == 4
    assert out['canonical_sha256_before'] == before
    assert out['canonical_sha256_after'] == _sha(through) == _sha(canonical)
    assert out['canonical_prefix_preserved'] is True
    assert out['future_information_used'] is False
    assert out['retroactive_rewrite'] is False
    backup = tmp_path / out['canonical_backup']
    assert backup.is_file() and _sha(backup) == before
    proof = tmp_path / 'SMART_CANONICAL_HISTORY_ADVANCE_4.json'
    assert proof.is_file()
    second = cha.advance_completed_epoch(tmp_path, active)
    assert second['status'] == 'ALREADY_CURRENT'



def test_replay_preserves_original_pass_receipt_bytes(tmp_path: Path, monkeypatch):
    canonical, through, _, _, active = _fixture(tmp_path, monkeypatch)
    first = cha.advance_completed_epoch(tmp_path, active)
    assert first['status'] == 'PASS'
    receipt = tmp_path / 'SMART_CANONICAL_HISTORY_ADVANCE_4.json'
    original = receipt.read_bytes()
    original_sha = _sha(receipt)
    again = cha.advance_completed_epoch(tmp_path, active)
    assert again['status'] == 'ALREADY_CURRENT'
    assert again['existing_proof_preserved'] is True
    assert again['persisted_proof_sha256'] == original_sha
    assert receipt.read_bytes() == original
    assert json.loads(receipt.read_text())['status'] == 'PASS'


def test_replay_keeps_first_pass_after_metadata_enrichment(tmp_path: Path, monkeypatch):
    canonical, through, _, _, active = _fixture(tmp_path, monkeypatch)
    assert cha.advance_completed_epoch(tmp_path, active)['status'] == 'PASS'
    receipt = tmp_path / 'SMART_CANONICAL_HISTORY_ADVANCE_4.json'
    original = receipt.read_bytes()
    frame = pd.read_excel(canonical)
    frame.loc[frame['Concurso'] == 4, 'Ganhadores 6 acertos'] = 0
    frame.to_excel(canonical, index=False)
    replay = cha.advance_completed_epoch(tmp_path, active)
    assert replay['status'] == 'ALREADY_CURRENT'
    assert replay['canonical_metadata_enrichment_preserved'] is True
    assert receipt.read_bytes() == original


@pytest.mark.parametrize('corrupt', ['self_hash', 'target'])
def test_replay_rejects_modified_original_receipt(tmp_path: Path, monkeypatch, corrupt):
    _, _, _, _, active = _fixture(tmp_path, monkeypatch)
    assert cha.advance_completed_epoch(tmp_path, active)['status'] == 'PASS'
    receipt = tmp_path / 'SMART_CANONICAL_HISTORY_ADVANCE_4.json'
    forged = json.loads(receipt.read_text())
    if corrupt == 'self_hash':
        forged['sha256'] = '0' * 64
    else:
        forged['target_contest'] = 5
        forged.pop('sha256')
        forged['sha256'] = hashlib.sha256(json.dumps(
            forged, ensure_ascii=False, sort_keys=True, separators=(',', ':')
        ).encode('utf-8')).hexdigest()
    receipt.write_text(json.dumps(forged), encoding='utf-8')
    malicious = receipt.read_bytes()
    with pytest.raises(ValueError, match='existing canonical history advance proof invalid'):
        cha.advance_completed_epoch(tmp_path, active)
    assert receipt.read_bytes() == malicious


def test_advance_rejects_prefix_change(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    df = pd.read_excel(through)
    df.loc[df['Concurso'] == 2, 'Bola1'] = 60
    df.to_excel(through, index=False)
    with pytest.raises(ValueError, match='prefix'):
        cha.advance_completed_epoch(tmp_path, active)


def test_advance_rejects_target_numbers_not_matching_adjudication(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    ledger['events'][0]['actual_numbers'] = [10, 11, 12, 13, 14, 15]
    with pytest.raises(ValueError, match='differ from adjudication'):
        cha.advance_completed_epoch(tmp_path, active)


def test_advance_requires_completed_sequence(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(cha, 'validate_target_sequence', lambda *a, **k: {'valid': False, 'adjudicated': True})
    with pytest.raises(ValueError, match='not a completed prospective attempt'):
        cha.advance_completed_epoch(tmp_path, active)


def test_advance_rejects_result_hash_mismatch(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    ledger['events'][0]['result_data_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='result evidence'):
        cha.advance_completed_epoch(tmp_path, active)


def test_advance_already_current_preserves_non_predictive_metadata_enrichment(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    enriched = pd.read_excel(through)
    enriched.loc[enriched['Concurso'] == 4, 'Ganhadores 6 acertos'] = 0
    enriched.to_excel(canonical, index=False)
    assert _sha(canonical) != _sha(through)
    out = cha.advance_completed_epoch(tmp_path, active)
    assert out['status'] == 'ALREADY_CURRENT'
    assert out['core_history_equal'] is True
    assert out['canonical_metadata_enrichment_preserved'] is True
    assert _sha(canonical) != _sha(through)


def test_advance_already_current_rejects_core_draw_divergence(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    current = pd.read_excel(through)
    current.loc[current['Concurso'] == 2, 'Bola1'] = 60
    current.to_excel(canonical, index=False)
    with pytest.raises(ValueError, match='core draw history differs'):
        cha.advance_completed_epoch(tmp_path, active)


def test_advance_already_current_rejects_metadata_rewrite(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    base = pd.read_excel(through)
    base.loc[base['Concurso'] == 4, 'Ganhadores 6 acertos'] = 1
    base.to_excel(through, index=False)
    changed = pd.read_excel(through)
    changed.loc[changed['Concurso'] == 4, 'Ganhadores 6 acertos'] = 2
    changed.to_excel(canonical, index=False)
    with pytest.raises(ValueError, match='already-advanced canonical history differs'):
        cha.advance_completed_epoch(tmp_path, active)


def test_advance_resolves_archived_result_evidence_by_committed_hash(tmp_path: Path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    expected = _sha(result)
    archive_dir = tmp_path / 'SMART_STATE_ARCHIVE' / 'adjudication-evidence'
    archive_dir.mkdir(parents=True)
    archived = archive_dir / f'Mega-Sena.{expected}.xlsx'
    archived.write_bytes(result.read_bytes())
    result.write_bytes(b'mutable canonical path advanced after adjudication')

    out = cha.advance_completed_epoch(tmp_path, active)
    assert out['status'] == 'PASS'
    assert out['result_file'].replace('\\', '/').endswith(f'SMART_STATE_ARCHIVE/adjudication-evidence/Mega-Sena.{expected}.xlsx')
    assert out['result_file_sha256'] == expected
    assert ledger['events'][0]['result_data_sha256'] == expected



def test_core_history_equal_normalizes_brazilian_day_first_mixed_dates():
    left = _frame(2)
    right = _frame(2)
    left['Data do Sorteio'] = ['11/03/1996', '18/03/1996']
    right['Data do Sorteio'] = [pd.Timestamp('1996-03-11'), pd.Timestamp('1996-03-18')]
    assert cha._core_history_equal(left, right) is True


def test_advance_resolves_legacy_windows_epoch_result_by_exact_suffix_and_hash(tmp_path, monkeypatch):
    canonical, through, result, ledger, active = _fixture(tmp_path, monkeypatch)
    ledger["events"][0]["result_data_file"] = r"C:\SMART-MEGA\runtime\learning_epochs\e1\Mega-Sena_through_4.xlsx"
    ledger["events"][0]["result_data_sha256"] = _sha(through)
    (through.parent / "SMART_SIGNAL_LEDGER.json").write_text(json.dumps(ledger), encoding="utf-8")

    out = cha.advance_completed_epoch(tmp_path, active)
    assert out["status"] == "PASS"
    assert out["result_file"] == "runtime/learning_epochs/e1/Mega-Sena_through_4.xlsx"
    assert out["result_file_sha256"] == _sha(through)


def test_advance_rejects_unrelated_windows_result_even_with_matching_hash(tmp_path, monkeypatch):
    _, through, _, ledger, active = _fixture(tmp_path, monkeypatch)
    ledger["events"][0]["result_data_file"] = r"C:\OTHER\runtime\learning_epochs\e2\Mega-Sena_through_4.xlsx"
    ledger["events"][0]["result_data_sha256"] = _sha(through)
    with pytest.raises(ValueError, match="result evidence missing or hash mismatch"):
        cha.advance_completed_epoch(tmp_path, active)
