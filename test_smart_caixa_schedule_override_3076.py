from datetime import datetime
import json
from pathlib import Path

import pytest
import smart_target_schedule as schedules


def _receipt(root: Path, *, next_date='27/10/2026', next_contest=3076):
    import pandas as pd
    pd.DataFrame([{ "Concurso": 3075, "Data do Sorteio": "26/10/2026",
        **{f"Bola{i}": x for i, x in enumerate((7, 10, 14, 27, 36, 55), 1)}}]).to_excel(root / "Mega-Sena.xlsx", index=False)
    path = root / 'runtime' / 'procedural_sources' / 'caixa_api_previous' / '3075.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        'numero': 3075, 'dataApuracao': '26/10/2026',
        'numeroConcursoProximo': next_contest,
        'dataProximoConcurso': next_date,
        'listaDezenas': ['07', '10', '14', '27', '36', '55'],
    }), encoding='utf-8')
    return path


def test_caixa_api_receipt_overrides_superseded_special_schedule(tmp_path, monkeypatch):
    receipt = _receipt(tmp_path)
    monkeypatch.setattr(schedules, '_previous_contest_date', lambda root, target: datetime(2026, 10, 26))
    policy_path = tmp_path / 'SMART_MEGA_SENA_DRAW_TIME_POLICY.json'
    policy_path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(schedules, 'load_draw_time_policy', lambda root, policy: (
        {'weekday_times': {'1': '21:00'}, 'timezone': 'America/Sao_Paulo',
         'authority': 'CAIXA_LOTERIAS_OFFICIAL_DRAW_RULES'}, policy_path
    ))
    doc = schedules.resolve_target_schedule(tmp_path, 3076)
    assert doc['target_date'] == '27/10/2026'
    assert doc['scheduled_datetime'] == '2026-10-27T21:00:00-03:00'
    assert doc['source_file'] == receipt.relative_to(tmp_path).as_posix()
    assert doc['authority'] == 'CAIXA_PREVIOUS_RESULT_API_RECEIPT'
    assert doc['result_used'] is False


def test_caixa_api_receipt_rejects_invalid_next_contest_sequence(tmp_path, monkeypatch):
    _receipt(tmp_path, next_contest=3077)
    monkeypatch.setattr(schedules, '_previous_contest_date', lambda root, target: datetime(2026, 10, 26))
    with pytest.raises(ValueError, match='CAIXA.*next contest'):
        schedules.resolve_target_schedule(tmp_path, 3076)