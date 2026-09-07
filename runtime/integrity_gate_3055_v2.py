from pathlib import Path
import json, hashlib
import smart_learning_epoch_reset as lr
import smart_current_epoch_contract as ce
import smart_engineering_activation as ea
import smart_regression_evidence as re
import smart_total_integration_gate as tig
import smart_runtime_guard as rg
import smart_agent_skill_orchestration as aso
import smart_data_quality_gate as dq
import smart_independent_audit as ia

root=Path(__file__).resolve().parents[1]
active=lr.verify_active_epoch(root/'SMART_ACTIVE_EPOCH.json')
ctx=ce.resolve(root)
activation=json.loads((root/'SMART_FULL_ACTIVATION_EPOCH.json').read_text(encoding='utf-8-sig'))
current_fp=ea._code_fingerprint(root)
reg=re.junit_summary(root/'SMART_AUDIT_JUNIT_CURRENT.xml')

def resolve(rel):
    p=Path(rel)
    return p if p.is_absolute() else (root/p).resolve()

data=resolve(ctx['data_file'])
ledger=resolve(active['state_paths']['ledger'])
freeze=resolve(active['state_paths']['freeze'])
cur_ledger=json.loads(ledger.read_text(encoding='utf-8-sig'))
quality=dq.audit_draw_file(data, expected_max_contest=3054).to_dict()
total=tig.write(root, root/'SMART_TOTAL_INTEGRATION_PRE_GENERATION_3055.json', phase='PRE_FREEZE')
runtime=rg.audit(root)
orch=aso.build_orchestration(root, phase='PRE_FREEZE')
bindings=[root/n for n in (
    'SMART_P14_COVERAGE_BINDING_AUDIT.json',
    'SMART_P14_COVERAGE_BINDING_ORCHESTRATOR.json',
    'SMART_P14_COVERAGE_BINDING_PROMOTION.json',
    'SMART_P14_COVERAGE_BINDING_EVIDENCE_ONLY.json',
)]
historical=ia.audit_prospective_ledger(root, root/'SMART_SIGNAL_LEDGER.json')
replay=ia.audit_deterministic_replay(root, data, 3055, start=1000)
independence=ia.audit_independence(root)
coverage=ia.audit_coverage_bindings(root, bindings)
deficiencies=ia.load_material_deficiency_registry(root=root)
checks={
    'regression_676_green': reg.get('status')=='PASS' and reg.get('tests')==676 and reg.get('failures')==0 and reg.get('errors')==0,
    'code_fingerprint_still_fresh': current_fp.get('sha256')==activation.get('code_fingerprint',{}).get('sha256'),
    'active_epoch_verified': active.get('status')=='RESET_READY',
    'active_context_exact_3055_3054': ctx.get('target_contest')==3055 and ctx.get('cutoff_contest')==3054,
    'new_engineering_epoch_authority': ctx.get('authority_mode')=='NEW_ENGINEERING_EPOCH',
    'result_not_used': ctx.get('result_used') is False,
    'no_freeze_authority': ctx.get('freeze_authority_present') is False and active.get('freeze_authority') is None,
    'freeze_file_absent': not freeze.exists(),
    'current_epoch_ledger_pristine': len(cur_ledger.get('events',[]))==0,
    'no_parallel_legacy_experiment': active.get('parallel_locked_experiment') is None,
    'data_quality_pass': quality.get('status')=='PASS',
    'total_integration_pass': total.get('status')=='PASS' and total.get('phase')=='PRE_FREEZE',
    'runtime_guard_pass': runtime.get('status')=='PASS' and all(runtime.get('checks',{}).values()),
    'orchestration_pass': orch.get('integration_status')=='PASS',
    'orchestration_context_exact': orch.get('active_context',{}).get('target_contest')==3055 and orch.get('active_context',{}).get('cutoff_contest')==3054,
    'historical_prospective_ledger_pass': historical.get('status')=='PASS',
    'current_3055_replay_pass': replay.get('status')=='PASS',
    'current_3055_independent_oracle_verified': replay.get('independent_decision_oracle',{}).get('verified') is True,
    'auditor_independence_pass': independence.get('status')=='PASS',
    'coverage_bindings_pass': coverage.get('status')=='PASS',
    'material_deficiencies_zero': deficiencies.get('status')=='PASS' and deficiencies.get('open_count')==0,
    'scientific_terminal_not_falsely_declared': orch.get('global_mission_state')=='MISSION_ACTIVE' and orch.get('terminal_6of6_proven') is False,
}
report={
    'schema':'SMART_PRE_GENERATION_INTEGRITY_3055_V2',
    'status':'PASS' if all(checks.values()) else 'FAIL',
    'target_contest':3055,
    'cutoff_contest':3054,
    'active_epoch_id':active['epoch_id'],
    'active_epoch_sha256':active['sha256'],
    'data_file':ctx['data_file'],
    'data_sha256':ctx['data_sha256'],
    'ledger_file':active['state_paths']['ledger'],
    'freeze_file':active['state_paths']['freeze'],
    'checks':checks,
    'regression':reg,
    'code_fingerprint_sha256':current_fp['sha256'],
    'data_quality':quality,
    'total_integration_sha256':total.get('sha256'),
    'runtime_guard':runtime,
    'orchestration_sha256':orch.get('sha256'),
    'historical_ledger_audit_status':historical.get('status'),
    'current_replay_status':replay.get('status'),
    'current_replay_oracle_verified':replay.get('independent_decision_oracle',{}).get('verified'),
    'auditor_independence_status':independence.get('status'),
    'coverage_status':coverage.get('status'),
    'material_deficiency_registry':deficiencies,
    'generation_authorized':all(checks.values()),
    'freeze_created':False,
    'numbers_generated':False,
}
raw=json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
report['sha256']=hashlib.sha256(raw).hexdigest()
(root/'SMART_PRE_GENERATION_INTEGRITY_3055.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
independent_bundle={
    'schema':'SMART_PRE_GENERATION_INDEPENDENT_AUDIT_3055_V1',
    'status':'PASS' if checks['historical_prospective_ledger_pass'] and checks['current_3055_replay_pass'] and checks['current_3055_independent_oracle_verified'] and checks['auditor_independence_pass'] and checks['coverage_bindings_pass'] else 'FAIL',
    'historical_prospective_ledger':historical,
    'current_3055_replay':replay,
    'independence':independence,
    'coverage':coverage,
}
independent_bundle['sha256']=hashlib.sha256(json.dumps(independent_bundle,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
(root/'SMART_P14_INDEPENDENT_AUDIT_PRE_GENERATION_3055.json').write_text(json.dumps(independent_bundle,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':report['status'],'generation_authorized':report['generation_authorized'],'checks':checks,'report_sha256':report['sha256'],'independent_audit_status':independent_bundle['status'],'independent_audit_sha256':independent_bundle['sha256']},ensure_ascii=False,indent=2))
