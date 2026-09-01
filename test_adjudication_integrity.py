from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import adjudicate_signal_challenger as adj
import smart_champion_challenger as cc
from test_smart_coverage_governance import make_freeze_ledger, result_excel


def test_eprocess_rejects_invalid_hits_and_nonfinite_previous_evalue():
    with pytest.raises(ValueError, match='hits'):
        adj._next_e_value({'schema': cc.LEDGER_SCHEMA, 'events': []}, -1, 1)
    freeze = {'event_type': 'FREEZE', 'target_contest': 10, 'freeze_sha256': 'a' * 64,
              'frozen_before_result': True, 'causal_cutoff': True}
    ad = {'event_type': 'ADJUDICATION', 'target_contest': 10, 'freeze_sha256': 'a' * 64,
          'challenger_hits': 1, 'champion_hits': 1, 'e_value_after': float('nan')}
    ledger = {'schema': cc.LEDGER_SCHEMA, 'events': [freeze, ad]}
    with pytest.raises(ValueError, match='previous e-value'):
        adj._next_e_value(ledger, 1, 1)


def test_adjudication_requires_snapshot_equal_to_frozen_artifact(tmp_path: Path):
    ledger_path, _ = make_freeze_ledger(tmp_path, target=20)
    ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
    ledger['events'][0]['snapshot']['weights']['freq25'] = 0.99
    ledger_path.write_text(json.dumps(ledger), encoding='utf-8')
    with pytest.raises(ValueError, match='snapshot differs from artifact'):
        adj.adjudicate(result_excel(tmp_path / 'r.xlsx', 20), 20, ledger_path)


def test_adjudication_rejects_fractional_official_number(tmp_path: Path):
    ledger_path, _ = make_freeze_ledger(tmp_path, target=21)
    row = {'Concurso': 21, 'Bola1': 1.5, 'Bola2': 2, 'Bola3': 3, 'Bola4': 4, 'Bola5': 5, 'Bola6': 6}
    result = tmp_path / 'fractional.xlsx'
    pd.DataFrame([row]).to_excel(result, index=False)
    with pytest.raises(ValueError, match='integer lottery numbers'):
        adj.adjudicate(result, 21, ledger_path)


def test_freeze_event_and_artifact_top6_must_match(tmp_path: Path):
    ledger_path, _ = make_freeze_ledger(tmp_path, target=22)
    ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
    ledger['events'][0]['champion_top6'] = [1, 2, 3, 4, 5, 8]
    ledger_path.write_text(json.dumps(ledger), encoding='utf-8')
    with pytest.raises(ValueError, match='top6 differs'):
        adj.adjudicate(result_excel(tmp_path / 'r22.xlsx', 22), 22, ledger_path)
