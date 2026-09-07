from __future__ import annotations

import copy
import json
import runpy
import sys
from pathlib import Path

import pandas as pd
import pytest

import smart_agent_runtime as ar
import smart_agent_skill_orchestration as orch
import smart_independent_oracle as oracle
import smart_agent_skill_orchestration as aso

ROOT = Path(__file__).resolve().parent


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj), encoding='utf-8')


def _epoch(state_paths, *, data_file=None, data_sha256=None, status='RESET_READY', cutoff=1, target=2):
    return {
        'status': status,
        'state_paths': state_paths,
        'data_file': data_file,
        'data_sha256': data_sha256,
        'cutoff_contest': cutoff,
        'target_contest': target,
    }


def _paths():
    return {
        'ledger': 'ledger.json',
        'state': 'state.json',
        'activation_authority': 'authority.json',
        'expansion_registry': 'registry.json',
    }


def test_state_path_contract_and_root_escape_guards(tmp_path: Path):
    active = tmp_path / 'SMART_ACTIVE_EPOCH.json'
    _write_json(active, {'state_paths': None})
    with pytest.raises(ValueError, match='state_paths missing'):
        orch._resolve_state_paths(tmp_path)
    _write_json(active, {'state_paths': {'ledger': 'ledger.json'}})
    with pytest.raises(ValueError, match='state_paths incomplete'):
        orch._resolve_state_paths(tmp_path)
    with pytest.raises(ValueError, match='escapes project root'):
        orch._project_relative(tmp_path, tmp_path.parent / 'outside.json')


def test_pre_freeze_context_fail_closed_and_fallback_paths(tmp_path: Path):
    active = tmp_path / 'SMART_ACTIVE_EPOCH.json'
    _write_json(active, _epoch(_paths()))
    with pytest.raises(ValueError, match='data_file missing'):
        orch._resolve_pre_freeze_context(tmp_path)

    _write_json(active, _epoch(_paths(), data_file='missing.xlsx', data_sha256='x'))
    with pytest.raises(ValueError, match='immutable data is missing'):
        orch._resolve_pre_freeze_context(tmp_path)

    data = tmp_path / 'snapshot.xlsx'
    pd.DataFrame([{'Concurso': 1}]).to_excel(data, index=False)
    _write_json(active, _epoch(_paths(), data_file=data.name, data_sha256='0'*64))
    with pytest.raises(ValueError, match='immutable data hash mismatch'):
        orch._resolve_pre_freeze_context(tmp_path)

    _write_json(active, _epoch(_paths(), data_file=data.name, data_sha256=orch._sha256(data), cutoff=1, target=99))
    with pytest.raises(ValueError, match='target/cutoff differs'):
        orch._resolve_pre_freeze_context(tmp_path)

    active.unlink()
    canonical = tmp_path / 'Mega-Sena.xlsx'
    pd.DataFrame([{'Concurso': 7}]).to_excel(canonical, index=False)
    ctx = orch._resolve_pre_freeze_context(tmp_path)
    assert ctx['cutoff_contest'] == 7 and ctx['target_contest'] == 8

    pd.DataFrame([{'X': 1}]).to_excel(canonical, index=False)
    with pytest.raises(ValueError, match='no Concurso'):
        orch._resolve_pre_freeze_context(tmp_path)
    pd.DataFrame(columns=['Concurso']).to_excel(canonical, index=False)
    with pytest.raises(ValueError, match='no contests'):
        orch._resolve_pre_freeze_context(tmp_path)


def test_runtime_phase_parse_and_status_guards(tmp_path: Path):
    with pytest.raises(ValueError, match='phase must be'):
        orch.resolve_runtime_phase(tmp_path, 'BAD')
    active = tmp_path / 'SMART_ACTIVE_EPOCH.json'
    active.write_text('{bad json', encoding='utf-8')
    with pytest.raises(ValueError, match='cannot be parsed'):
        orch.resolve_runtime_phase(tmp_path, 'AUTO')
    _write_json(active, {'status': 'UNKNOWN'})
    with pytest.raises(ValueError, match='has no runtime phase'):
        orch.resolve_runtime_phase(tmp_path, 'AUTO')
    active.unlink()
    assert orch.resolve_runtime_phase(tmp_path, 'AUTO') == 'POST_FREEZE'


def test_post_freeze_build_executes_active_freeze_branch(monkeypatch):
    freeze = ROOT / 'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json'
    data = ROOT / 'Mega-Sena_through_3053_v2.xlsx'
    ledger = ROOT / 'SMART_SIGNAL_LEDGER.json'
    ctx = {
        'target_contest': 3054,
        'cutoff_contest': 3053,
        'freeze_file': freeze.name,
        'freeze_sha256': orch._sha256(freeze),
        'data_file': data.name,
        'data_sha256': orch._sha256(data),
        'signal_state_file': None,
        'signal_state_sha256': None,
        'ledger_file': ledger.name,
        'ledger_sha256': orch._sha256(ledger),
        'pending_target': True,
        'phase': 'POST_FREEZE',
    }
    monkeypatch.setattr(orch, '_resolve_active_context', lambda root: ctx)
    doc = orch.build_orchestration(ROOT, phase='POST_FREEZE')
    assert doc['phase'] == 'POST_FREEZE'
    assert doc['checks']['active_freeze_present'] is True


def test_agent_runtime_critical_files_without_active_epoch(tmp_path: Path):
    runtime = object.__new__(ar.SmartAgentRuntime)
    runtime.root = tmp_path
    runtime.active_context = {
        'freeze_file': None, 'data_file': None, 'signal_state_file': None, 'ledger_file': None,
    }
    files = runtime._critical_files()
    assert 'SMART_ACTIVE_EPOCH.json' not in files


def test_functional_gate_cli_dispatch_is_exercised(monkeypatch, tmp_path: Path):
    output = tmp_path / 'functional.json'
    monkeypatch.setattr(sys, 'argv', ['smart_agent_skill_functional_gate.py', '--phase', 'PRE_FREEZE', '--output', str(output)])
    runpy.run_path(str(ROOT / 'smart_agent_skill_functional_gate.py'), run_name='__main__')
    assert output.is_file()



def test_oracle_multi_without_quality_dynamic_takes_optional_branch():
    frozen = json.loads((ROOT / 'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json').read_text(encoding='utf-8'))
    prediction = copy.deepcopy(frozen['challenger'])
    prediction['multi_challengers'] = {'policies': None}
    out = oracle.validate_prediction_snapshot(prediction)
    assert out['verified'] is True


def test_pre_freeze_context_without_active_epoch_covers_fallback(tmp_path):
    import pandas as pd
    pd.DataFrame({'Concurso':[1,2], 'Bola1':[1,2], 'Bola2':[3,4], 'Bola3':[5,6], 'Bola4':[7,8], 'Bola5':[9,10], 'Bola6':[11,12]}).to_excel(tmp_path/'Mega-Sena.xlsx', index=False)
    ctx = aso._resolve_pre_freeze_context(tmp_path)
    assert ctx['cutoff_contest'] == 2
    assert ctx['target_contest'] == 3
    assert ctx['freeze_file'] is None





def test_oracle_governed_freeze_consistent_path():
    frozen = json.loads((ROOT / 'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json').read_text(encoding='utf-8'))
    out = oracle.validate_frozen_decision(frozen)
    assert out['verified'] is True
    assert out['final_top6'] == frozen['governed_challenger_top6']

