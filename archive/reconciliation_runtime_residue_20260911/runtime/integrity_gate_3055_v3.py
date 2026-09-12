from pathlib import Path
import json, hashlib, shutil
import smart_continuous_red_team as rt
import smart_learning_epoch_reset as lr
import smart_current_epoch_contract as ce
import smart_engineering_activation as ea
import smart_regression_evidence as re

root=Path(__file__).resolve().parents[1]
canonical=root/'SMART_PRE_GENERATION_INTEGRITY_3055.json'
v2=json.loads(canonical.read_text(encoding='utf-8-sig'))
v2_file_hash=re.sha256_file(canonical)
archive=root/'SMART_STATE_ARCHIVE'/f'pre_generation_integrity_3055_v2_{v2_file_hash}.json'
archive.parent.mkdir(parents=True,exist_ok=True)
if not archive.exists(): shutil.copy2(canonical,archive)
if re.sha256_file(archive)!=v2_file_hash: raise RuntimeError('V2 archive hash mismatch')
active=lr.verify_active_epoch(root/'SMART_ACTIVE_EPOCH.json')
ctx=ce.resolve(root)
red=rt.verify_latest_report(root/'SMART_P09_RED_TEAM_LATEST.json',root=root)
activation=json.loads((root/'SMART_FULL_ACTIVATION_EPOCH.json').read_text(encoding='utf-8-sig'))
fp=ea._code_fingerprint(root)
reg=re.junit_summary(root/'SMART_AUDIT_JUNIT_CURRENT.xml')
paths=active['state_paths']
ledger=json.loads((root/paths['ledger']).read_text(encoding='utf-8-sig'))
rollback={
 'epoch_reset_ready':active.get('status')=='RESET_READY',
 'ledger_zero_events':len(ledger.get('events',[]))==0,
 'state_absent':not (root/paths['state']).exists(),
 'activation_authority_absent':not (root/paths['activation_authority']).exists(),
 'expansion_registry_absent':not (root/paths['expansion_registry']).exists(),
 'freeze_absent':not (root/paths['freeze']).exists(),
 'freeze_authority_absent':active.get('freeze_authority') is None,
}
checks=dict(v2.get('checks',{}))
checks.update({
 'continuous_red_team_fresh':red.get('status')=='PASS' and red.get('behavioral_hashes_current') is True and red.get('self_hash_valid') is True and red.get('scenario_count')==10,
 'failed_freeze_attempt_rolled_back_cleanly':all(rollback.values()),
 'regression_still_676_green':reg.get('status')=='PASS' and reg.get('tests')==676 and reg.get('failures')==0 and reg.get('errors')==0,
 'code_fingerprint_still_current_after_red_team':fp.get('sha256')==activation.get('code_fingerprint',{}).get('sha256'),
 'context_still_3055_3054':ctx.get('target_contest')==3055 and ctx.get('cutoff_contest')==3054 and ctx.get('result_used') is False,
})
report={
 'schema':'SMART_PRE_GENERATION_INTEGRITY_3055_V3',
 'status':'PASS' if all(checks.values()) else 'FAIL',
 'target_contest':3055,'cutoff_contest':3054,
 'supersedes_schema':v2.get('schema'),
 'supersedes_report_sha256':v2.get('sha256'),
 'supersedes_file_sha256':v2_file_hash,
 'supersession_reason':'ADDED_CONTINUOUS_RED_TEAM_FRESHNESS_GATE_AFTER_CANONICAL_PIPELINE_FAIL_CLOSED',
 'v2_archive_file':str(archive.relative_to(root)).replace('\\','/'),
 'active_epoch_id':active['epoch_id'],'active_epoch_sha256':active['sha256'],
 'data_file':ctx['data_file'],'data_sha256':ctx['data_sha256'],
 'checks':checks,'rollback_proof':rollback,
 'continuous_red_team':red,
 'regression':reg,
 'code_fingerprint_sha256':fp['sha256'],
 'generation_authorized':all(checks.values()),
 'freeze_created':False,'numbers_generated':False,
}
report['sha256']=hashlib.sha256(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
canonical.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':report['status'],'generation_authorized':report['generation_authorized'],'schema':report['schema'],'report_sha256':report['sha256'],'red_team':red,'rollback':rollback,'v2_archive':report['v2_archive_file']},ensure_ascii=False,indent=2))
