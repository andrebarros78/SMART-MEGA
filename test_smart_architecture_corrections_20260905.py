import ast
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import smart_v2_engine as engine
from smart_data_quality_gate import audit_draw_file
from smart_independent_oracle import validate_frozen_decision
from smart_signal_agent import SmartSignalAgent
from smart_signal_quality import PROFILE_DRIFT_HEALTH, SignalQualityState

ROOT = Path(__file__).resolve().parent


def _save(tmp_path, rows, name='draws.xlsx'):
    path = tmp_path / name
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def test_loader_rejects_fractional_values(tmp_path):
    rows = [
        {'Concurso': 1.9, 'Bola1': 1.9, 'Bola2': 2, 'Bola3': 3, 'Bola4': 4, 'Bola5': 5, 'Bola6': 6},
        {'Concurso': 2, 'Bola1': 7, 'Bola2': 8, 'Bola3': 9, 'Bola4': 10, 'Bola5': 11, 'Bola6': 12},
    ]
    path = _save(tmp_path, rows)
    with pytest.raises(ValueError, match='inteiro|integer|integral'):
        engine.load_draws(path)
    report = audit_draw_file(path)
    assert report.status == 'FAIL'
    assert report.checks['integer_values'] is False


def test_loader_and_quality_gate_reject_contest_gap(tmp_path):
    rows = [
        {'Concurso': 1, 'Bola1': 1, 'Bola2': 2, 'Bola3': 3, 'Bola4': 4, 'Bola5': 5, 'Bola6': 6},
        {'Concurso': 3, 'Bola1': 7, 'Bola2': 8, 'Bola3': 9, 'Bola4': 10, 'Bola5': 11, 'Bola6': 12},
    ]
    path = _save(tmp_path, rows)
    with pytest.raises(ValueError, match='lacuna|contiguous|consecut'):
        engine.load_draws(path)
    report = audit_draw_file(path)
    assert report.status == 'FAIL'
    assert report.checks['contiguous_contests'] is False
    assert report.missing_contest_count == 1


def test_profile_drift_affects_context_and_is_observed_causally():
    state = SignalQualityState('freq25', 'freq')
    state.profile_drift_cooldown = 10
    metrics = state.metrics(1.0)
    assert metrics['profile_drift_active'] is True
    assert metrics['drift_active'] is True
    assert metrics['profile_drift_penalty_enabled'] is True
    assert metrics['context'] == PROFILE_DRIFT_HEALTH
    assert metrics['context'] < 1.0

    rng = np.random.default_rng(20260905)
    draws = np.array([np.sort(rng.choice(np.arange(1, 61), 6, replace=False)) for _ in range(45)], dtype=int)
    contests = np.arange(1, 46)
    agent = SmartSignalAgent(start=20)
    agent.predict_next(draws, contests, target_contest=46)
    assert all(s.profile_n == (45 - 20 + 1) for s in agent.states.values())


def test_independent_oracle_has_no_project_import_and_recomputes_3054():
    source = ROOT / 'smart_independent_oracle.py'
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert not [name for name in imports if name == 'smart' or name.startswith('smart_')]
    import json
    frozen = json.loads((ROOT / 'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json').read_text(encoding='utf-8'))
    result = validate_frozen_decision(frozen)
    assert result['status'] == 'PASS'
    assert result['verified'] is True
    assert result['production_engine_imported'] is False
    assert result['final_top6'] == [11, 30, 27, 35, 10, 38]


def test_freshness_is_derived_from_forecast_horizon():
    rng = np.random.default_rng(20260906)
    draws = np.array([np.sort(rng.choice(np.arange(1, 61), 6, replace=False)) for _ in range(40)], dtype=int)
    contests = np.arange(1, 41)
    pred, _ = SmartSignalAgent(start=20).predict_next(draws, contests, target_contest=43)
    expected = math.exp(-0.25 * 2)
    assert all(math.isclose(row['freshness'], expected, rel_tol=1e-12) for row in pred.quality_metrics.values())
    assert all(row['forecast_horizon_contests'] == 3 for row in pred.quality_metrics.values())
    assert all(row['freshness_source'] == 'causal_score_age_from_cutoff_to_target' for row in pred.quality_metrics.values())
