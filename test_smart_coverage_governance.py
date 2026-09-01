from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import adjudicate_signal_challenger as adj
import freeze_next_research as fr
import smart_champion_challenger as cc
import smart_v2_engine as e
import smart_v2_production as prod


def draws(seed=2, n=50):
    rng = np.random.default_rng(seed)
    return np.array([np.sort(rng.choice(e.NUMBERS, 6, replace=False)) for _ in range(n)], dtype=int)


def make_excel(path: Path, ds, start_contest=1, include_date=True):
    rows = []
    for j, d in enumerate(ds):
        row = {'Concurso': start_contest + j}
        if include_date:
            row['Data do Sorteio'] = pd.Timestamp('2020-01-01') + pd.Timedelta(days=j)
        row.update({f'Bola{i}': int(d[i - 1]) for i in range(1, 7)})
        rows.append(row)
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def make_freeze_ledger(tmp_path: Path, target=10):
    values = {str(i): float(i) / 60.0 for i in range(1, 61)}
    values2 = {str(i): float(61-i) / 60.0 for i in range(1, 61)}
    challenger_payload = {
        'top6': [1,2,3,4,5,7],
        'raw_signals': {'freq25': {'values': values}, 'freq50': {'values': values2}},
        'weights': {'freq25': 0.6, 'freq50': 0.4},
        'quality_metrics': {'freq25': {'quality': 1.0}, 'freq50': {'quality': 1.0}},
    }
    snapshot = {
        'raw_signals': challenger_payload['raw_signals'],
        'weights': challenger_payload['weights'],
        'quality_metrics': challenger_payload['quality_metrics'],
    }
    freeze_file = tmp_path / f'freeze_{target}.json'
    data_sha = 'd' * 64; engine_sha = 'e' * 64
    frozen = {
        'schema': 'SMART_CHAMPION_CHALLENGER_FREEZE_2', 'target_contest': target,
        'cutoff_contest': target - 1, 'frozen_before_result': True, 'causal_cutoff': True,
        'data_sha256': data_sha, 'engine_sha256': engine_sha,
        'champion': {'top6': [1,2,3,4,5,6]}, 'challenger': challenger_payload,
    }
    freeze_file.write_text(json.dumps(frozen), encoding='utf-8')
    h = cc.sha256(freeze_file)
    event = {
        'event_type': 'FREEZE', 'target_contest': target, 'cutoff_contest': target - 1,
        'freeze_file': str(freeze_file), 'freeze_sha256': h, 'frozen_before_result': True,
        'causal_cutoff': True, 'data_sha256': data_sha,
        'champion_top6': [1,2,3,4,5,6], 'challenger_top6': [1,2,3,4,5,7],
        'snapshot': snapshot, 'hashes': {'engine': engine_sha},
    }
    ledger = {'schema': cc.LEDGER_SCHEMA, 'events': [event]}
    ledger_path = tmp_path / 'ledger.json'; cc.write_ledger(ledger_path, ledger)
    return ledger_path, event


def result_excel(path: Path, target=10, nums=(1,2,3,4,5,7), duplicate=False):
    rows=[]
    count = 2 if duplicate else 1
    for _ in range(count):
        row={'Concurso': target}; row.update({f'Bola{i}': int(nums[i-1]) for i in range(1,7)}); rows.append(row)
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def prospective_ledger(order=None, malformed=False):
    order = order or list(range(4000, 4020))
    rows=[]
    for i,c in enumerate(order):
        rows.append({'contest': c, 'frozen_before_result': True, 'adjudicated': True,
                     'prediction_sha256': f'{i:064x}'[-64:], 'smart_hits': 2, 'baseline_hits': 1,
                     'comparison_eligible': True,
                     'e_value_after': 12.0 if i == len(order)-1 else 1.0,
                     'comparison_eligible': True})
    if malformed:
        rows[0].pop('contest')
    return {'schema':'SMART_PROSPECTIVE_LEDGER_1','records':rows}


def test_production_ledger_all_error_paths_and_order_fix():
    assert not prod.validate_ledger(None)['valid']
    assert 'no adjudicated comparison-eligible' in prod.validate_ledger({'schema':prod.LEGACY_LEDGER_SCHEMA,'records':[]})['reason']
    assert 'positive integer' in prod.validate_ledger(prospective_ledger(malformed=True))['reason']
    bad = prospective_ledger(); bad['records'][0]['smart_hits'] = 7
    assert 'smart_hits' in prod.validate_ledger(bad)['reason']
    reversed_order = prospective_ledger(order=list(range(4019,3999,-1)))
    assert prod.validate_ledger(reversed_order)['reason'] == 'contest order invalid'
    good = prod.validate_ledger(prospective_ledger())
    assert good['valid'] and good['reason'] == 'legacy diagnostic conditions met'
    assert good['diagnostic_only'] is True and good['production_authority'] is False


def test_production_sha_decide_false_placebo_branch_and_main(tmp_path, monkeypatch, capsys):
    f=tmp_path/'x'; f.write_bytes(b'x'); assert len(prod.sha256(f)) == 64
    audit={'walk_forward':{'excess_hits':1,'diagnostic_z_vs_uniform':3,'total_hits':1},
           'placebo':{'total_hits':99},'monte_carlo_null':{'false_positive_rate_z_ge_2':0}}
    monkeypatch.setattr(prod, 'REQUIRE_BEAT_PLACEBO', False)
    state=prod.decide(audit, prospective_ledger())
    assert state['mode'] == 'NO_PREDICTIVE_SIGNAL_DETECTED'
    assert state['legacy_diagnostic_signal_detected'] is True
    assert state['legacy_production_authority_disabled'] is True
    auditp=tmp_path/'audit.json'; auditp.write_text(json.dumps(audit),encoding='utf-8')
    data=tmp_path/'data.bin'; data.write_bytes(b'data')
    led=tmp_path/'p.json'; led.write_text(json.dumps(prospective_ledger()),encoding='utf-8')
    out=tmp_path/'out.json'
    monkeypatch.setattr(sys,'argv',['smart_v2_production.py','--audit',str(auditp),'--data',str(data),'--ledger',str(led),'--out',str(out)])
    prod.main(); saved=json.loads(out.read_text(encoding='utf-8'))
    assert saved['mode']=='NO_PREDICTIVE_SIGNAL_DETECTED'
    assert saved['schema']=='SMART_V2_PRODUCTION_STATE_3'
    assert 'mode' in capsys.readouterr().out


def test_champion_helpers_source_ledger_active_pairing(tmp_path, monkeypatch):
    f=tmp_path/'x'; f.write_bytes(b'abc'); assert len(cc.sha256(f)) == 64
    d=make_excel(tmp_path/'dated.xlsx', draws(4,3), include_date=True)
    assert cc.source_cutoff_timestamp(d) is not None
    nd=make_excel(tmp_path/'nodate.xlsx', draws(5,3), include_date=False)
    assert cc.source_cutoff_timestamp(nd) is None
    monkeypatch.setattr(cc.pd, 'read_excel', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('x')))
    assert cc.source_cutoff_timestamp(nd) is None
    monkeypatch.undo()
    lp=tmp_path/'newledger.json'; L=cc.load_ledger(lp); assert L['events']==[]
    lp.write_text(json.dumps({'schema':'bad','events':[]}),encoding='utf-8')
    with pytest.raises(ValueError, match='invalid SMART'):
        cc.load_ledger(lp)
    assert cc.active_freeze({'schema':cc.LEDGER_SCHEMA,'events':[]}, 1) is None
    dup={'schema':cc.LEDGER_SCHEMA,'events':[{'event_type':'FREEZE','target_contest':1,'freeze_sha256':'a'},
                   {'event_type':'FREEZE','target_contest':1,'freeze_sha256':'b'}]}
    with pytest.raises(ValueError, match='supersede'):
        cc.active_freeze(dup,1)
    dupad={'schema':cc.LEDGER_SCHEMA,'events':[{'event_type':'FREEZE','target_contest':1,'freeze_sha256':'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'},
                     {'event_type':'ADJUDICATION','target_contest':1,'freeze_sha256':'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'},
                     {'event_type':'ADJUDICATION','target_contest':1,'freeze_sha256':'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'}]}
    with pytest.raises(ValueError, match='duplicate adjudication'):
        cc.paired_events(dupad)
    assert cc.promotion_eligibility_status({'schema':cc.LEDGER_SCHEMA,'events':[]})['reason'].startswith('no adjudicated')


def test_champion_promotion_noneligible_and_version_paths(tmp_path, monkeypatch):
    ledger={'schema':cc.LEDGER_SCHEMA,'events':[{'event_type':'FREEZE','target_contest':1,'freeze_sha256':'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','frozen_before_result':False,'causal_cutoff':True},
                      {'event_type':'ADJUDICATION','target_contest':1,'freeze_sha256':'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','challenger_hits':6,'champion_hits':0,'e_value_after':20.0}]}
    p=cc.promotion_eligibility_status(ledger); assert not p['eligible'] and p['n']==0
    out=tmp_path/'f.json'; assert cc._next_version_path(out)==out
    out.write_text('x')
    assert cc._next_version_path(out).name == 'f.v2.json'
    original=Path.exists
    monkeypatch.setattr(Path,'exists',lambda self: True)
    with pytest.raises(RuntimeError, match='allocate'):
        cc._next_version_path(out)
    monkeypatch.setattr(Path,'exists',original)


def test_champion_freeze_errors_idempotence_supersede_and_context_hash(tmp_path):
    ds=draws(8,45); data=make_excel(tmp_path/'mega.xlsx',ds)
    out=tmp_path/'freeze.json'; ledger=tmp_path/'ledger.json'; state=tmp_path/'state.json'
    with pytest.raises(ValueError, match='already present'):
        cc.freeze_champion_challenger(data,45,out,ledger,state,start=10)
    with pytest.raises(ValueError, match='immediately before'):
        cc.freeze_champion_challenger(data,47,out,ledger,state,start=10)
    first=cc.freeze_champion_challenger(data,46,out,ledger,state,start=10)
    obj=json.loads(Path(first['freeze_file']).read_text(encoding='utf-8'))
    assert len(obj['context_regime_sha256'])==64
    second=cc.freeze_champion_challenger(data,46,out,ledger,state,start=10)
    assert second['status']=='ALREADY_FROZEN_IDENTICAL_EVENT_PRESERVED'
    L=json.loads(ledger.read_text(encoding='utf-8'))
    L['events'][0]['hashes']['context_regime']='changed'
    ledger.write_text(json.dumps(L),encoding='utf-8')
    third=cc.freeze_champion_challenger(data,46,out,ledger,state,start=10)
    assert third['status']=='FROZEN_SUPERSEDING_PRIOR'
    L=json.loads(ledger.read_text(encoding='utf-8'))
    L['events'].append({'event_type':'ADJUDICATION','target_contest':46})
    ledger.write_text(json.dumps(L),encoding='utf-8')
    with pytest.raises(ValueError, match='adjudication must reference active freeze hash'):
        cc.freeze_champion_challenger(data,46,out,ledger,state,start=10)


def test_champion_main(monkeypatch, capsys):
    monkeypatch.setattr(cc, 'freeze_champion_challenger', lambda *a, **k: {'status':'OK'})
    monkeypatch.setattr(sys,'argv',['smart_champion_challenger.py','--target','1'])
    cc.main(); assert 'OK' in capsys.readouterr().out


def test_adjudication_normal_and_all_guards(tmp_path):
    lp, ev = make_freeze_ledger(tmp_path,10)
    result=result_excel(tmp_path/'res.xlsx',10)
    r=adj.adjudicate(result,10,lp)
    assert r['challenger_hits']==6 and r['champion_hits']==5
    with pytest.raises(ValueError, match='already adjudicated'):
        adj.adjudicate(result,10,lp)
    empty=tmp_path/'empty.json'; cc.write_ledger(empty,cc.load_ledger(Path(tmp_path/'never.json')))
    with pytest.raises(ValueError, match='active frozen prediction'):
        adj.adjudicate(result,10,empty)
    lp2, ev2=make_freeze_ledger(tmp_path/'sub' if False else tmp_path,11)
    # Corrupt artifact after hashing.
    Path(ev2['freeze_file']).write_text('changed',encoding='utf-8')
    with pytest.raises(ValueError, match='hash mismatch'):
        adj.adjudicate(result_excel(tmp_path/'r11.xlsx',11),11,lp2)


def test_adjudication_result_validation_eprocess_and_main(tmp_path, monkeypatch, capsys):
    lp, ev=make_freeze_ledger(tmp_path,12)
    with pytest.raises(ValueError, match='exactly once'):
        adj.adjudicate(result_excel(tmp_path/'dup.xlsx',12,duplicate=True),12,lp)
    bad=result_excel(tmp_path/'bad.xlsx',12,nums=(1,1,2,3,4,5))
    with pytest.raises(ValueError, match='invalid result'):
        adj.adjudicate(bad,12,lp)
    with pytest.raises(ValueError, match='hits'):
        adj._next_e_value({'schema':cc.LEDGER_SCHEMA,'events':[]},-100,100)
    led={'schema':cc.LEDGER_SCHEMA,'events':[{'event_type':'FREEZE','target_contest':1,'freeze_sha256':'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','frozen_before_result':True,'causal_cutoff':True},
                   {'event_type':'ADJUDICATION','target_contest':1,'freeze_sha256':'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','challenger_hits':1,'champion_hits':1,'e_value_after':2.0}]}
    assert adj._next_e_value(led,2,1) > 2.0
    monkeypatch.setattr(adj,'adjudicate',lambda *a, **k:{'target_contest':99})
    monkeypatch.setattr(sys,'argv',['adjudicate_signal_challenger.py','--result-data','x','--target','99'])
    adj.main(); assert '99' in capsys.readouterr().out


def test_freeze_research_hash_policy_guards_and_main(tmp_path, monkeypatch, capsys):
    f=tmp_path/'x'; f.write_bytes(b'a'); assert len(fr.sha256(f))==64
    ds=draws(20,18); pol=fr.current_policy(ds,start=12); assert len(pol['top6'])==6
    data=make_excel(tmp_path/'mega.xlsx',ds)
    monkeypatch.setattr(sys,'argv',['freeze_next_research.py','--data',str(data),'--target','18','--out',str(tmp_path/'a.json'),'--start','10'])
    with pytest.raises(SystemExit,match='already present'):
        fr.main()
    monkeypatch.setattr(sys,'argv',['freeze_next_research.py','--data',str(data),'--target','20','--out',str(tmp_path/'b.json'),'--start','10'])
    with pytest.raises(SystemExit,match='immediately before'):
        fr.main()
    out=tmp_path/'ok.json'
    monkeypatch.setattr(sys,'argv',['freeze_next_research.py','--data',str(data),'--target','19','--out',str(out),'--start','10'])
    fr.main(); assert out.exists(); assert 'target' in capsys.readouterr().out


def test_engine_main_via_stub(monkeypatch, capsys):
    fake={'walk_forward':{'x':1},'placebo':{'x':2},'monte_carlo_null':{'x':3}}
    monkeypatch.setattr(e,'audit',lambda *a, **k: fake)
    monkeypatch.setattr(sys,'argv',['smart_v2_engine.py'])
    e.main(); assert 'walk_forward' in capsys.readouterr().out


def test_real_entrypoint_guards_via_runpy(tmp_path, monkeypatch, capsys):
    import runpy
    # Champion/Challenger entrypoint: real execution on a temporary causal dataset.
    ds = draws(1234, 30)
    data = make_excel(tmp_path/'cli_mega.xlsx', ds)
    out = tmp_path/'cli_freeze.json'; led = tmp_path/'cli_ledger.json'; state = tmp_path/'cli_state.json'
    monkeypatch.setattr(sys, 'argv', ['smart_champion_challenger.py','--data',str(data),'--target','31','--out',str(out),'--ledger',str(led),'--state',str(state),'--start','10'])
    runpy.run_path(str(Path(cc.__file__)), run_name='__main__')
    assert out.exists() and led.exists()

    # Adjudication entrypoint: real execution against its own frozen artifact.
    res = result_excel(tmp_path/'cli_result.xlsx', 31, nums=(1,2,3,4,5,6))
    monkeypatch.setattr(sys, 'argv', ['adjudicate_signal_challenger.py','--result-data',str(res),'--target','31','--ledger',str(led)])
    runpy.run_path(str(Path(adj.__file__)), run_name='__main__')
    assert 'target_contest' in capsys.readouterr().out


def test_paired_events_ignores_hash_match_with_wrong_target():
    import smart_champion_challenger as cc
    h = 'a' * 64
    ledger = {'schema': cc.LEDGER_SCHEMA, 'events': [
        {'event_type': 'FREEZE', 'target_contest': 2, 'freeze_sha256': h},
        {'event_type': 'ADJUDICATION', 'target_contest': 1, 'freeze_sha256': h,
         'challenger_hits': 1, 'champion_hits': 1, 'e_value_after': 1.0},
    ]}
    with pytest.raises(ValueError, match='supersede chain requires at least one freeze'):
        cc.paired_events(ledger)


def test_identical_active_freeze_with_missing_artifact_is_rebuilt(tmp_path):
    import json
    import numpy as np
    import pandas as pd
    import smart_v2_engine as e
    import smart_champion_challenger as cc

    rng = np.random.default_rng(424242)
    draws = np.array([np.sort(rng.choice(e.NUMBERS, 6, replace=False)) for _ in range(80)], dtype=int)
    rows = []
    for i, d in enumerate(draws, start=1):
        row = {'Concurso': i, 'Data do Sorteio': pd.Timestamp('2024-01-01') + pd.Timedelta(days=i)}
        row.update({f'Bola{j}': int(d[j - 1]) for j in range(1, 7)})
        rows.append(row)
    data = tmp_path / 'mega.xlsx'
    pd.DataFrame(rows).to_excel(data, index=False)
    out = tmp_path / 'freeze.json'
    ledger = tmp_path / 'ledger.json'
    state = tmp_path / 'state.json'

    first = cc.freeze_champion_challenger(data, 81, out, ledger, state, start=20)
    assert first['status'] == 'FROZEN'
    old_hash = first['freeze_sha256']
    out.unlink()
    second = cc.freeze_champion_challenger(data, 81, out, ledger, state, start=20)
    assert second['status'] == 'FROZEN_SUPERSEDING_PRIOR'
    assert out.exists()
    led = json.loads(ledger.read_text(encoding='utf-8'))
    assert any(ev.get('event_type') == 'SUPERSEDE' and ev.get('old_freeze_sha256') == old_hash for ev in led['events'])
    assert cc.active_freeze(led, 81)['freeze_sha256'] == second['freeze_sha256']


def _gate_manifest(status='PROVEN', evidence=True, freeze_allowed=True):
    return {
        'schema': cc.PRE_3052_GATE_SCHEMA,
        'freeze_allowed': freeze_allowed,
        'items': [
            {'priority': i, 'id': f'P{i:02d}', 'status': status,
             'evidence': [f'proof-{i}'] if evidence else []}
            for i in range(1, 16)
        ],
    }


def test_pre_3052_gate_all_guards_and_release(tmp_path):
    assert cc.require_pre_3052_gate(3051, tmp_path/'missing.json') is None
    with pytest.raises(ValueError, match='gate missing'):
        cc.require_pre_3052_gate(3052, tmp_path/'missing.json')

    p = tmp_path/'gate.json'
    bad = _gate_manifest(); bad['schema'] = 'BAD'; p.write_text(json.dumps(bad), encoding='utf-8')
    with pytest.raises(ValueError, match='gate invalid'):
        cc.require_pre_3052_gate(3052, p)

    bad = _gate_manifest(); bad['items'] = bad['items'][:-1]; p.write_text(json.dumps(bad), encoding='utf-8')
    with pytest.raises(ValueError, match='gate invalid'):
        cc.require_pre_3052_gate(3052, p)

    bad = _gate_manifest(); bad['items'][0]['priority'] = 99; p.write_text(json.dumps(bad), encoding='utf-8')
    with pytest.raises(ValueError, match='priorities invalid'):
        cc.require_pre_3052_gate(3052, p)

    bad = _gate_manifest(status='TO_VERIFY_OR_IMPLEMENT'); p.write_text(json.dumps(bad), encoding='utf-8')
    with pytest.raises(ValueError, match='gate blocked'):
        cc.require_pre_3052_gate(3052, p)

    bad = _gate_manifest(evidence=False); p.write_text(json.dumps(bad), encoding='utf-8')
    with pytest.raises(ValueError, match='gate blocked'):
        cc.require_pre_3052_gate(3052, p)

    bad = _gate_manifest(freeze_allowed=False); p.write_text(json.dumps(bad), encoding='utf-8')
    with pytest.raises(ValueError, match='gate blocked'):
        cc.require_pre_3052_gate(3052, p)

    good = _gate_manifest(); p.write_text(json.dumps(good), encoding='utf-8')
    assert cc.require_pre_3052_gate(3052, p)['freeze_allowed'] is True


def test_pre_3052_gate_fails_closed_when_registered_items_are_pending(tmp_path):
    gate = json.loads(Path('SMART_3052_IMPLEMENTATION_GATE.json').read_text(encoding='utf-8'))
    gate['items'][8]['status'] = 'TO_VERIFY_OR_IMPLEMENT'
    gate['items'][8]['evidence'] = []
    gate['freeze_allowed'] = False
    gate_path = tmp_path / 'gate.json'
    gate_path.write_text(json.dumps(gate), encoding='utf-8')
    with pytest.raises(ValueError, match='pre-3052 implementation gate blocked'):
        cc.require_pre_3052_gate(3052, gate_path)



def test_adjudication_automatically_appends_attribution_and_is_idempotent(tmp_path):
    lp, _ = make_freeze_ledger(tmp_path, target=70)
    res = result_excel(tmp_path/'r70.xlsx', 70, nums=(1,2,3,4,5,7))
    out = adj.adjudicate(res, 70, lp)
    assert len(out['attribution_sha256']) == 64
    ledger = json.loads(lp.read_text(encoding='utf-8'))
    attrs = [ev for ev in ledger['events'] if ev.get('event_type') == 'ATTRIBUTION' and ev.get('target_contest') == 70]
    assert len(attrs) == 1
    assert attrs[0]['policy_effect'] == 'NONE_POST_RESULT_DIAGNOSTIC_ONLY'
    assert len(attrs[0]['attribution_engine_sha256']) == 64
    again = adj.append_attribution_for_existing(lp, 70)
    assert again['status'] == 'ALREADY_ATTRIBUTED_EVENT_PRESERVED'
    assert again['attribution_sha256'] == attrs[0]['attribution_sha256']


def test_append_attribution_for_legacy_adjudication_and_guards(tmp_path):
    lp, fr_event = make_freeze_ledger(tmp_path, target=71)
    ledger = json.loads(lp.read_text(encoding='utf-8'))
    ledger['events'].append({
        'event_type': 'ADJUDICATION', 'target_contest': 71, 'freeze_sha256': fr_event['freeze_sha256'],
        'actual_numbers': [1,2,3,4,5,7], 'champion_hits': 5, 'challenger_hits': 6, 'e_value_after': 1.0,
    })
    cc.write_ledger(lp, ledger)
    out = adj.append_attribution_for_existing(lp, 71)
    assert out['status'] == 'ATTRIBUTION_APPENDED'
    ledger2 = json.loads(lp.read_text(encoding='utf-8'))
    assert len([ev for ev in ledger2['events'] if ev.get('event_type') == 'ATTRIBUTION']) == 1

    empty = tmp_path/'empty_attr.json'; cc.write_ledger(empty, cc.load_ledger(tmp_path/'missing.json'))
    with pytest.raises(ValueError, match='exactly one adjudication'):
        adj.append_attribution_for_existing(empty, 71)

    lp2, _ = make_freeze_ledger(tmp_path, target=72)
    led2 = json.loads(lp2.read_text(encoding='utf-8'))
    led2['events'].append({'event_type':'ADJUDICATION','target_contest':72,'freeze_sha256':'bad','actual_numbers':[1,2,3,4,5,6]})
    cc.write_ledger(lp2, led2)
    with pytest.raises(ValueError, match='adjudication must reference active freeze hash'):
        adj.append_attribution_for_existing(lp2, 72)


def test_adjudication_rejects_predated_attribution(tmp_path):
    lp, fr_event = make_freeze_ledger(tmp_path, target=73)
    led = json.loads(lp.read_text(encoding='utf-8'))
    led['events'].append({'event_type':'ATTRIBUTION','target_contest':73,'freeze_sha256':fr_event['freeze_sha256'],
                          'attribution_sha256':'a'*64})
    cc.write_ledger(lp, led)
    with pytest.raises(ValueError, match='post-result sequence event exists without adjudication'):
        adj.adjudicate(result_excel(tmp_path/'r73.xlsx',73),73,lp)


def test_append_attribution_rejects_duplicate_attribution_events(tmp_path):
    lp, fr_event = make_freeze_ledger(tmp_path, target=74)
    led = json.loads(lp.read_text(encoding='utf-8'))
    for x in ('a','b'):
        led['events'].append({'event_type':'ATTRIBUTION','target_contest':74,'freeze_sha256':fr_event['freeze_sha256'],
                              'attribution_sha256':x*64})
    cc.write_ledger(lp, led)
    with pytest.raises(ValueError, match='at most one attribution'):
        adj.append_attribution_for_existing(lp,74)

