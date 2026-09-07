from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import smart_independent_audit as ia
import smart_material_deficiency_registry as mdr


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dataset(n: int, seed: int = 1414) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for contest in range(1, n + 1):
        draw = np.sort(rng.choice(np.arange(1, 61), 6, replace=False))
        row = {'Concurso': contest, 'Data do Sorteio': pd.Timestamp('2025-01-01') + pd.Timedelta(days=contest)}
        row.update({f'Bola{i}': int(draw[i - 1]) for i in range(1, 7)})
        rows.append(row)
    return pd.DataFrame(rows)


def _coverage_binding(tmp_path: Path, source_name='unit.py') -> Path:
    source = tmp_path / source_name
    source.write_text('x = 1\n', encoding='utf-8')
    report = tmp_path / 'coverage.json'
    report.write_text(json.dumps({
        'meta': {'branch_coverage': True},
        'files': {
            source_name: {
                'summary': {
                    'covered_lines': 1, 'num_statements': 1, 'missing_lines': 0,
                    'covered_branches': 0, 'num_branches': 0, 'missing_branches': 0,
                }
            }
        }
    }), encoding='utf-8')
    binding = tmp_path / 'binding.json'
    binding.write_text(json.dumps({
        'schema': ia.COVERAGE_BINDING_SCHEMA,
        'source_file': source_name,
        'source_sha256': _sha(source),
        'coverage_report_file': report.name,
        'coverage_report_sha256': _sha(report),
        'coverage_file_key': source_name,
    }), encoding='utf-8')
    return binding


def _pair_fixture(tmp_path: Path, target: int = 11):
    registry_path = tmp_path / mdr.DEFAULT_PATH
    if not registry_path.exists():
        mdr.write_registry(registry_path, mdr.build_registry([]))
    pre = tmp_path / 'pre.xlsx'
    result = tmp_path / 'result.xlsx'
    _dataset(target - 1).to_excel(pre, index=False)
    full = _dataset(target)
    full.to_excel(result, index=False)
    actual = sorted(int(full.iloc[-1][f'Bola{i}']) for i in range(1, 7))
    champion = [actual[0]] + [n for n in range(1, 61) if n not in actual and n != actual[0]][:5]
    challenger = [actual[-1]] + [n for n in range(60, 0, -1) if n not in actual and n != actual[-1]][:5]
    state = tmp_path / 'state.json'
    state.write_text('{"state":1}', encoding='utf-8')
    freeze = tmp_path / 'freeze.json'
    frozen = {
        'schema': 'SMART_CHAMPION_CHALLENGER_FREEZE_2',
        'target_contest': target,
        'cutoff_contest': target - 1,
        'frozen_before_result': True,
        'causal_cutoff': True,
        'data_file': pre.name,
        'data_sha256': _sha(pre),
        'engine_sha256': 'a' * 64,
        'signal_state_file': state.name,
        'signal_state_sha256': _sha(state),
        'champion': {'top6': champion},
        'challenger': {'top6': challenger},
    }
    freeze.write_text(json.dumps(frozen), encoding='utf-8')
    fsha = _sha(freeze)
    ch = len(set(champion) & set(actual))
    hh = len(set(challenger) & set(actual))
    e_value = 1.0 * (1.0 + ia.E_BET_LAMBDA * ((hh - ch) / 6.0))
    fr = {
        'event_type': 'FREEZE', 'target_contest': target, 'cutoff_contest': target - 1,
        'created_utc': '2026-01-01T10:00:00+00:00', 'frozen_before_result': True, 'causal_cutoff': True,
        'freeze_file': freeze.name, 'freeze_sha256': fsha, 'data_sha256': _sha(pre),
        'champion_top6': champion, 'challenger_top6': challenger,
        'hashes': {'engine': 'a' * 64, 'state': _sha(state)},
    }
    ad = {
        'event_type': 'ADJUDICATION', 'target_contest': target, 'created_utc': '2026-01-01T11:00:00+00:00',
        'freeze_sha256': fsha, 'result_data_file': result.name, 'result_data_sha256': _sha(result),
        'actual_numbers': actual, 'champion_hits': ch, 'challenger_hits': hh,
        'difference_hits': hh - ch, 'e_value_after': e_value,
    }
    ledger = tmp_path / 'ledger.json'
    ledger.write_text(json.dumps({'schema': ia.LEDGER_SCHEMA, 'events': [fr, ad]}), encoding='utf-8')
    return ledger, pre, result, freeze, state, fr, ad, actual


def test_policy_snapshot_is_fail_closed_and_has_no_promotion_authority():
    p = ia.policy_snapshot()
    assert p['fail_closed'] is True
    assert p['promotion_authority'] is False
    assert p['deterministic_replay_required'] is True
    assert p['full_champion_comparison_required'] is True
    assert len(p['sha256']) == 64


def test_sha_helpers_and_top6_guards(tmp_path: Path):
    p = tmp_path / 'x'; p.write_bytes(b'abc')
    assert ia.sha256_file(p) == hashlib.sha256(b'abc').hexdigest()
    assert ia.sha256_json({'b': 2, 'a': 1}) == ia.sha256_json({'a': 1, 'b': 2})
    assert ia._is_hex64('a' * 64) and not ia._is_hex64('x' * 64) and not ia._is_hex64(1)
    assert ia._valid_top6([1, 2, 3, 4, 5, 6], 'x') == [1, 2, 3, 4, 5, 6]
    for bad in ([1, 2], [1, 2, 3, 4, 5, True], [1, 1, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5], [56, 57, 58, 59, 60, 61]):
        with pytest.raises(ValueError):
            ia._valid_top6(bad, 'x')


def test_json_and_time_guards(tmp_path: Path):
    bad = tmp_path / 'bad.json'; bad.write_text('[]', encoding='utf-8')
    with pytest.raises(ValueError): ia._load_json(bad)
    assert ia._event_time('2026-01-01T00:00:00Z') is not None
    assert ia._event_time('bad') is None and ia._event_time(None) is None
    assert ia._resolve(tmp_path, 'a') == tmp_path / 'a'
    assert ia._resolve(tmp_path, tmp_path / 'b') == tmp_path / 'b'


def test_coverage_binding_passes_and_detects_stale_or_incomplete_evidence(tmp_path: Path):
    binding = _coverage_binding(tmp_path)
    out = ia.audit_coverage_binding(tmp_path, binding)
    assert out['status'] == 'PASS' and out['covered_lines'] == out['statements'] == 1
    assert ia.audit_coverage_bindings(tmp_path, [binding])['count'] == 1
    with pytest.raises(ValueError): ia.audit_coverage_bindings(tmp_path, [])

    b = json.loads(binding.read_text())
    b['schema'] = 'BAD'; binding.write_text(json.dumps(b))
    with pytest.raises(ValueError): ia.audit_coverage_binding(tmp_path, binding)
    binding = _coverage_binding(tmp_path, 'unit2.py')
    (tmp_path / 'unit2.py').write_text('changed=1')
    with pytest.raises(ValueError): ia.audit_coverage_binding(tmp_path, binding)


def test_coverage_binding_rejects_report_tampering_and_missing_coverage(tmp_path: Path):
    binding = _coverage_binding(tmp_path)
    b = json.loads(binding.read_text())
    report = tmp_path / b['coverage_report_file']
    r = json.loads(report.read_text()); r['meta']['branch_coverage'] = False
    report.write_text(json.dumps(r)); b['coverage_report_sha256'] = _sha(report); binding.write_text(json.dumps(b))
    with pytest.raises(ValueError): ia.audit_coverage_binding(tmp_path, binding)

    binding = _coverage_binding(tmp_path, 'unit3.py'); b = json.loads(binding.read_text()); report = tmp_path / b['coverage_report_file']
    r = json.loads(report.read_text()); r['files'].pop('unit3.py'); report.write_text(json.dumps(r)); b['coverage_report_sha256'] = _sha(report); binding.write_text(json.dumps(b))
    with pytest.raises(ValueError): ia.audit_coverage_binding(tmp_path, binding)

    binding = _coverage_binding(tmp_path, 'unit4.py'); b = json.loads(binding.read_text()); report = tmp_path / b['coverage_report_file']
    r = json.loads(report.read_text()); s = r['files']['unit4.py']['summary']; s['missing_lines'] = 1; s['covered_lines'] = 0
    report.write_text(json.dumps(r)); b['coverage_report_sha256'] = _sha(report); binding.write_text(json.dumps(b))
    with pytest.raises(ValueError): ia.audit_coverage_binding(tmp_path, binding)

    binding = _coverage_binding(tmp_path, 'unit5.py'); b = json.loads(binding.read_text()); report = tmp_path / b['coverage_report_file']
    r = json.loads(report.read_text()); s = r['files']['unit5.py']['summary']; s['num_branches'] = 1; s['covered_branches'] = 0; s['missing_branches'] = 0
    report.write_text(json.dumps(r)); b['coverage_report_sha256'] = _sha(report); binding.write_text(json.dumps(b))
    with pytest.raises(ValueError): ia.audit_coverage_binding(tmp_path, binding)


def test_independent_ledger_audit_recomputes_hashes_hits_eprocess_and_comparison(tmp_path: Path):
    ledger, _, _, _, _, _, _, actual = _pair_fixture(tmp_path)
    out = ia.audit_prospective_ledger(tmp_path, ledger)
    assert out['status'] == 'PASS' and out['no_future_leakage'] is True
    assert out['pair_count'] == 1
    row = out['pairs'][0]
    assert row['actual_numbers'] == actual
    assert row['champion_hits'] == 1 and row['challenger_hits'] == 1
    assert out['full_champion_comparison']['advantage_hits'] == 0


def test_ledger_audit_supports_pre_result_supersede_chain(tmp_path: Path):
    ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path)
    old = copy.deepcopy(fr); old['freeze_sha256'] = 'b' * 64; old['freeze_file'] = 'old.json'
    sup = {'event_type': 'SUPERSEDE', 'target_contest': ad['target_contest'], 'old_freeze_sha256': 'b' * 64, 'new_freeze_sha256': fr['freeze_sha256']}
    obj = {'schema': ia.LEDGER_SCHEMA, 'events': [old, fr, sup, ad]}
    ledger.write_text(json.dumps(obj))
    assert ia.audit_prospective_ledger(tmp_path, ledger)['pair_count'] == 1


def test_ledger_audit_rejects_duplicate_or_invalid_event_relations(tmp_path: Path):
    ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path)
    cases = []
    cases.append({'schema': ia.LEDGER_SCHEMA, 'events': [fr, ad, copy.deepcopy(ad)]})
    bad = copy.deepcopy(ad); bad['freeze_sha256'] = 'c' * 64; cases.append({'schema': ia.LEDGER_SCHEMA, 'events': [fr, bad]})
    sup = {'event_type': 'SUPERSEDE', 'target_contest': ad['target_contest'], 'old_freeze_sha256': fr['freeze_sha256'], 'new_freeze_sha256': 'd' * 64}
    cases.append({'schema': ia.LEDGER_SCHEMA, 'events': [fr, sup, ad]})
    cases.append({'schema': ia.LEDGER_SCHEMA, 'events': [ad, fr]})
    badfr = copy.deepcopy(fr); badfr['target_contest'] += 1; cases.append({'schema': ia.LEDGER_SCHEMA, 'events': [badfr, ad]})
    badfr = copy.deepcopy(fr); badfr['causal_cutoff'] = False; cases.append({'schema': ia.LEDGER_SCHEMA, 'events': [badfr, ad]})
    late = copy.deepcopy(fr); late['freeze_sha256'] = 'e' * 64; late['freeze_file'] = 'late.json'; cases.append({'schema': ia.LEDGER_SCHEMA, 'events': [fr, ad, late]})
    badad = copy.deepcopy(ad); badad['created_utc'] = fr['created_utc']; cases.append({'schema': ia.LEDGER_SCHEMA, 'events': [fr, badad]})
    for obj in cases:
        ledger.write_text(json.dumps(obj))
        with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)


def test_ledger_audit_rejects_artifact_data_result_and_comparison_tampering(tmp_path: Path):
    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path)
    base = json.loads(ledger.read_text())

    freeze.write_text('{}')
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)
    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path)

    frozen = json.loads(freeze.read_text()); frozen['cutoff_contest'] = 9; freeze.write_text(json.dumps(frozen)); fr['freeze_sha256'] = _sha(freeze); ad['freeze_sha256'] = fr['freeze_sha256']; ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)

    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path)
    pre.write_bytes(b'tampered')
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)

    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path)
    result.write_bytes(b'tampered')
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)

    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path)
    ad['actual_numbers'] = [1,2,3,4,5,6]; ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)

    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path)
    ad['champion_hits'] += 1; ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)

    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path)
    ad['difference_hits'] = 3; ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)

    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path)
    ad['e_value_after'] = 99; ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)


def test_ledger_audit_rejects_component_and_state_hash_tampering(tmp_path: Path):
    ledger, pre, result, freeze, state, fr, ad, _ = _pair_fixture(tmp_path)
    fr['hashes']['engine'] = 'bad'; ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)

    ledger, pre, result, freeze, state, fr, ad, _ = _pair_fixture(tmp_path)
    frozen = json.loads(freeze.read_text()); frozen['engine_sha256'] = 'b' * 64; freeze.write_text(json.dumps(frozen)); fr['freeze_sha256'] = _sha(freeze); ad['freeze_sha256'] = fr['freeze_sha256']; ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)

    ledger, pre, result, freeze, state, fr, ad, _ = _pair_fixture(tmp_path)
    state.write_text('changed')
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)


def test_ledger_audit_rejects_invalid_schema_no_pairs_and_future_leakage(tmp_path: Path):
    ledger = tmp_path/'ledger.json'; ledger.write_text(json.dumps({'schema':'BAD','events':[]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)

    ledger, pre, result, freeze, state, fr, ad, _ = _pair_fixture(tmp_path)
    df = pd.read_excel(pre); future = pd.read_excel(result).iloc[-1:]; pd.concat([df, future], ignore_index=True).to_excel(pre, index=False)
    frozen = json.loads(freeze.read_text()); frozen['data_sha256'] = _sha(pre); freeze.write_text(json.dumps(frozen)); fr['data_sha256'] = _sha(pre); fr['freeze_sha256'] = _sha(freeze); ad['freeze_sha256'] = fr['freeze_sha256']; ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)


def test_deterministic_replay_passes_on_same_causal_input(tmp_path: Path):
    data = tmp_path / 'replay.xlsx'; _dataset(35, 99).to_excel(data, index=False)
    out = ia.audit_deterministic_replay(tmp_path, data, 36, start=20)
    assert out['status'] == 'PASS' and out['deterministic'] is True
    assert out['cutoff_contest'] == 35 and len(out['champion_top6']) == len(out['challenger_top6']) == 6


def test_deterministic_replay_rejects_missing_or_wrong_cutoff(tmp_path: Path):
    with pytest.raises(ValueError): ia.audit_deterministic_replay(tmp_path, tmp_path/'missing.xlsx', 10, start=2)
    data = tmp_path/'replay.xlsx'; _dataset(12).to_excel(data,index=False)
    with pytest.raises(ValueError): ia.audit_deterministic_replay(tmp_path, data, 20, start=5)


def test_run_independent_audit_combines_all_required_evidence(tmp_path: Path):
    binding = _coverage_binding(tmp_path)
    ledger, pre, _, _, _, _, _, _ = _pair_fixture(tmp_path, target=36)
    # Pair fixture builds a 35-contest causal prefix, so the same prefix is valid for deterministic replay.
    report = ia.run_independent_audit(tmp_path, ledger, [binding], pre, 36, start=20)
    assert report['status'] == 'PASS'
    assert all(report['checks'].values())
    assert report['promotion_authority'] is False
    assert report['prospective_ledger']['full_champion_comparison']['adjudicated_contests'] == 1
    assert len(report['sha256']) == 64



def test_p14_remaining_coverage_binding_guards(tmp_path: Path):
    binding = _coverage_binding(tmp_path, 'missing_source.py')
    (tmp_path/'missing_source.py').unlink()
    with pytest.raises(ValueError): ia.audit_coverage_binding(tmp_path, binding)

    binding = _coverage_binding(tmp_path, 'report_tamper.py')
    b=json.loads(binding.read_text()); report=tmp_path/b['coverage_report_file']
    report.write_text(report.read_text()+' ')
    with pytest.raises(ValueError): ia.audit_coverage_binding(tmp_path, binding)

    binding = _coverage_binding(tmp_path, 'line_incomplete.py')
    b=json.loads(binding.read_text()); report=tmp_path/b['coverage_report_file']; r=json.loads(report.read_text())
    sm=r['files']['line_incomplete.py']['summary']; sm['covered_lines']=0; sm['num_statements']=1; sm['missing_lines']=0; sm['missing_branches']=0
    report.write_text(json.dumps(r)); b['coverage_report_sha256']=_sha(report); binding.write_text(json.dumps(b))
    with pytest.raises(ValueError): ia.audit_coverage_binding(tmp_path, binding)


def test_p14_contest_number_guards():
    with pytest.raises(ValueError): ia._contest_numbers(pd.DataFrame([{'x':1}]), 1)
    row={'Concurso':1}; row.update({f'Bola{i}':i for i in range(1,7)})
    with pytest.raises(ValueError): ia._contest_numbers(pd.DataFrame([row,row]), 1)


def test_p14_ledger_event_hash_and_supersede_guards(tmp_path: Path):
    ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path)
    dup=copy.deepcopy(fr)
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,dup,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)

    ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path)
    badsup={'event_type':'SUPERSEDE','target_contest':ad['target_contest'],'old_freeze_sha256':'bad','new_freeze_sha256':fr['freeze_sha256']}
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,badsup,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path, ledger)


def _rewrite_frozen_case(tmp_path: Path, mutate):
    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path)
    frozen=json.loads(freeze.read_text())
    mutate(frozen, fr, ad, pre, result, state, actual)
    freeze.write_text(json.dumps(frozen),encoding='utf-8')
    fr['freeze_sha256']=_sha(freeze); ad['freeze_sha256']=fr['freeze_sha256']
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}),encoding='utf-8')
    return ledger


def test_p14_frozen_artifact_semantic_guards(tmp_path: Path):
    ledger=_rewrite_frozen_case(tmp_path, lambda f,fr,ad,pre,result,state,actual: f.__setitem__('target_contest',999))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path,ledger)

    def flags(f,*_): f['causal_cutoff']=False
    ledger=_rewrite_frozen_case(tmp_path,flags)
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path,ledger)

    def data_disagree(f,fr,*_): f['data_sha256']='c'*64
    ledger=_rewrite_frozen_case(tmp_path,data_disagree)
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path,ledger)

    def champ(f,*_): f['champion']['top6']=[7,8,9,10,11,12]
    ledger=_rewrite_frozen_case(tmp_path,champ)
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path,ledger)

    def chall(f,*_): f['challenger']['top6']=[13,14,15,16,17,18]
    ledger=_rewrite_frozen_case(tmp_path,chall)
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path,ledger)

    ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path)
    fr['hashes']={}; ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError): ia.audit_prospective_ledger(tmp_path,ledger)


def test_p14_leakage_and_cutoff_classification_guards(tmp_path: Path):
    ledger, pre, result, freeze, state, fr, ad, _ = _pair_fixture(tmp_path)
    future=pd.read_excel(result).iloc[-1:]
    df=pd.read_excel(pre); pd.concat([df,future],ignore_index=True).to_excel(pre,index=False)
    frozen=json.loads(freeze.read_text()); frozen['data_sha256']=_sha(pre); freeze.write_text(json.dumps(frozen))
    fr['data_sha256']=_sha(pre); fr['freeze_sha256']=_sha(freeze); ad['freeze_sha256']=fr['freeze_sha256']
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError, match='future result leaked'): ia.audit_prospective_ledger(tmp_path,ledger)

    ledger, pre, result, freeze, state, fr, ad, _ = _pair_fixture(tmp_path)
    df=pd.read_excel(pre).iloc[:-1].copy(); df.to_excel(pre,index=False)
    frozen=json.loads(freeze.read_text()); frozen['data_sha256']=_sha(pre); freeze.write_text(json.dumps(frozen))
    fr['data_sha256']=_sha(pre); fr['freeze_sha256']=_sha(freeze); ad['freeze_sha256']=fr['freeze_sha256']
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}))
    with pytest.raises(ValueError, match='does not end'): ia.audit_prospective_ledger(tmp_path,ledger)


def test_p14_ledger_ignores_unrelated_events_but_scans_post_adjudication_events(tmp_path: Path):
    ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path)
    other={'event_type':'TELEMETRY','target_contest':9999}
    derived={'event_type':'ATTRIBUTION','target_contest':ad['target_contest']}
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[other,fr,ad,derived]}))
    assert ia.audit_prospective_ledger(tmp_path,ledger)['status']=='PASS'


def test_p14_replay_detects_champion_nondeterminism(monkeypatch, tmp_path: Path):
    data=tmp_path/'d.xlsx'; _dataset(12).to_excel(data,index=False)
    calls={'n':0}
    def fake(draws,start):
        calls['n']+=1
        return {'top6':[1,2,3,4,5,6], 'nonce':calls['n']}
    monkeypatch.setattr(ia.champion_engine,'current_policy',fake)
    with pytest.raises(ValueError, match='Champion replay'): ia.audit_deterministic_replay(tmp_path,data,13,start=5)


def test_p14_replay_detects_challenger_nondeterminism_and_bad_cutoff(monkeypatch, tmp_path: Path):
    data=tmp_path/'d.xlsx'; _dataset(12).to_excel(data,index=False)
    class Pred:
        def __init__(self, nonce=0, cutoff=12):
            self.nonce=nonce; self.cutoff_contest=cutoff; self.target_contest=13; self.top6=[1,2,3,4,5,6]
        def as_dict(self): return {'generated_utc':'x','nonce':self.nonce,'top6':self.top6}
    class AgentND:
        calls=0
        def __init__(self,start): pass
        def predict_next(self,*args,**kwargs):
            type(self).calls+=1; return Pred(type(self).calls), {'rows':[]}
    monkeypatch.setattr(ia,'SmartSignalAgent',AgentND)
    with pytest.raises(ValueError, match='Challenger replay'): ia.audit_deterministic_replay(tmp_path,data,13,start=5)

    class AgentBad:
        def __init__(self,start): pass
        def predict_next(self,*args,**kwargs): return Pred(0,cutoff=11), {'rows':[]}
    monkeypatch.setattr(ia,'SmartSignalAgent',AgentBad)
    with pytest.raises(ValueError, match='causal target/cutoff'): ia.audit_deterministic_replay(tmp_path,data,13,start=5)



def test_p14_future_freeze_hashes_and_snapshots_independent_audit(tmp_path: Path):
    import smart_champion_challenger as cc
    data=tmp_path/'pre.xlsx'; _dataset(35,seed=1415).to_excel(data,index=False)
    out=tmp_path/'freeze.json'; ledger=tmp_path/'ledger.json'; state=tmp_path/'state.json'
    cwd=Path.cwd()
    try:
        # Component hashes are resolved from the canonical project working directory.
        result=cc.freeze_champion_challenger(data,36,out,ledger,state,start=20, enforce_temporal_guard=False)
    finally:
        assert Path.cwd()==cwd
    assert result['status']=='FROZEN'
    frozen=json.loads(out.read_text()); L=json.loads(ledger.read_text()); ev=L['events'][0]
    assert frozen['independent_audit_sha256']==ia.sha256_file(Path('smart_independent_audit.py'))
    assert frozen['independent_audit_policy']['schema']=='SMART_INDEPENDENT_AUDIT_POLICY_1'
    assert frozen['independent_audit_policy']['promotion_authority'] is False
    assert ev['hashes']['independent_audit']==frozen['independent_audit_sha256']
    assert ev['snapshot']['independent_audit_policy']==frozen['independent_audit_policy']



def _legacy_3051_fixture(base: Path):
    base.mkdir(parents=True, exist_ok=True)
    pre=base/'pre3050.xlsx'; result=base/'result3051.xlsx'; state=base/'state.json'; freeze=base/'freeze.json'; ledger=base/'ledger.json'
    cols=['Concurso','Data do Sorteio']+[f'Bola{i}' for i in range(1,7)]+['Observacao']
    pre_df=pd.DataFrame([{
        'Concurso':3050,'Data do Sorteio':pd.Timestamp('2026-08-27'),
        'Bola1':11,'Bola2':14,'Bola3':30,'Bola4':38,'Bola5':49,'Bola6':55,'Observacao':None,
    }],columns=cols)
    target_row={
        'Concurso':3051,'Data do Sorteio':pd.Timestamp('2026-08-30'),
        'Bola1':11,'Bola2':15,'Bola3':20,'Bola4':21,'Bola5':38,'Bola6':48,'Observacao':None,
    }
    result_df=pd.concat([pre_df,pd.DataFrame([target_row],columns=cols)],ignore_index=True)
    pre_df.to_excel(pre,index=False); result_df.to_excel(result,index=False)
    state.write_text('{"state":3050}',encoding='utf-8')
    champion=[11,27,10,30,53,46]; challenger=[11,27,10,30,53,43]
    frozen={
        'schema':'SMART_CHAMPION_CHALLENGER_FREEZE_2','target_contest':3051,'cutoff_contest':3050,
        'frozen_before_result':True,'causal_cutoff':True,'data_file':pre.name,'data_sha256':_sha(pre),
        'engine_sha256':'a'*64,'signal_state_file':state.name,'signal_state_sha256':_sha(state),
        'champion':{'top6':champion},'challenger':{'top6':challenger},
    }
    freeze.write_text(json.dumps(frozen),encoding='utf-8'); fsha=_sha(freeze)
    actual=[11,15,20,21,38,48]; ch=len(set(champion)&set(actual)); hh=len(set(challenger)&set(actual))
    original='8'*64
    fr={
        'event_type':'FREEZE','target_contest':3051,'cutoff_contest':3050,'created_utc':'2026-08-30T16:00:00+00:00',
        'frozen_before_result':True,'causal_cutoff':True,'freeze_file':freeze.name,'freeze_sha256':fsha,'data_sha256':_sha(pre),
        'champion_top6':champion,'challenger_top6':challenger,'hashes':{'engine':'a'*64,'state':_sha(state)},
    }
    ad={
        'event_type':'ADJUDICATION','target_contest':3051,'created_utc':'2026-08-30T16:30:00+00:00','freeze_sha256':fsha,
        'result_data_file':result.name,'result_data_sha256':original,'actual_numbers':actual,
        'champion_hits':ch,'challenger_hits':hh,'difference_hits':hh-ch,
        'e_value_after':1.0*(1.0+ia.E_BET_LAMBDA*((hh-ch)/6.0)),
    }
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}),encoding='utf-8')
    proof={
        'schema':ia.LEGACY_CONTINUITY_SCHEMA,'target_contest':3051,
        'original_adjudicated_result_sha256':original,'current_result_sha256':_sha(result),
        'frozen_prefix_sha256':_sha(pre),'prefix_semantic_sha256':ia.semantic_dataframe_sha256(pre_df),
        'current_semantic_sha256':ia.semantic_dataframe_sha256(result_df),'target_numbers':actual,
    }
    pp=base/'SMART_P14_LEGACY_RESULT_CONTINUITY_3051.json'; pp.write_text(json.dumps(proof),encoding='utf-8')
    return ledger,pre,result,freeze,state,fr,ad,proof,pp


def test_p14_legacy_3051_continuity_accepts_only_full_semantic_equivalence(tmp_path: Path):
    ledger,pre,result,freeze,state,fr,ad,proof,pp=_legacy_3051_fixture(tmp_path)
    out=ia.audit_prospective_ledger(tmp_path,ledger)
    assert out['status']=='PASS' and out['legacy_result_continuity_used'] is True
    row=out['pairs'][0]
    assert row['result_binary_hash_exact'] is False
    assert row['result_data_hash_verified'] is False
    assert row['legacy_result_continuity']['exact_prefix_semantic_equal'] is True
    assert row['legacy_result_continuity']['target_numbers']==[11,15,20,21,38,48]
    assert ia.policy_snapshot()['legacy_result_continuity_target']==3051


def test_p14_legacy_continuity_is_forbidden_outside_3051(tmp_path: Path):
    ledger,pre,result,freeze,state,fr,ad,proof,pp=_legacy_3051_fixture(tmp_path)
    frozen=json.loads(freeze.read_text())
    with pytest.raises(ValueError,match='only for contest 3051'):
        ia.audit_legacy_result_continuity(tmp_path,3050,ad,frozen,pre,result)


def _legacy_direct(base: Path):
    ledger,pre,result,freeze,state,fr,ad,proof,pp=_legacy_3051_fixture(base)
    return pre,result,json.loads(freeze.read_text()),ad,proof,pp


def test_p14_legacy_proof_metadata_guards(tmp_path: Path):
    cases=[
        ('schema',lambda p: p.__setitem__('schema','BAD'),'invalid legacy continuity proof'),
        ('original',lambda p: p.__setitem__('original_adjudicated_result_sha256','0'*64),'original adjudicated hash mismatch'),
        ('current',lambda p: p.__setitem__('current_result_sha256','0'*64),'current result hash mismatch'),
        ('prefix',lambda p: p.__setitem__('frozen_prefix_sha256','0'*64),'frozen prefix hash mismatch'),
        ('semantic',lambda p: p.__setitem__('prefix_semantic_sha256','0'*64),'proof semantic prefix hash mismatch'),
        ('targetnums',lambda p: p.__setitem__('target_numbers',[1,2,3,4,5,6]),'target result does not match'),
        ('currentsemantic',lambda p: p.__setitem__('current_semantic_sha256','0'*64),'current semantic hash mismatch'),
    ]
    for name,mut,msg in cases:
        base=tmp_path/name; pre,result,frozen,ad,proof,pp=_legacy_direct(base)
        mut(proof); pp.write_text(json.dumps(proof),encoding='utf-8')
        with pytest.raises(ValueError,match=msg):
            ia.audit_legacy_result_continuity(base,3051,ad,frozen,pre,result)


def test_p14_legacy_file_structure_and_semantic_guards(tmp_path: Path):
    # columns mismatch
    base=tmp_path/'columns'; pre,result,frozen,ad,proof,pp=_legacy_direct(base)
    df=pd.read_excel(result); df['Extra']=1; df.to_excel(result,index=False); proof['current_result_sha256']=_sha(result); pp.write_text(json.dumps(proof))
    with pytest.raises(ValueError,match='columns differ'): ia.audit_legacy_result_continuity(base,3051,ad,frozen,pre,result)
    # row count mismatch
    base=tmp_path/'rows'; pre,result,frozen,ad,proof,pp=_legacy_direct(base)
    df=pd.read_excel(result); pd.concat([df,df.iloc[-1:]],ignore_index=True).to_excel(result,index=False); proof['current_result_sha256']=_sha(result); pp.write_text(json.dumps(proof))
    with pytest.raises(ValueError,match='prefix plus one contest'): ia.audit_legacy_result_continuity(base,3051,ad,frozen,pre,result)
    # semantic prefix mismatch
    base=tmp_path/'prefixsem'; pre,result,frozen,ad,proof,pp=_legacy_direct(base)
    df=pd.read_excel(result); df.loc[0,'Bola1']=12; df.to_excel(result,index=False); proof['current_result_sha256']=_sha(result); pp.write_text(json.dumps(proof))
    with pytest.raises(ValueError,match='prefix differs semantically'): ia.audit_legacy_result_continuity(base,3051,ad,frozen,pre,result)
    # wrong final contest
    base=tmp_path/'final'; pre,result,frozen,ad,proof,pp=_legacy_direct(base)
    df=pd.read_excel(result); df.loc[len(df)-1,'Concurso']=3052; df.to_excel(result,index=False); proof['current_result_sha256']=_sha(result); pp.write_text(json.dumps(proof))
    with pytest.raises(ValueError,match='beyond target or wrong final contest'): ia.audit_legacy_result_continuity(base,3051,ad,frozen,pre,result)


def test_p14_legacy_frozen_hash_guard_and_exact_binary_path(tmp_path: Path):
    base=tmp_path/'fh'; pre,result,frozen,ad,proof,pp=_legacy_direct(base)
    frozen['data_sha256']='0'*64
    with pytest.raises(ValueError,match='frozen prefix hash mismatch'):
        ia.audit_legacy_result_continuity(base,3051,ad,frozen,pre,result)
    # Ordinary exact-binary audit remains on the strict path and does not use legacy continuity.
    strict=tmp_path/'strict'; strict.mkdir()
    ledger,*_= _pair_fixture(strict)
    out=ia.audit_prospective_ledger(strict,ledger)
    assert out['legacy_result_continuity_used'] is False
    assert out['pairs'][0]['result_binary_hash_exact'] is True
    assert out['pairs'][0]['result_data_hash_verified'] is True


def test_p14_missing_result_file_fails_closed(tmp_path: Path):
    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path)
    result.unlink()
    with pytest.raises(ValueError, match='result data missing'):
        ia.audit_prospective_ledger(tmp_path, ledger)



def test_p14_independence_source_mismatch_and_forbidden_import(monkeypatch, tmp_path: Path):
    project = tmp_path / 'smart_independent_audit.py'
    project.write_text('x=1\n', encoding='utf-8')
    with pytest.raises(ValueError, match='project/runtime source mismatch'):
        ia.audit_independence(tmp_path)
    project.write_text('import smart_promotion_gate\n', encoding='utf-8')
    monkeypatch.setattr(ia, '__file__', str(project))
    with pytest.raises(ValueError, match='forbidden upward dependency'):
        ia.audit_independence(tmp_path)


def test_p14_promotion_lineage_fingerprint_all_guards():
    assert ia._promotion_lineage_fingerprint_independent({}) is None
    bad={'promotion_lineage':{'schema':ia.PROMOTION_LINEAGE_SCHEMA,'sha256':'bad'}}
    assert ia._promotion_lineage_fingerprint_independent(bad) is None
    component_hashes={k:'a'*64 for k in ia.PROMOTION_LINEAGE_COMPONENTS}
    lin={'schema':ia.PROMOTION_LINEAGE_SCHEMA,'component_hashes':component_hashes}
    lin['sha256']=ia.sha256_json(lin)
    assert ia._promotion_lineage_fingerprint_independent({'promotion_lineage':lin}) is None
    fr={'promotion_lineage':lin,'hashes':dict(component_hashes)}
    assert ia._promotion_lineage_fingerprint_independent(fr)==lin['sha256']
    tampered=json.loads(json.dumps(fr)); tampered['promotion_lineage']['sha256']='b'*64
    assert ia._promotion_lineage_fingerprint_independent(tampered) is None
    badcomp=json.loads(json.dumps(fr)); badcomp['hashes'][ia.PROMOTION_LINEAGE_COMPONENTS[0]]='bad'
    assert ia._promotion_lineage_fingerprint_independent(badcomp) is None
    mismatch=json.loads(json.dumps(fr)); mismatch['promotion_lineage']['component_hashes'][ia.PROMOTION_LINEAGE_COMPONENTS[0]]='c'*64
    canon=dict(mismatch['promotion_lineage']); canon.pop('sha256',None); mismatch['promotion_lineage']['sha256']=ia.sha256_json(canon)
    assert ia._promotion_lineage_fingerprint_independent(mismatch) is None


def test_p14_independent_supersede_remaining_guards():
    a,b,c='a'*64,'b'*64,'c'*64
    with pytest.raises(ValueError, match='before prior supersede'):
        ia._audit_supersede_chains([
            {'event_type':'FREEZE','target_contest':1,'freeze_sha256':a},
            {'event_type':'FREEZE','target_contest':1,'freeze_sha256':b},
            {'event_type':'FREEZE','target_contest':1,'freeze_sha256':c},
        ])
    with pytest.raises(ValueError, match='replace exactly'):
        ia._audit_supersede_chains([
            {'event_type':'FREEZE','target_contest':1,'freeze_sha256':a},
            {'event_type':'FREEZE','target_contest':1,'freeze_sha256':b},
            {'event_type':'SUPERSEDE','target_contest':1,'old_freeze_sha256':c,'new_freeze_sha256':b},
        ])


def test_p14_prospective_ledger_remaining_structural_guards(monkeypatch, tmp_path: Path):
    (tmp_path/'dup').mkdir(); ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path/'dup')
    dup=dict(fr)
    (tmp_path/'dup'/'ledger.json').write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,dup,ad]}),encoding='utf-8')
    with pytest.raises(ValueError, match='duplicate freeze hash'):
        ia.audit_prospective_ledger(tmp_path/'dup', tmp_path/'dup'/'ledger.json')

    (tmp_path/'sup').mkdir(); ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path/'sup')
    bad={'event_type':'SUPERSEDE','target_contest':ad['target_contest'],'old_freeze_sha256':'bad','new_freeze_sha256':'b'*64}
    (tmp_path/'sup'/'ledger.json').write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,bad,ad]}),encoding='utf-8')
    with pytest.raises(ValueError, match='invalid supersede hash linkage'):
        ia.audit_prospective_ledger(tmp_path/'sup', tmp_path/'sup'/'ledger.json')

    # Reach defense-in-depth guards after independently-active resolution by fixing resolver output.
    (tmp_path/'unknown').mkdir(); ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path/'unknown')
    unknown=dict(ad); unknown['freeze_sha256']='d'*64
    (tmp_path/'unknown'/'ledger.json').write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,unknown]}),encoding='utf-8')
    monkeypatch.setattr(ia,'_audit_supersede_chains',lambda events:{int(unknown['target_contest']):unknown['freeze_sha256']})
    with pytest.raises(ValueError, match='unknown freeze'):
        ia.audit_prospective_ledger(tmp_path/'unknown', tmp_path/'unknown'/'ledger.json')

    (tmp_path/'post').mkdir(); ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path/'post')
    post=dict(fr); post['freeze_sha256']='e'*64
    events=[fr,ad,post]
    (tmp_path/'post'/'ledger.json').write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':events}),encoding='utf-8')
    monkeypatch.setattr(ia,'_audit_supersede_chains',lambda events:{int(ad['target_contest']):fr['freeze_sha256']})
    with pytest.raises(ValueError, match='after adjudication'):
        ia.audit_prospective_ledger(tmp_path/'post', tmp_path/'post'/'ledger.json')


def test_p14_promotion_lineage_comparison_branch(tmp_path: Path):
    ledger, _, _, _, _, fr, ad, _ = _pair_fixture(tmp_path)
    comps={k:'a'*64 for k in ia.PROMOTION_LINEAGE_COMPONENTS}
    lineage={'schema':ia.PROMOTION_LINEAGE_SCHEMA,'component_hashes':comps}
    lineage['sha256']=ia.sha256_json(lineage)
    fr['hashes'].update(comps); fr['promotion_lineage']=lineage
    ledger.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}),encoding='utf-8')
    out=ia.audit_prospective_ledger(tmp_path,ledger)
    pc=out['promotion_lineage_comparison']
    assert pc['candidate_fingerprint']==lineage['sha256']
    assert pc['adjudicated_contests']==1
    assert pc['lineage_pairs_recomputed'] is True



def test_p14_secondary_scan_guards_with_resolver_isolated(monkeypatch, tmp_path: Path):
    # Duplicate freeze guard in the second independent scan.
    d=tmp_path/'dup2'; d.mkdir(); ledger,_,_,_,_,fr,ad,_=_pair_fixture(d)
    events=[fr,dict(fr),ad]
    (d/'ledger.json').write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':events}),encoding='utf-8')
    monkeypatch.setattr(ia,'_audit_supersede_chains',lambda ev:{int(ad['target_contest']):fr['freeze_sha256']})
    with pytest.raises(ValueError,match='invalid or duplicate freeze hash'):
        ia.audit_prospective_ledger(d,d/'ledger.json')

    # Invalid supersede hash guard in the second scan.
    d=tmp_path/'sup2'; d.mkdir(); ledger,_,_,_,_,fr,ad,_=_pair_fixture(d)
    bad={'event_type':'SUPERSEDE','target_contest':ad['target_contest'],'old_freeze_sha256':'bad','new_freeze_sha256':'b'*64}
    (d/'ledger.json').write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,bad,ad]}),encoding='utf-8')
    monkeypatch.setattr(ia,'_audit_supersede_chains',lambda ev:{int(ad['target_contest']):fr['freeze_sha256']})
    with pytest.raises(ValueError,match='invalid supersede hashes'):
        ia.audit_prospective_ledger(d,d/'ledger.json')

    # Superseded adjudication guard after active resolver is intentionally isolated.
    d=tmp_path/'oldsup'; d.mkdir(); ledger,_,_,_,_,fr,ad,_=_pair_fixture(d)
    new=dict(fr); new['freeze_sha256']='c'*64
    sup={'event_type':'SUPERSEDE','target_contest':ad['target_contest'],'old_freeze_sha256':fr['freeze_sha256'],'new_freeze_sha256':new['freeze_sha256']}
    (d/'ledger.json').write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,new,sup,ad]}),encoding='utf-8')
    monkeypatch.setattr(ia,'_audit_supersede_chains',lambda ev:{int(ad['target_contest']):fr['freeze_sha256']})
    with pytest.raises(ValueError,match='superseded freeze'):
        ia.audit_prospective_ledger(d,d/'ledger.json')

    # Freeze/adjudication target mismatch guard after active resolver is isolated.
    d=tmp_path/'targetmm'; d.mkdir(); ledger,_,_,_,_,fr,ad,_=_pair_fixture(d)
    fr['target_contest']=999
    (d/'ledger.json').write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':[fr,ad]}),encoding='utf-8')
    monkeypatch.setattr(ia,'_audit_supersede_chains',lambda ev:{int(ad['target_contest']):fr['freeze_sha256']})
    with pytest.raises(ValueError,match='target mismatch'):
        ia.audit_prospective_ledger(d,d/'ledger.json')


def test_p14_lineage_discards_prior_version(monkeypatch, tmp_path: Path):
    # Build two complete causal pairs in distinct folders, then expose them through
    # a resolver patched only for file paths; this exercises lineage-version cutoff.
    rows=[]
    events=[]
    for target,tag in ((11,'a'),(12,'b')):
        d=tmp_path/f'p{target}'; d.mkdir()
        ledger,pre,result,freeze,state,fr,ad,_=_pair_fixture(d,target=target)
        comps={k:tag*64 for k in ia.PROMOTION_LINEAGE_COMPONENTS}
        lin={'schema':ia.PROMOTION_LINEAGE_SCHEMA,'component_hashes':comps}
        lin['sha256']=ia.sha256_json(lin)
        fr['hashes'].update(comps); fr['promotion_lineage']=lin
        # Preserve absolute paths so the combined ledger can validate both pairs.
        fr['freeze_file']=str(freeze.resolve())
        ad['result_data_file']=str(result.resolve())
        frozen=json.loads(freeze.read_text(encoding='utf-8'))
        frozen['data_file']=str(pre.resolve()); frozen['signal_state_file']=str(state.resolve())
        for component,value in comps.items(): frozen[ia._freeze_hash_field(component)]=value
        freeze.write_text(json.dumps(frozen),encoding='utf-8')
        fr['freeze_sha256']=ia.sha256_file(freeze); ad['freeze_sha256']=fr['freeze_sha256']
        events.extend([fr,ad])
    combined=tmp_path/'combined.json'
    combined.write_text(json.dumps({'schema':ia.LEDGER_SCHEMA,'events':events}),encoding='utf-8')
    out=ia.audit_prospective_ledger(tmp_path,combined)
    pc=out['promotion_lineage_comparison']
    assert pc['adjudicated_contests']==1
    assert pc['discarded_prior_version_pairs']==1


def test_state_evidence_archive_and_legacy_contracts(tmp_path, monkeypatch):
    state = tmp_path / 'state.json'
    state.write_text('{"state": 7}', encoding='utf-8')
    sha = _sha(state)
    fr = {'freeze_file': str(tmp_path / 'freeze.json'), 'state_archive_sha256': sha}
    frozen = {
        'signal_state_file': state.name,
        'signal_state_sha256': sha,
        'signal_state_archive_file': state.name,
        'signal_state_archive_sha256': sha,
    }
    out = ia.audit_frozen_state_evidence(tmp_path, 4000, fr, frozen, sha)
    assert out['mode'] == 'IMMUTABLE_HASH_ARCHIVE'

    bad = dict(frozen); bad['signal_state_archive_sha256'] = None
    with pytest.raises(ValueError, match='metadata invalid'):
        ia.audit_frozen_state_evidence(tmp_path, 4000, fr, bad, sha)
    bad = dict(frozen); bad['signal_state_archive_file'] = 'missing.json'
    with pytest.raises(ValueError, match='archive hash mismatch'):
        ia.audit_frozen_state_evidence(tmp_path, 4000, fr, bad, sha)
    bad_fr = dict(fr); bad_fr['state_archive_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='ledger state archive hash mismatch'):
        ia.audit_frozen_state_evidence(tmp_path, 4000, bad_fr, frozen, sha)

    live_frozen = {'signal_state_file': state.name, 'signal_state_sha256': sha}
    live = ia.audit_frozen_state_evidence(tmp_path, 4000, {}, live_frozen, sha)
    assert live['mode'] == 'LEGACY_LIVE_FILE_EXACT_HASH'
    state.write_text('changed', encoding='utf-8')
    monkeypatch.setattr(ia, 'audit_legacy_state_continuity', lambda *a, **k: {'status':'PASS','mode':'FALLBACK'})
    assert ia.audit_frozen_state_evidence(tmp_path, 4000, {}, live_frozen, sha)['mode'] == 'FALLBACK'


def test_legacy_state_continuity_3051_all_guards(tmp_path, monkeypatch):
    monkeypatch.setattr(ia, 'LEGACY_MUTABLE_STATE_EVIDENCE', {3051:'proof.json'})
    fr = {'freeze_sha256': 'a' * 64}
    frozen = {'data_sha256': 'd' * 64}
    state_sha = 'b' * 64
    with pytest.raises(ValueError, match='evidence missing'):
        ia.audit_legacy_state_continuity(tmp_path, 3051, fr, frozen, state_sha)

    proof = tmp_path / 'proof.json'
    def write(obj): proof.write_text(json.dumps(obj), encoding='utf-8')
    base = {
        'schema':'SMART_SIGNAL_INTEGRATION_FINAL_PROOF_1', 'status':'MISSION_PROVEN',
        'active_freeze': {'sha256': fr['freeze_sha256'], 'event': {'freeze_sha256':fr['freeze_sha256'], 'hashes':{'state':state_sha}}},
        'artifact_hashes': {'freeze':fr['freeze_sha256'], 'state':state_sha},
    }
    x = copy.deepcopy(base); x['status']='FAIL'; write(x)
    with pytest.raises(ValueError, match='proof invalid'):
        ia.audit_legacy_state_continuity(tmp_path,3051,fr,frozen,state_sha)
    x = copy.deepcopy(base); x['active_freeze']=None; write(x)
    with pytest.raises(ValueError, match='proof incomplete'):
        ia.audit_legacy_state_continuity(tmp_path,3051,fr,frozen,state_sha)
    x = copy.deepcopy(base); x['active_freeze']['sha256']='c'*64; write(x)
    with pytest.raises(ValueError, match='freeze mismatch'):
        ia.audit_legacy_state_continuity(tmp_path,3051,fr,frozen,state_sha)
    x = copy.deepcopy(base); x['artifact_hashes']['state']='c'*64; write(x)
    with pytest.raises(ValueError, match='hash mismatch'):
        ia.audit_legacy_state_continuity(tmp_path,3051,fr,frozen,state_sha)
    write(base)
    good = ia.audit_legacy_state_continuity(tmp_path,3051,fr,frozen,state_sha)
    assert good['mode']=='LEGACY_HASH_BOUND_CONTINUITY' and good['mutable_state_path_not_trusted'] is True


def test_legacy_state_continuity_3052_and_unsupported_guards(tmp_path, monkeypatch):
    fr = {'freeze_sha256':'a'*64}; frozen={'data_sha256':'d'*64}; state_sha='b'*64
    monkeypatch.setattr(ia, 'LEGACY_MUTABLE_STATE_EVIDENCE', {3052:'app.json'})
    app = tmp_path/'app.json'
    base = {'schema':'SMART_3052_TRAINED_APPLICATION_1','contest':3052,'causal':True,'result_used':False,
            'active_freeze_sha256':fr['freeze_sha256'],'signal_state_sha256':state_sha,'data_sha256':frozen['data_sha256']}
    def write(obj): app.write_text(json.dumps(obj),encoding='utf-8')
    x=dict(base); x['contest']=1; write(x)
    with pytest.raises(ValueError,match='proof invalid'): ia.audit_legacy_state_continuity(tmp_path,3052,fr,frozen,state_sha)
    x=dict(base); x['causal']=False; write(x)
    with pytest.raises(ValueError,match='causal flags'): ia.audit_legacy_state_continuity(tmp_path,3052,fr,frozen,state_sha)
    x=dict(base); x['signal_state_sha256']='c'*64; write(x)
    with pytest.raises(ValueError,match='hash mismatch'): ia.audit_legacy_state_continuity(tmp_path,3052,fr,frozen,state_sha)
    x=dict(base); x['data_sha256']='e'*64; write(x)
    with pytest.raises(ValueError,match='data mismatch'): ia.audit_legacy_state_continuity(tmp_path,3052,fr,frozen,state_sha)
    write(base)
    assert ia.audit_legacy_state_continuity(tmp_path,3052,fr,frozen,state_sha)['status']=='PASS'

    monkeypatch.setattr(ia, 'LEGACY_MUTABLE_STATE_EVIDENCE', {})
    with pytest.raises(ValueError,match='frozen signal state hash mismatch'):
        ia.audit_legacy_state_continuity(tmp_path,9999,fr,frozen,state_sha)
    monkeypatch.setattr(ia, 'LEGACY_MUTABLE_STATE_EVIDENCE', {9999:'other.json'})
    (tmp_path/'other.json').write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='unsupported legacy'):
        ia.audit_legacy_state_continuity(tmp_path,9999,fr,frozen,state_sha)


def test_prospective_audit_accepts_pair_without_optional_state_hash(tmp_path):
    ledger, pre, result, freeze, state, fr, ad, actual = _pair_fixture(tmp_path, target=11)
    frozen = json.loads(freeze.read_text(encoding='utf-8'))
    frozen.pop('signal_state_file', None)
    frozen.pop('signal_state_sha256', None)
    freeze.write_text(json.dumps(frozen), encoding='utf-8')
    new_sha = _sha(freeze)
    fr['freeze_sha256'] = new_sha
    fr['hashes'].pop('state', None)
    ad['freeze_sha256'] = new_sha
    ledger.write_text(json.dumps({'schema': ia.LEDGER_SCHEMA, 'events':[fr,ad]}), encoding='utf-8')
    out = ia.audit_prospective_ledger(tmp_path, ledger)
    assert out['status']=='PASS' and out['pair_count']==1
