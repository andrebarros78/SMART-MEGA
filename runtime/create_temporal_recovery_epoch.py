from pathlib import Path
import json, shutil, sys
from datetime import datetime, timezone
sys.path.insert(0,str(Path.cwd()))
from smart_learning_epoch_reset import write_active_epoch
from smart_champion_challenger import load_ledger
from smart_agent_runtime import sha256_file

root=Path.cwd()
qdirs=sorted((root/'runtime'/'quarantine').glob('temporal_invalid_3054_*'))
if not qdirs: raise SystemExit('temporal quarantine missing')
q=qdirs[-1]
old=json.loads((q/'SMART_ACTIVE_EPOCH.invalid.json').read_text(encoding='utf-8'))
manifest=json.loads((q/'MANIFEST.json').read_text(encoding='utf-8'))
epoch_id='temporal-recovery-'+manifest['invalid_freeze_sha256'][:12]
epoch_dir=root/'runtime'/'learning_epochs'/epoch_id
if epoch_dir.exists(): shutil.rmtree(epoch_dir)
epoch_dir.mkdir(parents=True)
source=root/old['data_file']
data=epoch_dir/'Mega-Sena_cutoff_3053.xlsx'
shutil.copy2(source,data)
ledger=epoch_dir/'SMART_SIGNAL_LEDGER.json'
fresh=load_ledger(epoch_dir/'__missing__.json')
ledger.write_text(json.dumps(fresh,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
paths={
 'ledger':str(ledger.relative_to(root)).replace('\\','/'),
 'state':str((epoch_dir/'SMART_SIGNAL_STATE.json').relative_to(root)).replace('\\','/'),
 'activation_authority':str((epoch_dir/'SMART_LEARNING_ACTIVATION_AUTHORITY.json').relative_to(root)).replace('\\','/'),
 'expansion_registry':str((epoch_dir/'SMART_SIGNAL_EXPANSION_REGISTRY.json').relative_to(root)).replace('\\','/'),
 'freeze':str((epoch_dir/'SMART_3054_CHAMPION_CHALLENGER_FREEZE.json').relative_to(root)).replace('\\','/'),
}
doc={
 'schema':'SMART_ACTIVE_LEARNING_EPOCH_2','status':'RESET_READY','project':'SMART-MEGA','epoch_id':epoch_id,
 'created_utc':datetime.now(timezone.utc).isoformat(),
 'engineering_activation_file':old['engineering_activation_file'],'engineering_activation_sha256':old['engineering_activation_sha256'],
 'state_paths':paths,'data_file':str(data.relative_to(root)).replace('\\','/'),'data_sha256':sha256_file(data),
 'canonical_source_file':old['canonical_source_file'],'canonical_source_sha256_at_reset':old['canonical_source_sha256_at_reset'],
 'immutable_history_snapshot':True,'cutoff_contest':3053,'target_contest':3054,
 'authority_mode':'TEMPORAL_RECOVERY_STAGING_FAIL_CLOSED','current_engineering_role':'NON_AUTHORITATIVE_RECOVERY_STAGING',
 'first_possible_authoritative_target_for_current_engineering':3055,
 'parallel_locked_experiment':old.get('parallel_locked_experiment'),
 'parallel_attempts_must_be_counted_separately':bool(old.get('parallel_locked_experiment')),
 'prospective_authority_lock_file':old.get('prospective_authority_lock_file'),
 'prospective_authority_lock_sha256':old.get('prospective_authority_lock_sha256'),
 'result_used':False,'freeze_authority':None,'learning_state_authority':None,
 'supersedes_active_epoch_sha256':manifest['invalid_active_epoch_sha256'],
 'temporal_revocation_proof_file':'SMART_TEMPORAL_AUTHORITY_REVOCATION_3054.json',
 'temporal_revocation_proof_sha256':sha256_file(root/'SMART_TEMPORAL_AUTHORITY_REVOCATION_3054.json'),
}
active=write_active_epoch(root/'SMART_ACTIVE_EPOCH.json',doc)
print('ACTIVE_STATUS',active['status'])
print('ACTIVE_SHA',active['sha256'])
print('LEDGER_EVENTS',len(fresh['events']))
print('FREEZE_EXISTS',(root/paths['freeze']).exists())
