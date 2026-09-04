from __future__ import annotations

import copy
import json
import math
import runpy
import sys
from pathlib import Path

import pytest

import adjudicate_signal_challenger as adj
import smart_portfolio_optimizer as po
import smart_portfolio_pipeline as pp
import smart_v2_production as prod


def _scores():
    return {n: float(61 - n) for n in range(1, 61)}


@pytest.mark.parametrize('cfg', [
    po.PortfolioConfig(game_count=0),
    po.PortfolioConfig(numbers_per_game=5),
    po.PortfolioConfig(candidate_pool_size=5),
    po.PortfolioConfig(max_pairwise_overlap=-1),
    po.PortfolioConfig(coverage_bonus=-1),
    po.PortfolioConfig(time_limit_seconds=0),
    po.PortfolioConfig(min_number_exposure=-1),
    po.PortfolioConfig(max_number_exposure=-1),
    po.PortfolioConfig(min_number_exposure=1, max_number_exposure=0),
])
def test_portfolio_config_all_fail_closed_guards(cfg):
    with pytest.raises(ValueError):
        cfg.validate()


def test_portfolio_score_and_normalization_guards(monkeypatch):
    with pytest.raises(ValueError):
        po._coerce_scores({0: 1.0, **{n: 1.0 for n in range(1, 7)}})
    with pytest.raises(ValueError):
        po._coerce_scores({1: math.inf, **{n: 1.0 for n in range(2, 7)}})
    with pytest.raises(ValueError):
        po._coerce_scores({n: 1.0 for n in range(1, 6)})
    assert set(po._normalized_scores({n: 1.0 for n in range(1, 7)}).values()) == {1.0}
    monkeypatch.setattr(po, '_coerce_scores', lambda _: {n: float(n) for n in range(1, 6)})
    with pytest.raises(ValueError, match='candidate pool'):
        po.optimize_portfolio(_scores(), po.PortfolioConfig(candidate_pool_size=6))


def test_portfolio_infeasible_and_freeze_input_guards(tmp_path):
    with pytest.raises(RuntimeError, match='portfolio optimization failed'):
        po.optimize_portfolio(_scores(), po.PortfolioConfig(game_count=2, candidate_pool_size=6, max_pairwise_overlap=4))
    f = tmp_path / 'freeze.json'
    f.write_text(json.dumps({'champion': {'aggregate_scores': {str(n): 1.0 for n in range(1, 61)}}}), encoding='utf-8')
    with pytest.raises(KeyError):
        po.optimize_from_freeze(f, head='missing')
    f.write_text(json.dumps({'champion': {'aggregate_scores': []}}), encoding='utf-8')
    with pytest.raises(ValueError, match='aggregate_scores'):
        po.optimize_from_freeze(f)


def _pipeline_freeze(tmp_path: Path) -> Path:
    p = tmp_path / 'freeze.json'
    p.write_text(json.dumps({
        'target_contest': 10, 'cutoff_contest': 9, 'frozen_before_result': True,
        'champion': {'top6': [1,2,3,4,5,6], 'aggregate_scores': {str(n): float(61-n) for n in range(1,61)}},
    }), encoding='utf-8')
    return p


def test_pipeline_cutoff_champion_failure_and_output(tmp_path, monkeypatch):
    p = _pipeline_freeze(tmp_path)
    obj = json.loads(p.read_text())
    obj['cutoff_contest'] = 8; p.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='immediately follow'):
        pp.build_portfolio_package(p, config=po.PortfolioConfig(game_count=1, candidate_pool_size=6))
    obj['cutoff_contest'] = 9; obj['champion'] = None; p.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='champion head'):
        pp.build_portfolio_package(p, config=po.PortfolioConfig(game_count=1, candidate_pool_size=6))
    p = _pipeline_freeze(tmp_path)
    out = tmp_path / 'portfolio.json'
    r = pp.build_portfolio_package(p, out, config=po.PortfolioConfig(game_count=1, candidate_pool_size=6))
    assert r['artifact_file'] == out.name and out.is_file()


def test_pipeline_fail_status_guard(tmp_path, monkeypatch):
    p = _pipeline_freeze(tmp_path)
    control = {'games': [[1,2,3,4,5,6]]}
    bad = {
        'games': [[1,2,3,4,5,6]], 'solver_status': 'FEASIBLE', 'objective_value': 1.0, 'best_objective_bound': 1.0,
        'metrics': {'max_pairwise_overlap_observed': 0, 'unique_number_count': 6, 'min_number_exposure_observed': 1, 'max_number_exposure_observed': 1},
        'contract': {'portfolio_only': True, 'predictive_scores_unchanged': True},
    }
    calls = {'n': 0}
    def fake(*args, **kwargs):
        calls['n'] += 1
        return control if calls['n'] == 1 else bad
    monkeypatch.setattr(pp, 'optimize_from_freeze', fake)
    with pytest.raises(RuntimeError, match='failed validation'):
        pp.build_portfolio_package(p, config=po.PortfolioConfig(game_count=2, candidate_pool_size=6))


def test_pipeline_main_real_path(tmp_path, monkeypatch, capsys):
    p = _pipeline_freeze(tmp_path); out = tmp_path / 'out.json'
    monkeypatch.setattr(sys, 'argv', ['smart_portfolio_pipeline.py', '--freeze', str(p), '--out', str(out)])
    pp.main()
    assert out.is_file() and 'PASS' in capsys.readouterr().out


def test_v2_remaining_guards_and_entrypoint(tmp_path, monkeypatch):
    assert prod._is_hex64('z' * 64) is False
    with pytest.raises(ValueError, match='malformed legacy production audit'):
        prod.decide({'walk_forward': {}}, None)
    audit = tmp_path / 'audit.json'; audit.write_text(json.dumps({
        'walk_forward': {'excess_hits': 1, 'diagnostic_z_vs_uniform': 3, 'total_hits': 2},
        'placebo': {'total_hits': 1}, 'monte_carlo_null': {'false_positive_rate_z_ge_2': 0.01},
    }), encoding='utf-8')
    data = tmp_path / 'data.bin'; data.write_bytes(b'data')
    out = tmp_path / 'state.json'
    monkeypatch.setattr(sys, 'argv', ['smart_v2_production.py', '--audit', str(audit), '--data', str(data), '--ledger', str(tmp_path/'missing.json'), '--out', str(out)])
    prod.main(); assert out.is_file()


def _valid_portfolio(tmp_path: Path):
    path = tmp_path / 'portfolio.json'
    freeze_sha = 'f' * 64; opt = 'a' * 64; pipe = 'b' * 64
    body = {'games': [[1,2,3,4,5,6]], 'metrics': {'x': 1}}
    obj = {
        'schema': 'SMART_PORTFOLIO_PIPELINE_V1', 'status': 'PASS', 'target_contest': 10, 'cutoff_contest': 9,
        'freeze_sha256': freeze_sha, 'optimizer_sha256': opt, 'pipeline_sha256': pipe,
        'portfolio': body,
        'contract': {'post_scoring_component': True, 'predictive_model_unchanged': True, 'no_retroactive_result_use': True},
    }
    path.write_text(json.dumps(obj), encoding='utf-8')
    fr = {'freeze_file': str(tmp_path/'freeze.json'), 'freeze_sha256': freeze_sha, 'portfolio_file': str(path),
          'portfolio_sha256': adj.sha256(path), 'portfolio_status': 'PASS', 'portfolio_games': body['games'], 'portfolio_metrics': body['metrics']}
    frozen = {'portfolio_optimizer_sha256': opt, 'portfolio_pipeline_sha256': pipe, 'portfolio_policy': {'enabled': True}}
    return path, fr, frozen, obj


def test_adjudication_basic_numeric_and_path_guards(tmp_path):
    with pytest.raises(ValueError): adj._strict_int(True, 'x')
    with pytest.raises(ValueError): adj._strict_int(7, 'x', hi=6)
    with pytest.raises(ValueError): adj._strict_top6([1,2], 'x')
    fr = {'freeze_file': str(tmp_path/'f.json')}
    assert adj._resolve_evidence_file('missing.json', fr) == tmp_path/'missing.json'


def test_adjudication_state_archive_all_guards(tmp_path):
    fr = {'freeze_file': str(tmp_path/'freeze.json')}
    frozen = {'signal_state_archive_file': 1, 'signal_state_archive_sha256': 'a'*64}
    with pytest.raises(ValueError, match='incomplete'): adj._validate_state_archive_evidence(fr, frozen)
    frozen = {'signal_state_archive_file': 's.json', 'signal_state_archive_sha256': 'a'*64, 'signal_state_sha256': 'b'*64}
    with pytest.raises(ValueError, match='differs from state'): adj._validate_state_archive_evidence(fr, frozen)
    frozen['signal_state_sha256']='a'*64
    with pytest.raises(ValueError, match='ledger state archive'): adj._validate_state_archive_evidence(fr, frozen)
    fr.update({'state_archive_file':'s.json','state_archive_sha256':'a'*64})
    with pytest.raises(ValueError, match='missing'): adj._validate_state_archive_evidence(fr, frozen)
    s=tmp_path/'s.json'; s.write_text('x')
    with pytest.raises(ValueError, match='hash mismatch'): adj._validate_state_archive_evidence(fr, frozen)
    h=adj.sha256(s); frozen['signal_state_archive_sha256']=h; frozen['signal_state_sha256']=h; fr['state_archive_sha256']=h
    adj._validate_state_archive_evidence(fr, frozen)


def _write_portfolio(path, obj, fr):
    path.write_text(json.dumps(obj), encoding='utf-8')
    fr['portfolio_sha256'] = adj.sha256(path)


def test_adjudication_portfolio_all_fail_closed_guards(tmp_path):
    path, fr, frozen, obj = _valid_portfolio(tmp_path)
    adj._validate_portfolio_evidence(fr, frozen, 10)
    with pytest.raises(ValueError, match='missing portfolio evidence'):
        adj._validate_portfolio_evidence({}, {'portfolio_policy': {'enabled': True}}, 10)
    with pytest.raises(ValueError, match='incomplete'):
        adj._validate_portfolio_evidence({'portfolio_file': 'x'}, {}, 10)
    badfr = copy.deepcopy(fr); badfr['portfolio_file'] = str(tmp_path/'none.json')
    with pytest.raises(ValueError, match='artifact missing'): adj._validate_portfolio_evidence(badfr, frozen, 10)
    badfr = copy.deepcopy(fr); badfr['portfolio_sha256']='0'*64
    with pytest.raises(ValueError, match='hash mismatch'): adj._validate_portfolio_evidence(badfr, frozen, 10)
    path.write_text('{bad'); fr['portfolio_sha256']=adj.sha256(path)
    with pytest.raises(ValueError, match='invalid JSON'): adj._validate_portfolio_evidence(fr, frozen, 10)
    for label, mutate, match in [
        ('schema', lambda o: o.update(schema='bad'), 'schema invalid'),
        ('status', lambda o: o.update(status='FAIL'), 'not PASS'),
        ('target', lambda o: o.update(target_contest=11), 'target mismatch'),
        ('cutoff', lambda o: o.update(cutoff_contest=8), 'cutoff mismatch'),
        ('freeze', lambda o: o.update(freeze_sha256='0'*64), 'active freeze'),
        ('optimizer', lambda o: o.update(optimizer_sha256='0'*64), 'optimizer hash'),
        ('pipeline', lambda o: o.update(pipeline_sha256='0'*64), 'pipeline hash'),
        ('body', lambda o: o.update(portfolio=[]), 'body missing'),
    ]:
        _, fr, frozen, base = _valid_portfolio(tmp_path); mutate(base); _write_portfolio(path, base, fr)
        with pytest.raises(ValueError, match=match): adj._validate_portfolio_evidence(fr, frozen, 10)
    _, fr, frozen, base = _valid_portfolio(tmp_path); base['portfolio']['games']=[[7,8,9,10,11,12]]; _write_portfolio(path,base,fr)
    with pytest.raises(ValueError, match='games differ'): adj._validate_portfolio_evidence(fr,frozen,10)
    _, fr, frozen, base = _valid_portfolio(tmp_path); base['portfolio']['metrics']={'x':2}; _write_portfolio(path,base,fr)
    with pytest.raises(ValueError, match='metrics differ'): adj._validate_portfolio_evidence(fr,frozen,10)
    _, fr, frozen, base = _valid_portfolio(tmp_path); base['contract']['post_scoring_component']=False; _write_portfolio(path,base,fr)
    with pytest.raises(ValueError, match='causal contract'): adj._validate_portfolio_evidence(fr,frozen,10)


def _freeze_contract_base():
    champion=[1,2,3,4,5,6]; challenger=[7,8,9,10,11,12]
    fr={'target_contest':10,'cutoff_contest':9,'frozen_before_result':True,'causal_cutoff':True,'data_sha256':'d'*64,
        'champion_top6':champion,'challenger_top6':challenger,'snapshot':{'raw_signals':{'x':1}},'hashes':{'engine':'a'*64,'state':'b'*64}}
    frozen={'target_contest':10,'cutoff_contest':9,'frozen_before_result':True,'causal_cutoff':True,'data_sha256':'d'*64,
            'champion':{'top6':champion,'raw_signals':{'x':1}},'challenger':{'top6':challenger,'raw_signals':{'x':1}},
            'engine_sha256':'a'*64,'signal_state_sha256':'b'*64}
    return fr,frozen


def test_adjudication_freeze_contract_all_major_guards():
    fr,fz=_freeze_contract_base(); adj._validate_freeze_event_against_artifact(fr,fz,10)
    cases=[]
    cases.append((None, fz, 'objects'))
    a,b=_freeze_contract_base(); a['target_contest']=11; cases.append((a,b,'event target'))
    a,b=_freeze_contract_base(); b['target_contest']=11; cases.append((a,b,'artifact target'))
    a,b=_freeze_contract_base(); a['causal_cutoff']=False; cases.append((a,b,'event lacks'))
    a,b=_freeze_contract_base(); b['causal_cutoff']=False; cases.append((a,b,'artifact lacks'))
    a,b=_freeze_contract_base(); a['cutoff_contest']=8; cases.append((a,b,'cutoff mismatch'))
    a,b=_freeze_contract_base(); a['data_sha256']='x'; cases.append((a,b,'data hash'))
    a,b=_freeze_contract_base(); a['champion_top6']=[1,2,3,4,5,7]; cases.append((a,b,'top6 differs'))
    a,b=_freeze_contract_base(); a['snapshot']=None; cases.append((a,b,'snapshot'))
    a,b=_freeze_contract_base(); a['snapshot']={'unknown':1}; cases.append((a,b,'unbound'))
    a,b=_freeze_contract_base(); a['snapshot']={'raw_signals':{'x':2}}; cases.append((a,b,'snapshot differs'))
    a,b=_freeze_contract_base(); a['promotion_lineage']={'x':1}; b['promotion_lineage']={'x':2}; cases.append((a,b,'promotion lineage'))
    a,b=_freeze_contract_base(); a['hashes']={}; cases.append((a,b,'hashes missing'))
    a,b=_freeze_contract_base(); b.pop('engine_sha256'); cases.append((a,b,'component hash'))
    for a,b,match in cases:
        with pytest.raises(ValueError, match=match): adj._validate_freeze_event_against_artifact(a,b,10)


def test_adjudication_eprocess_extreme_guards(monkeypatch):
    monkeypatch.setattr(adj, 'paired_events', lambda ledger: [])
    monkeypatch.setattr(adj, 'E_BET_LAMBDA', 10.0)
    with pytest.raises(ValueError, match='factor'): adj._next_e_value({'events':[]},0,6)
    monkeypatch.setattr(adj, 'E_BET_LAMBDA', 0.5)
    monkeypatch.setattr(adj, 'paired_events', lambda ledger: [(None,None,{'e_value_after':1.7e308})])
    with pytest.raises(ValueError, match='result'): adj._next_e_value({'events':[]},6,0)


def test_append_helpers_active_freeze_mismatch(monkeypatch, tmp_path):
    ledger={'events':[{'event_type':'ADJUDICATION','target_contest':10,'freeze_sha256':'a','actual_numbers':[1,2,3,4,5,6]}]}
    monkeypatch.setattr(adj,'load_ledger',lambda _: ledger)
    monkeypatch.setattr(adj,'active_freeze',lambda *_: None)
    with pytest.raises(ValueError, match='active frozen'): adj.append_attribution_for_existing(tmp_path/'l.json',10)
    with pytest.raises(ValueError, match='active frozen'): adj.append_marginal_utility_for_existing(tmp_path/'l.json',10)


@pytest.mark.parametrize('event_type,msg', [
    ('ATTRIBUTION','attribution cannot'),('MARGINAL_UTILITY','marginal utility cannot'),('INTERACTIONS','interactions cannot'),
    ('MULTI_CHALLENGERS','multi-challenger'),('META_GOVERNOR','meta-governor'),('RANK_SCORE_CALIBRATION','rank calibration')])
def test_adjudicate_rejects_derived_events_before_result(monkeypatch,tmp_path,event_type,msg):
    fr={'freeze_file':str(tmp_path/'f.json'),'freeze_sha256':'a'*64}
    ledger={'events':[{'event_type':event_type,'target_contest':10}]}
    monkeypatch.setattr(adj,'load_ledger',lambda _: ledger)
    monkeypatch.setattr(adj,'active_freeze',lambda *_: fr)
    with pytest.raises(ValueError, match=msg): adj.adjudicate(tmp_path/'r.xlsx',10,tmp_path/'l.json')


def test_adjudicate_non_object_freeze(monkeypatch,tmp_path):
    f=tmp_path/'f.json'; f.write_text('[]'); h=adj.sha256(f)
    fr={'freeze_file':str(f),'freeze_sha256':h}
    monkeypatch.setattr(adj,'load_ledger',lambda _: {'events':[]})
    monkeypatch.setattr(adj,'active_freeze',lambda *_: fr)
    with pytest.raises(ValueError, match='object'): adj.adjudicate(tmp_path/'r.xlsx',10,tmp_path/'l.json')


def test_final_entrypoint_and_short_hash_coverage(tmp_path, monkeypatch):
    assert prod._is_hex64('short') is False

    freeze = _pipeline_freeze(tmp_path)
    portfolio_out = tmp_path / 'portfolio_cli.json'
    monkeypatch.setattr(sys, 'argv', ['smart_portfolio_pipeline.py', '--freeze', str(freeze), '--out', str(portfolio_out)])
    runpy.run_path(str(Path(pp.__file__)), run_name='__main__')
    assert portfolio_out.is_file()

    audit = tmp_path / 'audit_cli.json'
    audit.write_text(json.dumps({
        'walk_forward': {'excess_hits': 1, 'diagnostic_z_vs_uniform': 3, 'total_hits': 2},
        'placebo': {'total_hits': 1},
        'monte_carlo_null': {'false_positive_rate_z_ge_2': 0.01},
    }), encoding='utf-8')
    data = tmp_path / 'data_cli.bin'; data.write_bytes(b'data')
    production_out = tmp_path / 'production_cli.json'
    monkeypatch.setattr(sys, 'argv', ['smart_v2_production.py', '--audit', str(audit), '--data', str(data), '--ledger', str(tmp_path/'missing_ledger.json'), '--out', str(production_out)])
    runpy.run_path(str(Path(prod.__file__)), run_name='__main__')
    assert production_out.is_file()


def test_append_interactions_missing_active_freeze_branch(monkeypatch, tmp_path):
    ledger = {'events': [{'event_type': 'ADJUDICATION', 'target_contest': 10, 'freeze_sha256': 'a', 'actual_numbers': [1,2,3,4,5,6]}]}
    monkeypatch.setattr(adj, 'load_ledger', lambda _: ledger)
    monkeypatch.setattr(adj, 'active_freeze', lambda *_: None)
    with pytest.raises(ValueError, match='active freeze'):
        adj.append_interactions_for_existing(tmp_path/'ledger.json', 10)
