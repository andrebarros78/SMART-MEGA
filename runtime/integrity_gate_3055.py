from pathlib import Path
import json, hashlib
import smart_learning_epoch_reset as lr
import smart_current_epoch_contract as ce
import smart_total_integration_gate as tig
import smart_runtime_guard as rg
import smart_agent_skill_orchestration as aso
import smart_data_quality_gate as dq
import smart_independent_audit as ia

root=Path('.').resolve()
active=lr.verify_active_epoch(root/'SMART_ACTIVE_EPOCH.json')
ctx=ce.resolve(root)
assert ctx['status']=='RESET_READY'
assert ctx['authority_mode']=='NEW_ENGINEERING_EPOCH'
assert int(ctx['target_contest'])==3055 and int(ctx['cutoff_contest'])==3054
assert ctx['result_used'] is False
assert ctx['freeze_authority_present'] is False
assert active.get('freeze_authority') is None
assert active.get('parallel_locked_experiment') is None

def resolve(rel):
    p=Path(rel)
    return p if p.is_absolute() else (root/p).resolve()

data=resolve(ctx['data_file'])
ledger=resolve(active['state_paths']['ledger'])
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
audit=ia.run_independent_audit(root, ledger, bindings, data, 3055, start=1000)
checks={
    'active_epoch_verified': True,
    'target_3055_cutoff_3054': ctx['target_contest']==3055 and ctx['cutoff_contest']==3054,
    'result_not_used': ctx['result_used'] is False,
    'no_freeze_authority': ctx['freeze_authority_present'] is False and active.get('freeze_authority') is None,
    'no_parallel_legacy_experiment': active.get('parallel_locked_experiment') is None,
    'data_quality_pass': quality.get('status')=='PASS',
    'total_integration_pass': total.get('status')=='PASS',
    'runtime_guard_pass': runtime.get('status')=='PASS' and all(runtime.get('checks',{}).values()),
    'orchestration_pass': orch.get('integration_status')=='PASS',
    'orchestration_context_exact': orch.get('active_context',{}).get('target_contest')==3055 and orch.get('active_context',{}).get('cutoff_contest')==3054,
    'independent_audit_pass': audit.get('status')=='PASS' and all(audit.get('checks',{}).values()),
    'scientific_terminal_not_falsely_declared': orch.get('global_mission_state')=='MISSION_ACTIVE' and orch.get('terminal_6of6_proven') is False,
}
report={
    'schema':'SMART_PRE_GENERATION_INTEGRITY_3055_V1',
    'status':'PASS' if all(checks.values()) else 'FAIL',
    'target_contest':3055,
    'cutoff_contest':3054,
    'active_epoch_id':active['epoch_id'],
    'active_epoch_sha256':active['sha256'],
    'data_file':ctx['data_file'],
    'data_sha256':ctx['data_sha256'],
    'ledger_file':active['state_paths']['ledger'],
    'checks':checks,
    'data_quality':quality,
    'total_integration_sha256':total.get('sha256'),
    'runtime_guard':runtime,
    'orchestration_sha256':orch.get('sha256'),
    'independent_audit_sha256':audit.get('sha256'),
    'independent_audit_material_deficiencies':audit.get('material_deficiencies'),
    'generation_authorized': all(checks.values()),
    'freeze_created': False,
    'numbers_generated': False,
}
raw=json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
report['sha256']=hashlib.sha256(raw).hexdigest()
(root/'SMART_PRE_GENERATION_INTEGRITY_3055.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(root/'SMART_P14_INDEPENDENT_AUDIT_PRE_GENERATION_3055.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':report['status'],'checks':checks,'generation_authorized':report['generation_authorized'],'report_sha256':report['sha256'],'audit_status':audit.get('status'),'material_deficiencies':audit.get('material_deficiencies')},ensure_ascii=False,indent=2))
