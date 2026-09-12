from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

import smart_canonical_history_advance as cha


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_advance_accepts_value_equal_prefix_with_dtype_shift(tmp_path: Path, monkeypatch):
    rows = []
    for contest in range(1, 5):
        rows.append({
            'Concurso': contest,
            'Data do Sorteio': pd.Timestamp('2026-01-01') + pd.Timedelta(days=contest),
            **{f'Bola{i}': contest + i - 1 for i in range(1, 7)},
            'Cidade / UF': None if contest < 4 else 'SP',
        })
    through_frame = pd.DataFrame(rows)
    canonical_frame = through_frame.iloc[:3].copy()
    # Round-tripping these files yields equal values for the first 3 rows,
    # while the appended string can change pandas dtype inference in the through prefix.
    canonical = tmp_path / 'Mega-Sena.xlsx'
    epoch = tmp_path / 'runtime' / 'learning_epochs' / 'e1'
    epoch.mkdir(parents=True)
    through = epoch / 'Mega-Sena_through_4.xlsx'
    canonical_frame.to_excel(canonical, index=False)
    through_frame.to_excel(through, index=False)
    result = epoch / 'Mega-Sena_result_4.xlsx'
    pd.DataFrame([{'Concurso': 4, **{f'Bola{i}': 4 + i - 1 for i in range(1, 7)}}]).to_excel(result, index=False)
    ledger = {'schema': 'SMART_CHAMPION_CHALLENGER_LEDGER_1', 'events': [{
        'event_type': 'ADJUDICATION', 'target_contest': 4,
        'result_data_file': str(result.relative_to(tmp_path)).replace('\\','/'),
        'result_data_sha256': _sha(result), 'actual_numbers': [4,5,6,7,8,9],
    }]}
    ledger_path = epoch / 'SMART_SIGNAL_LEDGER.json'
    ledger_path.write_text(json.dumps(ledger), encoding='utf-8')
    active = {'project': 'SMART-MEGA', 'target_contest': 4,
              'state_paths': {'ledger': str(ledger_path.relative_to(tmp_path)).replace('\\','/')}}
    monkeypatch.setattr(cha, 'load_ledger', lambda path: ledger)
    monkeypatch.setattr(cha, 'validate_target_sequence', lambda *a, **k: {'valid': True, 'adjudicated': True, 'sequence_sha256': 'a'*64})
    assert not pd.read_excel(canonical).equals(pd.read_excel(through).iloc[:-1].reset_index(drop=True))
    out = cha.advance_completed_epoch(tmp_path, active)
    assert out['status'] == 'PASS'
    assert pd.read_excel(canonical)['Concurso'].astype(int).tolist() == [1,2,3,4]
