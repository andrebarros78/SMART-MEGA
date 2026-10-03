from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

import smart_agent_skill_functional_gate as fg
import smart_champion_challenger as cc
import smart_data_quality_gate as dq
import smart_evidence_only_promotion as p15
import smart_global_integrity as gi
import smart_independent_audit as ia
import smart_independent_oracle as oracle
import smart_learning_activation_authority as aa
import smart_material_deficiency_registry as mdr
from smart_learning_activation_gate import ActivationDecision, evaluate

import test_smart_evidence_only_promotion as p15t
import test_smart_global_integrity as git
import test_smart_independent_audit as iat

ROOT = Path(__file__).resolve().parent


def _legacy_frozen():
    return json.loads((ROOT / 'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json').read_text(encoding='utf-8'))


def _legacy_prediction():
    return copy.deepcopy(_legacy_frozen()['challenger'])


def _decision():
    return evaluate(calibration_gain=1.0, validation_gain=1.0, holdout_gain=1.0, global_gain=1.0,
                    preregistered=True, prospective_evidence=True, leakage_free=True)


def _materiality():
    return aa.build_materiality_evidence(
        decision_change_count=4, validation_gain=1.0, holdout_gain=0.5, global_gain=0.5,
        independent_holdout=True, leakage_free=True,
    )


def _build_learning_authority(**kwargs):
    kwargs.setdefault('materiality_evidence', _materiality())
    return aa.build_authority(**kwargs)


def _write_auth(path: Path, obj: dict, *, rehash: bool = True):
    obj = copy.deepcopy(obj)
    if rehash:
        canonical = dict(obj); canonical.pop('sha256', None)
        obj['sha256'] = aa._sha256_json(canonical)
    path.write_text(json.dumps(obj), encoding='utf-8')
    return path


def _open_registry():
    return mdr.build_registry([{
        'id': 'OPEN_TEST', 'severity': 'P0', 'status': 'OPEN',
        'summary': 'coverage closure open item', 'evidence': [],
    }])


def test_oracle_numeric_normalization_and_cap_guards():
    for value in (True, 'x'):
        with pytest.raises(ValueError, match='numeric'):
            oracle._finite(value, 'x')
    for value in (float('nan'), float('inf')):
        with pytest.raises(ValueError, match='finite'):
            oracle._finite(value, 'x')
    with pytest.raises(ValueError, match='empty'):
        oracle._normalize({})
    with pytest.raises(ValueError, match='non-negative'):
        oracle._normalize({'a': -1.0, 'b': 2.0})
    with pytest.raises(ValueError, match='positive'):
        oracle._normalize({'a': 0.0, 'b': 0.0})
    capped = oracle._expert_cap({'a': 1.0, 'b': 0.0})
    assert abs(sum(capped.values()) - 1.0) < 1e-12
    with pytest.raises(ValueError, match='families'):
        oracle._family_cap({'a': 1.0}, {'b': 'x'})
    assert oracle._family_cap({'a': 1.0}, {'a': 'x'}) == {'a': 1.0}
    two = oracle._family_cap({'a': 0.95, 'b': 0.05}, {'a': 'x', 'b': 'y'})
    assert abs(sum(two.values()) - 1.0) < 1e-12


def test_oracle_recompute_signal_and_comparison_guards():
    p = _legacy_prediction()
    arrays, families = oracle._signal_values(p['raw_signals'])
    metrics = p['quality_metrics']
    oracle.recompute_dynamic_weights(metrics, families)
    with pytest.raises(ValueError, match='metrics/families'):
        oracle.recompute_dynamic_weights({}, families)
    bad = copy.deepcopy(metrics); bad[next(iter(bad))] = None
    with pytest.raises(ValueError, match='metric row'):
        oracle.recompute_dynamic_weights(bad, families)
    bad = copy.deepcopy(metrics); bad[next(iter(bad))].pop('utility')
    with pytest.raises(ValueError, match='missing factor'):
        oracle.recompute_dynamic_weights(bad, families)
    with pytest.raises(ValueError, match='raw_signals missing'):
        oracle._signal_values({})
    bad = copy.deepcopy(p['raw_signals']); bad[next(iter(bad))] = None
    with pytest.raises(ValueError, match='invalid raw signal'):
        oracle._signal_values(bad)
    bad = copy.deepcopy(p['raw_signals']); first = next(iter(bad)); bad[first]['values'].pop('1')
    with pytest.raises(ValueError, match='exactly 1..60'):
        oracle._signal_values(bad)
    bad = copy.deepcopy(p['raw_signals']); first = next(iter(bad)); bad[first]['family'] = ''
    with pytest.raises(ValueError, match='family missing'):
        oracle._signal_values(bad)
    with pytest.raises(ValueError, match='ids mismatch'):
        oracle._compare_map({}, {'a': 1.0}, 'x')
    with pytest.raises(ValueError, match='mismatch at'):
        oracle._compare_map({'a': 2.0}, {'a': 1.0}, 'x')
    assert arrays and families


def test_oracle_prediction_fail_closed_and_optional_paths():
    base = _legacy_prediction()
    with pytest.raises(ValueError, match='prediction must be object'):
        oracle.validate_prediction_snapshot(None)

    def fails(mutator, match):
        p = copy.deepcopy(base); mutator(p)
        with pytest.raises(ValueError, match=match):
            oracle.validate_prediction_snapshot(p)

    fails(lambda p: p.update(quality_metrics={}), 'quality_metrics ids')
    fails(lambda p: p.update(weight_components={}), 'weight_components ids')
    first = next(iter(base['weight_components']))
    fails(lambda p: p['weight_components'].__setitem__(first, None), 'weight component')
    fails(lambda p: p['weight_components'][first].__setitem__('raw_product', 999.0), 'raw product mismatch')
    fails(lambda p: p['weight_components'][first].__setitem__('final_weight', 999.0), 'final weight mismatch')
    fails(lambda p: p.update(ranking60=list(reversed(p['ranking60']))), 'ranking60 mismatch')
    fails(lambda p: p.update(meta_governor={'alternate_authorized': True, 'selected_top6': [1]}), 'selected_top6 invalid')
    fails(lambda p: p.update(top6=[1, 2, 3, 4, 5, 6]), 'final top6 mismatch')
    fails(lambda p: p.update(multi_challengers={'policies': {'quality_dynamic': {'top6': [1,2,3,4,5,6]}}}), 'quality_dynamic anchor mismatch')
    fails(lambda p: p.update(rank_score_calibration={'probabilities_by_number': {'1': 6.0}}), 'probability map ids')
    fails(lambda p: p.update(rank_score_calibration={'probabilities_by_number': {str(i): 0.0 for i in range(1,61)}}), 'probability mass')

    p = copy.deepcopy(base)
    p.pop('multi_challengers', None); p.pop('rank_score_calibration', None); p.pop('meta_governor', None)
    p['top6'] = p['ranking60'][:6]
    assert oracle.validate_prediction_snapshot(p)['verified'] is True

    p = copy.deepcopy(base)
    p['meta_governor'] = {'alternate_authorized': True, 'selected_top6': list(base['top6'])}
    out = oracle.validate_prediction_snapshot(p)
    assert out['verified'] is True and out['decision_mode'] == 'authorized_meta_governor'

    with pytest.raises(ValueError, match='frozen artifact'):
        oracle.validate_frozen_decision(None)
    assert oracle.validate_frozen_decision({})['status'] == 'LEGACY_NOT_APPLICABLE'
    frozen = _legacy_frozen(); frozen['governed_challenger_top6'] = [1,2,3,4,5,6]
    with pytest.raises(ValueError, match='governed challenger'):
        oracle.validate_frozen_decision(frozen)


def test_activation_authority_build_guards(monkeypatch, tmp_path):
    assert aa._is_hex64('a' * 64)
    assert not aa._is_hex64('short')
    assert not aa._is_hex64('z' * 64)
    with pytest.raises(ValueError, match='positive'):
        _build_learning_authority(target_contest=0, decision=_decision(), evidence_sha256='a'*64,
                           marginal_strength=.1, root=ROOT)
    with pytest.raises(ValueError, match='ActivationDecision'):
        _build_learning_authority(target_contest=1, decision=None, evidence_sha256='a'*64,
                           marginal_strength=.1, root=ROOT)
    rejected = ActivationDecision('REJECT', False, False, 'x')
    with pytest.raises(ValueError, match='prospective'):
        _build_learning_authority(target_contest=1, decision=rejected, evidence_sha256='a'*64,
                           marginal_strength=.1, root=ROOT)
    for strength in (float('nan'), -0.1, 1.1):
        with pytest.raises(ValueError, match='marginal_strength'):
            _build_learning_authority(target_contest=1, decision=_decision(), evidence_sha256='a'*64,
                               marginal_strength=strength, root=ROOT)
    with pytest.raises(ValueError, match='at least one'):
        _build_learning_authority(target_contest=1, decision=_decision(), evidence_sha256='a'*64,
                           marginal_strength=0.0, allow_meta_alternate_selection=False, root=ROOT)
    with pytest.raises(ValueError, match='64-hex'):
        _build_learning_authority(target_contest=1, decision=_decision(), evidence_sha256='bad',
                           marginal_strength=.1, root=ROOT)
    monkeypatch.setattr(aa, 'COMPONENTS', {'x': 'missing.py'})
    with pytest.raises(ValueError, match='component missing'):
        _build_learning_authority(target_contest=1, decision=_decision(), evidence_sha256='a'*64,
                           marginal_strength=.1, root=tmp_path)


def test_activation_authority_load_and_write_guards(tmp_path):
    base = _build_learning_authority(target_contest=4000, decision=_decision(), evidence_sha256='a'*64,
                              marginal_strength=.25, allow_meta_alternate_selection=True, root=ROOT)
    p = tmp_path / 'a.json'

    def bad(mutator, match, *, rehash=True):
        obj = copy.deepcopy(base); mutator(obj); _write_auth(p, obj, rehash=rehash)
        with pytest.raises((ValueError, FileExistsError), match=match):
            aa.load_activation_authority(p, target_contest=4000, root=ROOT)

    bad(lambda o: o.update(schema='BAD'), 'schema')
    bad(lambda o: o.update(marginal_strength=.5), 'self-hash', rehash=False)
    bad(lambda o: o.update(status='DISABLED'), 'not active')
    bad(lambda o: o.update(target_contest=True), 'target mismatch')
    bad(lambda o: o.update(evidence_sha256='bad'), 'evidence hash')
    bad(lambda o: o.update(activation_decision=None), 'decision missing')
    bad(lambda o: o['activation_decision'].pop('reason'), 'decision malformed')
    bad(lambda o: o['activation_decision'].update(predictive_weight_authorized='yes'), 'booleans invalid')
    bad(lambda o: o['activation_decision'].update(status='REJECT', predictive_weight_authorized=False), 'not production-authorized')
    bad(lambda o: o.update(marginal_strength=True), 'marginal strength')
    bad(lambda o: o.update(allow_meta_alternate_selection='yes'), 'meta flag')
    bad(lambda o: o.update(marginal_strength=0.0, allow_meta_alternate_selection=False), 'enables no mechanism')
    bad(lambda o: o.update(component_hashes={}), 'hashes incomplete')
    first = next(iter(base['component_hashes']))
    bad(lambda o: o['component_hashes'].__setitem__(first, '0'*64), 'hash stale')

    good = tmp_path / 'good.json'; aa.write_authority(good, base)
    with pytest.raises(FileExistsError, match='overwrite'):
        aa.write_authority(good, base)
    broken = copy.deepcopy(base); broken['sha256'] = '0'*64
    with pytest.raises(ValueError, match='self-hashed'):
        aa.write_authority(tmp_path/'broken.json', broken)


def test_data_quality_missing_columns_nonnumeric_null_and_empty(tmp_path):
    with pytest.raises(FileNotFoundError):
        dq.audit_draw_file(tmp_path/'missing.xlsx')
    p = tmp_path/'missing_cols.xlsx'; pd.DataFrame([{'Concurso':1}]).to_excel(p,index=False)
    with pytest.raises(ValueError, match='columns missing'):
        dq.audit_draw_file(p)
    cols = ['Concurso'] + [f'Bola{i}' for i in range(1,7)]
    p = tmp_path/'bad.xlsx'; pd.DataFrame([[1,'x',2,3,4,5,6]], columns=cols).to_excel(p,index=False)
    r = dq.audit_draw_file(p); assert r.status == 'FAIL' and r.invalid_draw_count == 1
    p = tmp_path/'null.xlsx'; pd.DataFrame([[1,None,2,3,4,5,6]], columns=cols).to_excel(p,index=False)
    r = dq.audit_draw_file(p); assert r.invalid_draw_count == 1
    p = tmp_path/'empty.xlsx'; pd.DataFrame(columns=cols).to_excel(p,index=False)
    r = dq.audit_draw_file(p); assert r.row_count == 0


def test_functional_gate_main_and_invalid_cutoff_date(monkeypatch, tmp_path):
    monkeypatch.setattr(fg, 'write', lambda *a, **k: {'status':'PASS','phase':'PRE_FREEZE','checks':{},'matrix':[]})
    fg.main(['--phase','PRE_FREEZE','--output',str(tmp_path/'proof.json')])
    p = tmp_path/'bad_date.xlsx'
    pd.DataFrame([{'Concurso':1,'Data do Sorteio':'not-a-date', **{f'Bola{i}':i for i in range(1,7)}}]).to_excel(p,index=False)
    with pytest.raises(ValueError, match='invalid cutoff draw date'):
        cc.source_cutoff_timestamp(p)


def test_evidence_only_rejects_unverified_independent_oracle():
    p13 = p15t._p13_eligible(); audit = p15t._audit(p13)
    audit['deterministic_replay']['independent_decision_oracle']['verified'] = False
    audit['sha256'] = p15.sha256_json({k:v for k,v in audit.items() if k!='sha256'})
    out = p15.assess_evidence_only_promotion(p13, p15t._gate(), audit, p15t._integrity())
    assert 'independent_audit_decision_oracle_not_verified' in out['blockers']


def test_global_integrity_material_registry_and_oracle_guards(monkeypatch, tmp_path):
    git._write_p14(tmp_path)
    (tmp_path/mdr.DEFAULT_PATH).unlink()
    mdr.write_registry(tmp_path/mdr.DEFAULT_PATH, _open_registry())
    with pytest.raises(ValueError, match='registry is stale'):
        gi.validate_p14_report(tmp_path)

    fresh = tmp_path/'fresh'; fresh.mkdir()
    mdr.write_registry(fresh/mdr.DEFAULT_PATH, _open_registry())
    git._write_p14(fresh)
    with pytest.raises(ValueError, match='has material deficiencies'):
        gi.validate_p14_report(fresh)

    clean = tmp_path/'clean'; clean.mkdir(); git._write_p14(clean, lambda o:o['deterministic_replay']['independent_decision_oracle'].update(verified=False))
    with pytest.raises(ValueError, match='decision oracle invalid'):
        gi.validate_p14_report(clean)

    monkeypatch.setattr(gi, 'validate_gate_state', lambda gate: {'status':'PASS'})
    monkeypatch.setattr(gi, 'current_source_hashes', lambda root: {})
    monkeypatch.setattr(gi, 'validate_p14_report', lambda root: {'status':'PASS'})
    monkeypatch.setattr(gi, 'load_material_deficiency_registry', lambda root=Path('.'): {'open_count':1,'open_deficiencies':['X']})
    import smart_continuous_red_team as rt
    monkeypatch.setattr(rt, 'verify_latest_report', lambda path, root: {'status':'PASS','report_sha256':'x'})
    (tmp_path/gi.DEFAULT_RED_TEAM_PATH).write_text('x')
    with pytest.raises(ValueError, match='blocked by material deficiencies'):
        gi.build_global_integrity_proof(tmp_path, {}, tmp_path/'none.xml', [])


def test_global_integrity_verify_open_and_stale_registry(monkeypatch, tmp_path):
    monkeypatch.setattr(gi, 'CRITICAL_SOURCE_FILES', ('a.py',))
    monkeypatch.setattr(gi, 'REQUIRED_GLOBAL_COVERAGE_SOURCES', ('a.py',))
    (tmp_path/'a.py').write_text('x=1\n')
    import smart_continuous_red_team as rt
    (tmp_path/gi.DEFAULT_RED_TEAM_PATH).write_text('red')
    monkeypatch.setattr(rt, 'verify_latest_report', lambda path=rt.REPORT_PATH, root=Path('.'): git._red_status())
    git._write_p14(tmp_path); cov=git._write_coverage(tmp_path); junit=git._write_junit(tmp_path); gate=git._gate()
    proof=gi.build_global_integrity_proof(tmp_path,gate,junit,[(cov.name,'a.py')])
    proof_path=tmp_path/gi.DEFAULT_PROOF_PATH; proof_path.write_text(json.dumps(proof))
    gate['global_integrity']={'file':proof_path.name,'sha256':gi.sha256_file(proof_path)}
    gate_path=tmp_path/'gate.json'; gate_path.write_text(json.dumps(gate))

    monkeypatch.setattr(gi, 'load_material_deficiency_registry', lambda root=Path('.'): {'open_count':1,'open_deficiencies':['X']})
    with pytest.raises(ValueError, match='open items'):
        gi.verify_global_integrity(tmp_path,gate_path,proof_path)

    clean_registry = proof['material_deficiency_registry']
    stale = copy.deepcopy(clean_registry); stale['status'] = 'DIFFERENT'; stale['open_count']=0; stale['open_deficiencies']=[]
    monkeypatch.setattr(gi, 'load_material_deficiency_registry', lambda root=Path('.'): stale)
    with pytest.raises(ValueError, match='registry is stale'):
        gi.verify_global_integrity(tmp_path,gate_path,proof_path)


def test_independent_audit_oracle_source_guards(monkeypatch, tmp_path):
    oracle_path = tmp_path/'smart_independent_oracle.py'
    shutil.copyfile(ROOT/'smart_independent_oracle.py', oracle_path)
    assert ia.audit_independence(tmp_path)['independent_oracle_file'] == 'smart_independent_oracle.py'
    oracle_path.write_text('x=1\n', encoding='utf-8')
    with pytest.raises(ValueError, match='oracle project/runtime source mismatch'):
        ia.audit_independence(tmp_path)

    oracle_path.write_text('import smart_fake\n', encoding='utf-8')
    original_sha = ia.sha256_source_file
    def same_oracle_hash(path):
        p = Path(path)
        if p.name == 'smart_independent_oracle.py':
            return 'a'*64
        return original_sha(p)
    monkeypatch.setattr(ia, 'sha256_source_file', same_oracle_hash)
    with pytest.raises(ValueError, match='imports project implementation'):
        ia.audit_independence(tmp_path)


def test_independent_audit_oracle_missing_and_verification_failures(monkeypatch, tmp_path):
    runtime_oracle = (ROOT/'smart_independent_oracle.py').resolve()
    original_is_file = Path.is_file
    def fake_is_file(self):
        try:
            if self.resolve() == runtime_oracle or (self.parent == tmp_path and self.name == 'smart_independent_oracle.py'):
                return False
        except Exception:
            pass
        return original_is_file(self)
    monkeypatch.setattr(Path, 'is_file', fake_is_file)
    with pytest.raises(ValueError, match='oracle source missing'):
        ia.audit_independence(tmp_path)

    ledger, *_ = iat._pair_fixture(tmp_path)
    monkeypatch.setattr(ia, 'validate_frozen_decision', lambda frozen: {'status':'PASS','verified':False})
    with pytest.raises(ValueError, match='did not verify every applicable'):
        ia.audit_prospective_ledger(tmp_path, ledger)

    data = tmp_path/'replay.xlsx'; iat._dataset(35, 99).to_excel(data,index=False)
    monkeypatch.setattr(ia, 'validate_prediction_snapshot', lambda prediction: {'verified':False})
    with pytest.raises(ValueError, match='could not verify replay prediction'):
        ia.audit_deterministic_replay(tmp_path, data, 36, start=20)


def test_material_registry_invalid_hex_and_noncanonical_top_level(tmp_path):
    assert not mdr._is_hex64('z'*64)
    obj = mdr.build_registry([]); obj['extra'] = True
    obj['sha256'] = mdr.sha256_json({k:v for k,v in obj.items() if k!='sha256'})
    p = tmp_path/'registry.json'; p.write_text(json.dumps(obj),encoding='utf-8')
    with pytest.raises(ValueError, match='canonical content invalid'):
        mdr.load_registry(p, root=tmp_path)


def test_agent_runtime_without_active_epoch_uses_base_critical_files(tmp_path):
    import smart_agent_runtime as ar
    runtime = object.__new__(ar.SmartAgentRuntime)
    runtime.root = tmp_path
    runtime.active_context = {}
    files = runtime._critical_files()
    assert 'SMART_ACTIVE_EPOCH.json' not in files
    assert set(ar.BASE_CRITICAL_CANONICAL_FILES).issubset(set(files))


def test_functional_gate_real_cli_entrypoint(monkeypatch, tmp_path):
    import runpy
    import sys
    monkeypatch.setattr(sys, 'argv', [str(ROOT/'smart_agent_skill_functional_gate.py'), '--phase', 'PRE_FREEZE', '--output', str(tmp_path/'fg-cli.json')])
    runpy.run_path(str(ROOT/'smart_agent_skill_functional_gate.py'), run_name='__main__')
    doc = json.loads((tmp_path/'fg-cli.json').read_text(encoding='utf-8'))
    assert doc['status'] == 'PASS' and doc['phase'] == 'PRE_FREEZE'


def test_oracle_zero_mass_other_family_and_multi_without_quality_dynamic():
    out = oracle._family_cap({'a': 1.0, 'b': 0.0}, {'a': 'x', 'b': 'y'})
    assert abs(sum(out.values()) - 1.0) < 1e-12 and out['b'] > 0.0
    p = _legacy_prediction()
    p['multi_challengers'] = {'policies': {}}
    assert oracle.validate_prediction_snapshot(p)['verified'] is True


def test_orchestration_state_path_and_pre_freeze_fail_closed(monkeypatch, tmp_path):
    import smart_agent_skill_orchestration as aso

    # No active epoch: deterministic defaults.
    defaults = aso._resolve_state_paths(tmp_path)
    assert defaults['ledger'].name == 'SMART_SIGNAL_LEDGER.json'

    active = tmp_path/'SMART_ACTIVE_EPOCH.json'
    active.write_text(json.dumps({'status':'RESET_READY'}), encoding='utf-8')
    with pytest.raises(ValueError, match='state_paths missing'):
        aso._resolve_state_paths(tmp_path)
    active.write_text(json.dumps({'status':'RESET_READY','state_paths':{'ledger':'x'}}), encoding='utf-8')
    with pytest.raises(ValueError, match='state_paths incomplete'):
        aso._resolve_state_paths(tmp_path)
    with pytest.raises(ValueError, match='escapes project root'):
        aso._project_relative(tmp_path, tmp_path.parent/'outside.json')

    active.write_text(json.dumps({'status':'RESET_READY'}), encoding='utf-8')
    with pytest.raises(ValueError, match='data_file missing'):
        aso._resolve_pre_freeze_context(tmp_path)
    active.write_text(json.dumps({'status':'RESET_READY','data_file':'none.xlsx','data_sha256':'0'*64}), encoding='utf-8')
    with pytest.raises(ValueError, match='immutable data is missing'):
        aso._resolve_pre_freeze_context(tmp_path)

    data = tmp_path/'d.xlsx'; pd.DataFrame([{'Concurso':1, **{f'Bola{i}':i for i in range(1,7)}}]).to_excel(data,index=False)
    active.write_text(json.dumps({'status':'RESET_READY','data_file':'d.xlsx','data_sha256':'0'*64}), encoding='utf-8')
    with pytest.raises(ValueError, match='data hash mismatch'):
        aso._resolve_pre_freeze_context(tmp_path)

    active.unlink()
    with pytest.raises(ValueError, match='canonical Mega-Sena.xlsx is missing'):
        aso._resolve_pre_freeze_context(tmp_path)
    canonical = tmp_path/'Mega-Sena.xlsx'; pd.DataFrame([{'X':1}]).to_excel(canonical,index=False)
    with pytest.raises(ValueError, match='no Concurso column'):
        aso._resolve_pre_freeze_context(tmp_path)
    pd.DataFrame(columns=['Concurso']).to_excel(canonical,index=False)
    with pytest.raises(ValueError, match='no contests'):
        aso._resolve_pre_freeze_context(tmp_path)

    pd.DataFrame([{'Concurso':1},{'Concurso':2}]).to_excel(data,index=False)
    import hashlib
    h = hashlib.sha256(data.read_bytes()).hexdigest()
    active.write_text(json.dumps({'status':'RESET_READY','data_file':'d.xlsx','data_sha256':h,'cutoff_contest':2,'target_contest':99}), encoding='utf-8')
    with pytest.raises(ValueError, match='target/cutoff differs'):
        aso._resolve_pre_freeze_context(tmp_path)


def test_orchestration_phase_resolution_fail_closed(tmp_path):
    import smart_agent_skill_orchestration as aso
    with pytest.raises(ValueError, match='phase must be'):
        aso.resolve_runtime_phase(tmp_path, 'WRONG')
    assert aso.resolve_runtime_phase(tmp_path, 'AUTO') == 'POST_FREEZE'
    active = tmp_path/'SMART_ACTIVE_EPOCH.json'
    active.write_text('{bad', encoding='utf-8')
    with pytest.raises(ValueError, match='cannot be parsed'):
        aso.resolve_runtime_phase(tmp_path, 'AUTO')
    active.write_text(json.dumps({'status':'FROZEN'}), encoding='utf-8')
    assert aso.resolve_runtime_phase(tmp_path, 'AUTO') == 'POST_FREEZE'
    active.write_text(json.dumps({'status':'UNKNOWN'}), encoding='utf-8')
    with pytest.raises(ValueError, match='no runtime phase'):
        aso.resolve_runtime_phase(tmp_path, 'AUTO')


def test_orchestration_post_freeze_check_branch(monkeypatch):
    import smart_agent_skill_orchestration as aso
    pre = aso._resolve_pre_freeze_context(ROOT)
    ctx = dict(pre)
    freeze = ROOT/'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json'
    ctx.update({
        'phase':'POST_FREEZE',
        'freeze_file': freeze.name,
        'freeze_sha256': aso._sha256(freeze),
        'signal_state_file': None,
        'signal_state_sha256': None,
        'pending_target': False,
    })
    monkeypatch.setattr(aso, '_resolve_active_context', lambda root: ctx)
    doc = aso.build_orchestration(ROOT, phase='POST_FREEZE')
    assert doc['checks']['active_freeze_present'] is True


def test_runtime_critical_files_without_active_epoch(tmp_path):
    import smart_agent_runtime as ar
    runtime = object.__new__(ar.SmartAgentRuntime)
    runtime.root = tmp_path
    runtime.active_context = {}
    files = runtime._critical_files()
    assert 'SMART_ACTIVE_EPOCH.json' not in files


def test_orchestration_remaining_state_path_and_phase_guards(monkeypatch, tmp_path):
    import smart_agent_skill_orchestration as aso
    active = tmp_path / 'SMART_ACTIVE_EPOCH.json'
    active.write_text(json.dumps({'state_paths': None}), encoding='utf-8')
    with pytest.raises(ValueError, match='state_paths missing'):
        aso._resolve_state_paths(tmp_path)
    active.write_text(json.dumps({'state_paths': {'ledger':'x'}}), encoding='utf-8')
    with pytest.raises(ValueError, match='state_paths incomplete'):
        aso._resolve_state_paths(tmp_path)
    with pytest.raises(ValueError, match='escapes project root'):
        aso._project_relative(tmp_path, tmp_path.parent / 'outside-smart')

    with pytest.raises(ValueError, match='phase must be'):
        aso.resolve_runtime_phase(tmp_path, 'BAD')
    active.write_text('{', encoding='utf-8')
    with pytest.raises(ValueError, match='cannot be parsed'):
        aso.resolve_runtime_phase(tmp_path, 'AUTO')
    active.write_text(json.dumps({'status':'FROZEN'}), encoding='utf-8')
    assert aso.resolve_runtime_phase(tmp_path, 'AUTO') == 'POST_FREEZE'
    active.write_text(json.dumps({'status':'UNKNOWN'}), encoding='utf-8')
    with pytest.raises(ValueError, match='has no runtime phase'):
        aso.resolve_runtime_phase(tmp_path, 'AUTO')
    active.unlink()
    assert aso.resolve_runtime_phase(tmp_path, 'AUTO') == 'POST_FREEZE'


def test_orchestration_pre_freeze_context_remaining_guards(monkeypatch, tmp_path):
    import smart_agent_skill_orchestration as aso
    import pandas as pd
    active = tmp_path / 'SMART_ACTIVE_EPOCH.json'

    active.write_text(json.dumps({'status':'RESET_READY'}), encoding='utf-8')
    with pytest.raises(ValueError, match='data_file missing'):
        aso._resolve_pre_freeze_context(tmp_path)

    active.write_text(json.dumps({'status':'RESET_READY','data_file':'data.bin','data_sha256':'x'}), encoding='utf-8')
    with pytest.raises(ValueError, match='immutable data is missing'):
        aso._resolve_pre_freeze_context(tmp_path)

    data = tmp_path / 'data.bin'; data.write_bytes(b'x')
    active.write_text(json.dumps({'status':'RESET_READY','data_file':'data.bin','data_sha256':'0'*64}), encoding='utf-8')
    with pytest.raises(ValueError, match='hash mismatch'):
        aso._resolve_pre_freeze_context(tmp_path)

    active.unlink();
    with pytest.raises(ValueError, match='canonical Mega-Sena.xlsx is missing'):
        aso._resolve_pre_freeze_context(tmp_path)

    canonical = tmp_path / 'Mega-Sena.xlsx'; canonical.write_bytes(b'x')
    monkeypatch.setattr(pd, 'read_excel', lambda p: pd.DataFrame({'X':[1]}))
    with pytest.raises(ValueError, match='no Concurso column'):
        aso._resolve_pre_freeze_context(tmp_path)

    monkeypatch.setattr(pd, 'read_excel', lambda p: pd.DataFrame({'Concurso': pd.Series(dtype=int)}))
    with pytest.raises(ValueError, match='no contests'):
        aso._resolve_pre_freeze_context(tmp_path)

    data.write_bytes(b'abc')
    active.write_text(json.dumps({
        'status':'RESET_READY','data_file':'data.bin','data_sha256':aso._sha256(data),
        'cutoff_contest':999,'target_contest':1000
    }), encoding='utf-8')
    monkeypatch.setattr(pd, 'read_excel', lambda p: pd.DataFrame({'Concurso':[1,2]}))
    with pytest.raises(ValueError, match='target/cutoff differs'):
        aso._resolve_pre_freeze_context(tmp_path)


def test_orchestration_post_freeze_branch(monkeypatch):
    import smart_agent_skill_orchestration as aso
    ctx = aso._resolve_pre_freeze_context(ROOT)
    ctx = dict(ctx)
    ctx['freeze_file'] = 'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json'
    ctx['freeze_sha256'] = aso._sha256(ROOT / ctx['freeze_file'])
    monkeypatch.setattr(aso, '_resolve_active_context', lambda root: dict(ctx))
    doc = aso.build_orchestration(ROOT, phase='POST_FREEZE')
    assert doc['phase'] == 'POST_FREEZE'
    assert doc['checks']['active_freeze_present'] is True


def test_expert_cap_zero_mass_pathology_is_bounded_in_production_and_oracle():
    import smart_signal_weights as sw
    for fn in (sw._expert_cap, oracle._expert_cap):
        out = fn({'a': 0.9, 'b': 0.1, 'c': 0.0}, cap=0.42)
        assert abs(sum(out.values()) - 1.0) < 1e-12
        assert max(out.values()) <= 0.42 + 1e-12
        assert all(v >= 0.0 for v in out.values())

    fam = oracle._family_cap({'a':1.0,'b':0.0}, {'a':'x','b':'y'}, cap=0.6)
    assert abs(sum(fam.values()) - 1.0) < 1e-12

    pred = _legacy_prediction()
    pred['multi_challengers'] = {'policies': {}}
    result = oracle.validate_prediction_snapshot(pred)
    assert result['status'] == 'PASS'


def test_orchestration_pre_freeze_without_active_epoch_uses_canonical_data(tmp_path):
    import pandas as pd
    import smart_agent_skill_orchestration as aso
    pd.DataFrame([
        {'Concurso': 1, 'Bola1': 1, 'Bola2': 2, 'Bola3': 3, 'Bola4': 4, 'Bola5': 5, 'Bola6': 6},
        {'Concurso': 2, 'Bola1': 7, 'Bola2': 8, 'Bola3': 9, 'Bola4': 10, 'Bola5': 11, 'Bola6': 12},
    ]).to_excel(tmp_path / 'Mega-Sena.xlsx', index=False)
    ctx = aso._resolve_pre_freeze_context(tmp_path)
    assert ctx['phase'] == 'PRE_FREEZE'
    assert ctx['cutoff_contest'] == 2
    assert ctx['target_contest'] == 3
    assert ctx['data_file'] == 'Mega-Sena.xlsx'

def test_expert_cap_randomized_capped_simplex_properties():
    import numpy as np
    import smart_signal_weights as sw
    rng = np.random.default_rng(20260906)
    for n in range(3, 13):
        for _ in range(40):
            raw = rng.random(n)
            raw[rng.random(n) < 0.30] = 0.0
            if raw.sum() == 0.0:
                raw[0] = 1.0
            weights = {f'e{i}': float(v) for i, v in enumerate(raw)}
            requested_cap = float(rng.uniform(0.05, 0.70))
            feasible_cap = max(requested_cap, 1.0 / n)
            for fn in (sw._expert_cap, oracle._expert_cap):
                out = fn(weights, cap=requested_cap)
                assert abs(sum(out.values()) - 1.0) < 1e-11
                assert min(out.values()) >= -1e-14
                assert max(out.values()) <= feasible_cap + 1e-11
