from pathlib import Path

import pytest

import smart_continuous_red_team as red
from smart_agent_runtime import SmartAgentRuntime
from smart_agent_skill_functional_gate import evaluate

ROOT = Path(__file__).resolve().parent


def test_agent_runtime_v2_executes_native_probes_and_preserves_canonical_hashes():
    doc = SmartAgentRuntime(ROOT).run()
    assert doc['schema'] == 'SMART_AGENT_RUNTIME_V2'
    assert doc['status'] == 'PASS'
    assert doc['checks']['all_9_agents_native_probed'] is True
    assert doc['checks']['all_agents_have_executed_function_evidence'] is True
    assert doc['checks']['critical_canonical_files_unchanged'] is True
    for execution in doc['executions'].values():
        assert execution['probe_result']['pass'] is True
        assert execution['probe_result']['executed_functions']
        assert execution['probe_id'] == execution['probe_result']['probe_id']


def test_functional_gate_binds_every_capability_to_a_passed_probe_without_external_execution():
    doc = evaluate(ROOT)
    assert doc['schema'] == 'SMART_AGENT_SKILL_FUNCTIONAL_GATE_V3'
    assert doc['status'] == 'PASS'
    assert len(doc['matrix']) == 41
    for row in doc['matrix']:
        assert row['probe_pass'] is True
        assert row['executed_functions']
        assert row['external_skill_source_executed'] is False
        assert row['direct_named_skill_execution'] is False
        if row['pertinent']:
            assert row['semantic_binding_kind'] == 'METHODOLOGY_ALIAS_TO_NATIVE_ROLE_PROBE'
        assert row['realization'] in {
            'SOURCE_ONLY_QUARANTINE_CURATED',
            'METHODOLOGY_DISTILLED_TO_NATIVE_LANE_PROBE',
            'NATIVE_LANE_PROBE',
        }


def test_agent_skill_layer_is_behaviorally_hashed_by_continuous_red_team():
    required = {
        'smart_agent_skill_orchestration.py',
        'smart_agent_runtime.py',
        'smart_agent_skill_functional_gate.py',
        'smart_learning_activation_gate.py',
    }
    assert required.issubset(set(red.BEHAVIORAL_FILES))


def test_operational_freeze_entrypoints_have_no_stale_3051_defaults():
    champion = (ROOT / 'smart_champion_challenger.py').read_text(encoding='utf-8-sig')
    research = (ROOT / 'freeze_next_research.py').read_text(encoding='utf-8-sig')
    assert "default='Mega-Sena_through_3050.xlsx'" not in champion
    assert 'default=3051' not in champion
    assert "default='Mega-Sena_through_3050.xlsx'" not in research
    assert 'default=3051' not in research
    assert "add_argument('--data', required=True" in champion
    assert "add_argument('--target', type=int, required=True" in champion
    assert "add_argument('--data',required=True" in research
    assert "add_argument('--target',type=int,required=True" in research

def test_champion_cli_fails_closed_without_explicit_dataset(monkeypatch):
    import sys
    import smart_champion_challenger as cc
    monkeypatch.setattr(sys, 'argv', ['smart_champion_challenger.py', '--target', '3054'])
    with pytest.raises(SystemExit):
        cc.main()


def test_legacy_patch_repair_and_sandbox_entrypoints_are_not_top_level():
    banned = {
        'extend_prospective_data.py', 'finalize_p13_gate.py', 'patch_data_integrity.py',
        'patch_false_positive.py', 'smart_governance_repair.py',
        'smart_repair_model_registry_and_learning.py', 'smart_repair_p1p2_binding.py',
        'smart_v2_sandbox.py', 'smart_v2_stress.py', 'smart_v2_stress_fast.py', 'smart_v2_validation.py',
    }
    assert not [name for name in banned if (ROOT / name).exists()]
    archive = ROOT / 'archive' / 'legacy_entrypoints_20260905'
    assert all((archive / name).is_file() for name in banned)

def test_importing_evidence_and_procedural_modules_has_no_write_side_effects(tmp_path, monkeypatch):
    import importlib
    import os
    import sys

    modules = [
        'smart_execution_checkpoint',
        'smart_refresh_falsification_report',
        'smart_procedural_cronogram_acquire',
        'smart_procedural_youtube_batch',
        'smart_procedural_youtube_recent_acquire',
    ]
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.rglob('*'))
    for name in modules:
        sys.modules.pop(name, None)
        importlib.import_module(name)
    after = set(tmp_path.rglob('*'))
    assert after == before


def test_generic_scientific_clis_do_not_embed_stale_3053_input_defaults():
    falsification = (ROOT / 'smart_falsification_lab.py').read_text(encoding='utf-8-sig')
    cartography = (ROOT / 'smart_randomness_cartography.py').read_text(encoding='utf-8-sig')
    for text in (falsification, cartography):
        assert 'default="Mega-Sena_through_3053_v2.xlsx"' not in text
        assert 'default=3053' not in text
        assert '--expected-max-contest' in text
        assert 'required=True' in text

def test_agent_runtime_fail_closed_branches_and_output_paths(tmp_path, monkeypatch, capsys):
    import smart_agent_runtime as ar

    rt = ar.SmartAgentRuntime(ROOT)
    # artifact missing branch
    monkeypatch.setitem(ar.ARTIFACT_HINTS, 'quarantine_curator', ['definitely_missing.file'])
    assert rt.artifact_records('quarantine_curator') == []
    monkeypatch.setitem(ar.ARTIFACT_HINTS, 'quarantine_curator', ['.external_skills_acquired/ACQUISITION_MANIFEST.json'])

    # invalid quarantine item branch
    original_is_dir = Path.is_dir
    monkeypatch.setattr(Path, 'is_dir', lambda self: False if self.name == 'aeon' else original_is_dir(self))
    bad = rt._probe_quarantine_curator()
    assert bad['pass'] is False and 'aeon' in bad['invalid_items']
    monkeypatch.setattr(Path, 'is_dir', original_is_dir)

    # failed native probe branch
    monkeypatch.setattr(rt, '_probe_quarantine_curator', lambda: {'probe_id':'x','executed_functions':['x'],'pass':False})
    with pytest.raises(RuntimeError, match='native probe failed'):
        rt._probe_for('quarantine_curator')

    rt = ar.SmartAgentRuntime(ROOT)
    rt.orchestration['integration_status'] = 'FAIL'
    with pytest.raises(RuntimeError, match='declarative orchestration'):
        rt.run()

    rt = ar.SmartAgentRuntime(ROOT)
    orig_targets = rt.targets_for
    monkeypatch.setattr(rt, 'targets_for', lambda name: ['missing_native_target.py'] if name == 'quarantine_curator' else orig_targets(name))
    with pytest.raises(RuntimeError, match='missing native targets'):
        rt.run()

    rt = ar.SmartAgentRuntime(ROOT)
    monkeypatch.setattr(rt, 'artifact_records', lambda name: [] if name == 'quarantine_curator' else ar.SmartAgentRuntime.artifact_records(rt, name))
    with pytest.raises(RuntimeError, match='no verifiable runtime evidence'):
        rt.run()

    # absolute output path branch
    out = tmp_path / 'runtime-proof.json'
    doc = ar.write_runtime(ROOT, out)
    assert out.is_file() and doc['status'] == 'PASS'

    # main wrapper without canonical write
    monkeypatch.setattr(ar, 'write_runtime', lambda root: {'status':'PASS','agent_count':9,'capability_count':41,'checks':{'x':True}})
    ar.main()
    assert '"status": "PASS"' in capsys.readouterr().out


def test_functional_gate_error_output_and_main_branches(tmp_path, monkeypatch, capsys):
    import smart_agent_skill_functional_gate as fg
    inventory={'source_only_skills':[],'v2_capabilities':[],'v3_capabilities':[],'native_scientific_libraries':[]}
    with pytest.raises(ValueError, match='unknown capability origin'):
        fg._origin('unknown-capability', inventory)
    out = tmp_path / 'functional-proof.json'
    doc = fg.write(ROOT, out)
    assert out.is_file() and doc['status'] == 'PASS'
    monkeypatch.setattr(fg, 'write', lambda root: {'status':'PASS','checks':{'x':True},'matrix':[1]*41})
    fg.main()
    assert '"status": "PASS"' in capsys.readouterr().out


def test_orchestration_write_failure_and_main_branches(tmp_path, monkeypatch, capsys):
    import smart_agent_skill_orchestration as aso
    doc = aso.write_orchestration(ROOT, str(tmp_path / 'orch.json'))
    assert doc['integration_status'] == 'PASS'
    monkeypatch.setattr(aso, 'build_orchestration', lambda root: {'integration_status':'FAIL','diagnostics':{'x':'bad'}})
    with pytest.raises(RuntimeError, match='agent/skill integration failed'):
        aso.write_orchestration(tmp_path, 'bad.json')
    good = {
        'integration_status':'PASS',
        'inventory':{'unique_capabilities_total':41},
        'global_mission_state':'MISSION_ACTIVE',
        'terminal_6of6_proven':False,
        'active_context':{'target_contest':999,'cutoff_contest':998},
        'evidence_hashes':{'active_freeze_sha256':'a'*64},
    }
    monkeypatch.setattr(aso, 'write_orchestration', lambda root: good)
    aso.main([])
    aso.main([str(tmp_path)])
    out=capsys.readouterr().out
    assert out.count('"integration_status": "PASS"') == 2


def test_agent_layer_resolves_active_context_without_fixed_contest_literals():
    import smart_agent_skill_orchestration as aso
    doc = aso.build_orchestration(ROOT)
    assert doc['active_context']['target_contest'] == doc['active_context']['cutoff_contest'] + 1
    assert doc['active_context']['target_contest'] == 3055
    assert doc['active_context']['cutoff_contest'] == 3054
    source = (ROOT / 'smart_agent_skill_orchestration.py').read_text(encoding='utf-8')
    runtime_source = (ROOT / 'smart_agent_runtime.py').read_text(encoding='utf-8')
    assert 'SMART_3054_CHAMPION_CHALLENGER_FREEZE.v2.json' not in source
    assert 'Mega-Sena_through_3053_v2.xlsx' not in runtime_source


def test_agent_runtime_data_guardian_uses_resolved_active_dataset():
    import smart_agent_runtime as ar
    rt = ar.SmartAgentRuntime(ROOT)
    probe = rt._probe_data_guardian()
    assert probe['pass'] is True
    assert probe['data_file'] == rt.active_context['data_file']
    assert probe['contest_max'] == rt.active_context['cutoff_contest']


def test_active_context_resolver_is_future_target_agnostic(tmp_path, monkeypatch):
    import json
    import smart_agent_skill_orchestration as aso
    import smart_champion_challenger as cc

    target = 9001
    cutoff = target - 1
    data = tmp_path / 'future_draws.xlsx'
    data.write_bytes(b'future-dataset-placeholder')
    freeze = tmp_path / 'future_freeze.json'
    import hashlib
    data_sha = hashlib.sha256(data.read_bytes()).hexdigest()
    freeze.write_text(json.dumps({
        'target_contest': target,
        'cutoff_contest': cutoff,
        'data_file': data.name,
        'data_sha256': data_sha,
        'signal_state_file': None,
    }), encoding='utf-8')
    freeze_sha = hashlib.sha256(freeze.read_bytes()).hexdigest()
    ledger = {
        'schema': cc.LEDGER_SCHEMA,
        'events': [{'event_type':'FREEZE','target_contest':target,'cutoff_contest':cutoff,
                    'freeze_file':freeze.name,'freeze_sha256':freeze_sha,'data_sha256':data_sha}],
    }
    (tmp_path / 'SMART_SIGNAL_LEDGER.json').write_text(json.dumps(ledger), encoding='utf-8')
    monkeypatch.setattr(cc, 'load_ledger', lambda path: ledger)
    monkeypatch.setattr(cc, 'active_freeze', lambda doc, requested: ledger['events'][0] if requested == target else None)
    ctx = aso._resolve_active_context(tmp_path)
    assert ctx['target_contest'] == target
    assert ctx['cutoff_contest'] == cutoff
    assert ctx['freeze_file'] == freeze.name
    assert ctx['data_file'] == data.name
    assert ctx['pending_target'] is True


def test_active_context_resolver_rejects_multiple_pending_targets(tmp_path, monkeypatch):
    import json
    import pytest
    import smart_agent_skill_orchestration as aso
    import smart_champion_challenger as cc
    ledger = {
        'schema': cc.LEDGER_SCHEMA,
        'events': [
            {'event_type':'FREEZE','target_contest':9001,'cutoff_contest':9000,'freeze_file':'a.json','freeze_sha256':'a'},
            {'event_type':'FREEZE','target_contest':9002,'cutoff_contest':9001,'freeze_file':'b.json','freeze_sha256':'b'},
        ],
    }
    (tmp_path / 'SMART_SIGNAL_LEDGER.json').write_text(json.dumps(ledger), encoding='utf-8')
    monkeypatch.setattr(cc, 'load_ledger', lambda path: ledger)
    with pytest.raises(ValueError, match='ambiguous pending freezes'):
        aso._resolve_active_context(tmp_path)


def test_active_context_rejects_paths_outside_project_root(tmp_path, monkeypatch):
    import json
    import pytest
    import smart_agent_skill_orchestration as aso
    import smart_champion_challenger as cc
    outside = tmp_path.parent / 'outside-freeze.json'
    outside.write_text(json.dumps({'target_contest':9001,'cutoff_contest':9000,'data_file':'x.xlsx'}), encoding='utf-8')
    ledger = {'schema':cc.LEDGER_SCHEMA,'events':[{'event_type':'FREEZE','target_contest':9001,'cutoff_contest':9000,'freeze_file':'../outside-freeze.json','freeze_sha256':'x'}]}
    (tmp_path / 'SMART_SIGNAL_LEDGER.json').write_text(json.dumps(ledger), encoding='utf-8')
    monkeypatch.setattr(cc, 'load_ledger', lambda path: ledger)
    monkeypatch.setattr(cc, 'active_freeze', lambda doc, requested: ledger['events'][0])
    with pytest.raises(ValueError, match='escapes project root'):
        aso._resolve_active_context(tmp_path)


def test_runtime_critical_hashes_include_active_dataset():
    import smart_agent_runtime as ar
    rt = ar.SmartAgentRuntime(ROOT)
    hashes = rt._critical_hashes()
    assert rt.active_context['data_file'] in hashes
    assert hashes[rt.active_context['data_file']] == rt.active_context['data_sha256']


def test_active_context_rejects_freeze_hash_tamper(tmp_path, monkeypatch):
    import json
    import pytest
    import smart_agent_skill_orchestration as aso
    import smart_champion_challenger as cc
    data = tmp_path / 'd.xlsx'; data.write_bytes(b'x')
    freeze = tmp_path / 'f.json'; freeze.write_text(json.dumps({'target_contest':9001,'cutoff_contest':9000,'data_file':data.name,'data_sha256':'0'*64}), encoding='utf-8')
    ledger={'schema':cc.LEDGER_SCHEMA,'events':[{'event_type':'FREEZE','target_contest':9001,'cutoff_contest':9000,'freeze_file':freeze.name,'freeze_sha256':'f'*64,'data_sha256':'0'*64}]}
    (tmp_path/'SMART_SIGNAL_LEDGER.json').write_text(json.dumps(ledger),encoding='utf-8')
    monkeypatch.setattr(cc,'load_ledger',lambda path: ledger)
    monkeypatch.setattr(cc,'active_freeze',lambda doc,requested: ledger['events'][0])
    with pytest.raises(ValueError, match='freeze artifact hash mismatch'):
        aso._resolve_active_context(tmp_path)


def test_active_context_rejects_data_hash_tamper(tmp_path, monkeypatch):
    import json, hashlib
    import pytest
    import smart_agent_skill_orchestration as aso
    import smart_champion_challenger as cc
    data=tmp_path/'d.xlsx'; data.write_bytes(b'actual')
    freeze=tmp_path/'f.json'; freeze.write_text(json.dumps({'target_contest':9001,'cutoff_contest':9000,'data_file':data.name,'data_sha256':'0'*64}),encoding='utf-8')
    freeze_sha=hashlib.sha256(freeze.read_bytes()).hexdigest()
    ledger={'schema':cc.LEDGER_SCHEMA,'events':[{'event_type':'FREEZE','target_contest':9001,'cutoff_contest':9000,'freeze_file':freeze.name,'freeze_sha256':freeze_sha,'data_sha256':'0'*64}]}
    (tmp_path/'SMART_SIGNAL_LEDGER.json').write_text(json.dumps(ledger),encoding='utf-8')
    monkeypatch.setattr(cc,'load_ledger',lambda path: ledger)
    monkeypatch.setattr(cc,'active_freeze',lambda doc,requested: ledger['events'][0])
    with pytest.raises(ValueError, match='data hash mismatch'):
        aso._resolve_active_context(tmp_path)


def test_deployment_and_continuity_require_product_build_certification():
    continuity=(ROOT/'smart_continuity_consolidator.py').read_text(encoding='utf-8')
    deployment=(ROOT/'smart_finalize_deployment.py').read_text(encoding='utf-8')
    certification=(ROOT/'smart_product_certification.py').read_text(encoding='utf-8')
    assert 'build_product_certification' in deployment
    assert 'write_product_certification' in deployment
    assert 'phase="BUILD"' in certification
    assert 'functional_evaluate(root, phase="BUILD")' in certification
    assert 'total_integration_evaluate(root, phase="BUILD")' in certification
    assert 'wmcp_execution_proof_pass' in deployment
    assert 'SMART_WMCP_EXECUTION_PROOF_20260905.json' in deployment
    assert 'operator_interface' in deployment
    assert 'freeze_is_construction_gate' in deployment
    assert 'smart_operator.py' in deployment
    assert 'agent_skill_functional_integration_pass' in continuity


def test_orchestration_mission_consistency_allows_legitimate_terminal_state(monkeypatch):
    import smart_agent_skill_orchestration as aso
    real_read=aso._read_json
    def fake_read(path):
        obj=real_read(path)
        if path.name=='SMART_MISSION_STATUS.json':
            obj=dict(obj); obj['status']='MISSION_PROVEN'; obj['terminal_6of6_proven']=True
        return obj
    monkeypatch.setattr(aso,'_read_json',fake_read)
    doc=aso.build_orchestration(ROOT)
    assert doc['checks']['global_mission_status_consistent'] is True



def _synthetic_active_context_fixture(tmp_path, *, target=9001, with_state=False):
    import json, hashlib
    data=tmp_path/'data.xlsx'; data.write_bytes(b'dataset')
    state=None; state_sha=None
    if with_state:
        state=tmp_path/'state.json'; state.write_text('{}',encoding='utf-8'); state_sha=hashlib.sha256(state.read_bytes()).hexdigest()
    data_sha=hashlib.sha256(data.read_bytes()).hexdigest()
    freeze=tmp_path/'freeze.json'
    payload={'target_contest':target,'cutoff_contest':target-1,'data_file':data.name,'data_sha256':data_sha,
             'signal_state_file':state.name if state else None,'signal_state_sha256':state_sha}
    freeze.write_text(json.dumps(payload),encoding='utf-8')
    freeze_sha=hashlib.sha256(freeze.read_bytes()).hexdigest()
    event={'event_type':'FREEZE','target_contest':target,'cutoff_contest':target-1,'freeze_file':freeze.name,
           'freeze_sha256':freeze_sha,'data_sha256':data_sha}
    ledger={'schema':'SMART_SIGNAL_LEDGER_1','events':[event]}
    (tmp_path/'SMART_SIGNAL_LEDGER.json').write_text(json.dumps(ledger),encoding='utf-8')
    return ledger,event,freeze,data,state


def test_active_context_fail_closed_remaining_branches(tmp_path, monkeypatch):
    import json, hashlib, pytest
    import smart_agent_skill_orchestration as aso
    import smart_champion_challenger as cc

    # empty project file path
    with pytest.raises(ValueError, match='path is empty'):
        aso._resolve_project_file(tmp_path, '', label='x')

    # no freeze events
    empty={'schema':cc.LEDGER_SCHEMA,'events':[]}
    monkeypatch.setattr(cc,'load_ledger',lambda path: empty)
    with pytest.raises(ValueError, match='no freeze to resolve'):
        aso._resolve_active_context(tmp_path)

    # active_freeze resolves none
    ledger,event,freeze,data,state=_synthetic_active_context_fixture(tmp_path)
    monkeypatch.setattr(cc,'load_ledger',lambda path: ledger)
    monkeypatch.setattr(cc,'active_freeze',lambda doc,target: None)
    with pytest.raises(ValueError, match='no active freeze'):
        aso._resolve_active_context(tmp_path)

    # missing freeze_file declaration
    bad=dict(event); bad['freeze_file']=''
    monkeypatch.setattr(cc,'active_freeze',lambda doc,target: bad)
    with pytest.raises(ValueError, match='does not declare freeze_file'):
        aso._resolve_active_context(tmp_path)

    # declared freeze file does not exist
    bad=dict(event); bad['freeze_file']='missing.json'
    monkeypatch.setattr(cc,'active_freeze',lambda doc,target: bad)
    with pytest.raises(ValueError, match='artifact missing'):
        aso._resolve_active_context(tmp_path)

    # cutoff mismatch, with recomputed valid freeze hash
    payload=json.loads(freeze.read_text(encoding='utf-8')); payload['cutoff_contest']=8998
    freeze.write_text(json.dumps(payload),encoding='utf-8')
    bad=dict(event); bad['freeze_sha256']=hashlib.sha256(freeze.read_bytes()).hexdigest()
    monkeypatch.setattr(cc,'active_freeze',lambda doc,target: bad)
    with pytest.raises(ValueError, match='cutoff mismatch'):
        aso._resolve_active_context(tmp_path)


def test_active_context_fail_closed_data_and_state_branches(tmp_path, monkeypatch):
    import json, hashlib, pytest
    import smart_agent_skill_orchestration as aso
    import smart_champion_challenger as cc

    ledger,event,freeze,data,state=_synthetic_active_context_fixture(tmp_path,with_state=True)
    monkeypatch.setattr(cc,'load_ledger',lambda path: ledger)
    monkeypatch.setattr(cc,'active_freeze',lambda doc,target: event)

    # missing data file with freeze still hash-valid
    data.rename(tmp_path/'data-away.xlsx')
    with pytest.raises(ValueError, match='data artifact missing'):
        aso._resolve_active_context(tmp_path)
    (tmp_path/'data-away.xlsx').rename(data)

    # ledger/data hash mismatch distinct from frozen data hash mismatch
    event['data_sha256']='f'*64
    with pytest.raises(ValueError, match='ledger/data hash mismatch'):
        aso._resolve_active_context(tmp_path)
    event['data_sha256']=json.loads(freeze.read_text(encoding='utf-8'))['data_sha256']

    # missing state file
    state.rename(tmp_path/'state-away.json')
    with pytest.raises(ValueError, match='state artifact missing'):
        aso._resolve_active_context(tmp_path)
    (tmp_path/'state-away.json').rename(state)

    # state hash mismatch while state file exists
    payload=json.loads(freeze.read_text(encoding='utf-8')); payload['signal_state_sha256']='0'*64
    freeze.write_text(json.dumps(payload),encoding='utf-8')
    event['freeze_sha256']=hashlib.sha256(freeze.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='state hash mismatch'):
        aso._resolve_active_context(tmp_path)


def test_runtime_optional_state_and_absolute_output_branches(tmp_path):
    import smart_agent_runtime as ar
    rt=ar.SmartAgentRuntime(ROOT)
    original=dict(rt.active_context)
    rt.active_context['signal_state_file']=None
    files=rt._critical_files()
    assert None not in files
    rt.active_context=original
    out=tmp_path/'runtime-proof.json'
    doc=ar.write_runtime(ROOT,out)
    assert out.is_file() and doc['status']=='PASS'


def test_functional_gate_absolute_output_branch(tmp_path):
    import smart_agent_skill_functional_gate as fg
    out=tmp_path/'functional-proof-absolute.json'
    doc=fg.write(ROOT,out)
    assert out.is_file() and doc['status']=='PASS'



def test_relative_output_resolution_branches(tmp_path, monkeypatch):
    import smart_agent_runtime as ar
    import smart_agent_skill_functional_gate as fg
    class FakeRuntime:
        def __init__(self, root): self.root=root
        def run(self): return {'status':'PASS','agent_count':9,'capability_count':41,'checks':{}}
    monkeypatch.setattr(ar,'SmartAgentRuntime',FakeRuntime)
    r=ar.write_runtime(tmp_path,'runtime-relative.json')
    assert (tmp_path/'runtime-relative.json').is_file() and r['status']=='PASS'
    monkeypatch.setattr(fg,'evaluate',lambda root:{'status':'PASS','checks':{},'matrix':[],'sha256':'a'*64})
    f=fg.write(tmp_path,'functional-relative.json')
    assert (tmp_path/'functional-relative.json').is_file() and f['status']=='PASS'


def test_activation_gate_is_frozen_and_globally_protected():
    import smart_champion_challenger as cc
    import smart_global_integrity as gi
    assert 'learning_activation_gate' in cc.PROMOTION_LINEAGE_COMPONENTS
    assert 'smart_learning_activation_gate.py' in gi.CRITICAL_SOURCE_FILES
    assert 'smart_learning_activation_gate.py' in gi.REQUIRED_GLOBAL_COVERAGE_SOURCES
    assert 'smart_continuity_consolidator.py' in gi.CRITICAL_SOURCE_FILES
    assert 'smart_finalize_deployment.py' in gi.CRITICAL_SOURCE_FILES
