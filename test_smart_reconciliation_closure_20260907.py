from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import smart_agent_skill_orchestration as orch
from smart_independent_oracle import _contrastive_guard_independent, validate_prediction_snapshot
from smart_signal_agent import SmartSignalAgent


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _draws(seed: int = 1907, n: int = 55) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.array([np.sort(rng.choice(np.arange(1, 61), 6, replace=False)) for _ in range(n)], dtype=int)


def _guarded_prediction(applied: bool = True) -> dict:
    draws = _draws()
    contests = np.arange(3001, 3001 + len(draws))
    target = int(contests[-1]) + 1
    base, _ = SmartSignalAgent(start=30).predict_next(draws, contests, target_contest=target)
    if applied:
        champion = list(base.top6)
    else:
        outsider = next(n for n in base.ranking60 if n not in set(base.top6))
        champion = list(base.top6[:5]) + [int(outsider)]
    pred, _ = SmartSignalAgent(start=30).predict_next(
        draws, contests, target_contest=target, champion_top6=champion
    )
    return pred.as_dict()


def test_independent_diversity_helper_guard_paths():
    ranking = list(range(1, 61))
    with pytest.raises(ValueError, match='top6 invalid'):
        _contrastive_guard_independent([1, 2, 3], ranking, [1, 2, 3, 4, 5, 6])
    with pytest.raises(ValueError, match='ranking invalid'):
        _contrastive_guard_independent([1, 2, 3, 4, 5, 6], ranking[:-1], [1, 2, 3, 4, 5, 6])
    already = _contrastive_guard_independent([1, 2, 3, 4, 5, 7], ranking, [1, 2, 3, 4, 5, 6])
    assert already == [1, 2, 3, 4, 5, 7]
    with pytest.raises(ValueError, match='minimum novelty failed'):
        _contrastive_guard_independent([1, 2, 3, 4, 5, 6], ranking, [1, 2, 3, 4, 5, 6], minimum_novelty=2)


def test_independent_oracle_rejects_corrupted_diversity_guard_fields():
    original = _guarded_prediction(applied=True)
    assert validate_prediction_snapshot(original)['verified'] is True

    bad = copy.deepcopy(original)
    bad['challenger_diversity_guard']['result_used'] = True
    with pytest.raises(ValueError, match='authority semantics'):
        validate_prediction_snapshot(bad)

    bad = copy.deepcopy(original)
    bad['challenger_diversity_guard']['champion_top6'] = None
    with pytest.raises(ValueError, match='payload invalid'):
        validate_prediction_snapshot(bad)

    bad = copy.deepcopy(original)
    bad['challenger_diversity_guard']['primary_top6'] = list(reversed(bad['challenger_diversity_guard']['primary_top6']))
    with pytest.raises(ValueError, match='primary mismatch'):
        validate_prediction_snapshot(bad)

    bad = copy.deepcopy(original)
    bad['challenger_diversity_guard']['final_top6'] = list(reversed(bad['challenger_diversity_guard']['primary_top6']))
    with pytest.raises(ValueError, match='final mismatch'):
        validate_prediction_snapshot(bad)

    bad = copy.deepcopy(original)
    bad['challenger_diversity_guard']['shadow_top6'] = list(bad['challenger_diversity_guard']['primary_top6'])
    with pytest.raises(ValueError, match='shadow mismatch'):
        validate_prediction_snapshot(bad)

    bad = copy.deepcopy(original)
    bad['challenger_diversity_guard']['decision_effect'] = True
    with pytest.raises(ValueError, match='authority semantics'):
        validate_prediction_snapshot(bad)

    bad = copy.deepcopy(original)
    bad['challenger_diversity_guard']['shadow_candidate_generated'] = not bad['challenger_diversity_guard']['shadow_candidate_generated']
    with pytest.raises(ValueError, match='generated flag mismatch'):
        validate_prediction_snapshot(bad)


def test_independent_oracle_active_guard_can_be_noop_when_already_novel():
    doc = _guarded_prediction(applied=False)
    assert doc['challenger_diversity_guard']['active'] is True
    assert doc['challenger_diversity_guard']['applied'] is False
    assert doc['challenger_diversity_guard']['shadow_only'] is True
    assert doc['challenger_diversity_guard']['shadow_candidate_generated'] is False
    audit = validate_prediction_snapshot(doc)
    assert audit['verified'] is True
    assert audit['decision_mode'] == 'quality_dynamic_anchor'


def _write_frame(path: Path, contests: list[int], include_contest: bool = True) -> None:
    if include_contest:
        frame = pd.DataFrame({'Concurso': contests})
    else:
        frame = pd.DataFrame({'Outro': contests or [1]})
    frame.to_excel(path, index=False)


def _reset_ready_epoch(data_name: str, data_sha: str, cutoff: int, *, parallel: dict | None = None) -> dict:
    doc = {
        'status': 'RESET_READY',
        'data_file': data_name,
        'data_sha256': data_sha,
        'cutoff_contest': cutoff,
        'target_contest': cutoff + 1,
        'state_paths': {
            'ledger': 'epoch/ledger.json',
            'state': 'epoch/state.json',
            'activation_authority': 'epoch/activation.json',
            'expansion_registry': 'epoch/expansion.json',
        },
    }
    if parallel is not None:
        doc['parallel_locked_experiment'] = parallel
    return doc


def test_pre_freeze_parallel_without_ledger_falls_back_to_epoch_state_paths(tmp_path: Path):
    data = tmp_path / 'snapshot.xlsx'
    _write_frame(data, [10, 11])
    parallel = {'target_contest': 11, 'freeze_sha256': 'a' * 64}
    active = _reset_ready_epoch('snapshot.xlsx', _sha(data), 11, parallel=parallel)
    (tmp_path / 'SMART_ACTIVE_EPOCH.json').write_text(json.dumps(active), encoding='utf-8')
    out = orch._resolve_pre_freeze_context(tmp_path)
    assert out['target_contest'] == 12
    assert out['ledger_file'] == 'epoch/ledger.json'
    assert out['ledger_sha256'] is None


def test_pre_freeze_parallel_duplicate_adjudication_fails_closed(tmp_path: Path):
    freeze_sha = 'b' * 64
    parallel = {'target_contest': 55, 'freeze_sha256': freeze_sha}
    active = {'status': 'RESET_READY', 'parallel_locked_experiment': parallel}
    (tmp_path / 'SMART_ACTIVE_EPOCH.json').write_text(json.dumps(active), encoding='utf-8')
    event = {'event_type': 'ADJUDICATION', 'target_contest': 55, 'freeze_sha256': freeze_sha}
    (tmp_path / 'SMART_SIGNAL_LEDGER.json').write_text(json.dumps({'events': [event, dict(event)]}), encoding='utf-8')
    with pytest.raises(ValueError, match='duplicate adjudications'):
        orch._resolve_pre_freeze_context(tmp_path)


def test_pre_freeze_parallel_single_adjudication_rolls_to_canonical_history(tmp_path: Path):
    canonical = tmp_path / 'Mega-Sena.xlsx'
    _write_frame(canonical, [70, 71, 72])
    freeze_sha = 'c' * 64
    parallel = {'target_contest': 72, 'freeze_sha256': freeze_sha}
    active = {'status': 'FROZEN', 'parallel_locked_experiment': parallel}
    (tmp_path / 'SMART_ACTIVE_EPOCH.json').write_text(json.dumps(active), encoding='utf-8')
    event = {'event_type': 'ADJUDICATION', 'target_contest': 72, 'freeze_sha256': freeze_sha}
    ledger = tmp_path / 'SMART_SIGNAL_LEDGER.json'
    ledger.write_text(json.dumps({'events': [event]}), encoding='utf-8')
    out = orch._resolve_pre_freeze_context(tmp_path)
    assert out['target_contest'] == 73
    assert out['cutoff_contest'] == 72
    assert out['data_file'] == 'Mega-Sena.xlsx'
    assert out['ledger_file'] == 'SMART_SIGNAL_LEDGER.json'
    assert out['ledger_sha256'] == _sha(ledger)


def test_build_context_fail_closed_data_guards_and_reset_phase(tmp_path: Path):
    with pytest.raises(ValueError, match='canonical Mega-Sena.xlsx is missing'):
        orch._resolve_build_context(tmp_path)

    data = tmp_path / 'Mega-Sena.xlsx'
    _write_frame(data, [1], include_contest=False)
    with pytest.raises(ValueError, match='no Concurso column'):
        orch._resolve_build_context(tmp_path)

    _write_frame(data, [])
    with pytest.raises(ValueError, match='no contests'):
        orch._resolve_build_context(tmp_path)

    (tmp_path / 'SMART_ACTIVE_EPOCH.json').write_text(json.dumps({'status': 'RESET_READY'}), encoding='utf-8')
    assert orch.resolve_runtime_phase(tmp_path, 'AUTO') == 'PRE_FREEZE'
