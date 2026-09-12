from pathlib import Path
import json, hashlib, shutil
from datetime import datetime, timezone
import sys
sys.path.insert(0, str(Path.cwd()))
import smart_material_deficiency_registry as mdr

root=Path.cwd()
active_path=root/'SMART_ACTIVE_EPOCH.json'
active=json.loads(active_path.read_text(encoding='utf-8'))
freeze_rel=active['freeze_authority']['file']
freeze_path=root/freeze_rel
freeze=json.loads(freeze_path.read_text(encoding='utf-8'))
schedule=active['prospective_registration']['schedule_authority']

def sha_file(p:Path):
    h=hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()

def sha_json(v):
    raw=json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

active_sha=sha_file(active_path)
freeze_sha=sha_file(freeze_path)
qdir=root/'runtime'/'quarantine'/f'temporal_invalid_3054_{freeze_sha[:16]}'
qdir.mkdir(parents=True,exist_ok=True)
shutil.copy2(active_path,qdir/'SMART_ACTIVE_EPOCH.invalid.json')
shutil.copy2(freeze_path,qdir/freeze_path.name)
ledger_path=root/active['state_paths']['ledger']
if ledger_path.is_file(): shutil.copy2(ledger_path,qdir/ledger_path.name)
full_proof=ledger_path.parent/'FULL_PROCESS_PROOF.json'
if full_proof.is_file(): shutil.copy2(full_proof,qdir/full_proof.name)
manifest={
  'schema':'SMART_TEMPORAL_AUTHORITY_REVOCATION_1',
  'status':'REVOKED_INVALID_TEMPORAL_AUTHORITY',
  'target_contest':3054,
  'cutoff_contest':3053,
  'scheduled_datetime':schedule['scheduled_datetime'],
  'invalid_freeze_utc':freeze['frozen_utc'],
  'invalid_freeze_sha256':freeze_sha,
  'invalid_active_epoch_sha256':active_sha,
  'reason':'freeze timestamp is not strictly before the official scheduled draw; prospective authority revoked',
  'result_used':False,
  'prospective_authority_valid':False,
  'scientific_use':'CAUSAL_SHADOW_DIAGNOSTIC_ONLY',
  'revoked_at_utc':datetime.now(timezone.utc).isoformat(),
}
manifest['sha256']=sha_json(manifest)
(qdir/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(root/'SMART_TEMPORAL_AUTHORITY_REVOCATION_3054.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# Remove only the root authority pointer. Epoch artifacts stay preserved in their original directory and quarantine.
active_path.unlink()

# Register D009 as resolved with executable evidence.
reg=json.loads((root/'SMART_MATERIAL_DEFICIENCY_REGISTRY.json').read_text(encoding='utf-8'))
entries=list(reg['entries'])
if not any(e.get('id')=='D009_RETROSPECTIVE_FREEZE_AUTHORITY' for e in entries):
    entries.append({
      'id':'D009_RETROSPECTIVE_FREEZE_AUTHORITY',
      'severity':'P0',
      'status':'RESOLVED',
      'summary':'Canonical full-process freeze could claim frozen_before_result after the official scheduled draw because the target schedule timestamp was resolved but not enforced before freeze authority creation.',
      'evidence':[
        'test_smart_procedural_actionability_gate.py::test_freeze_window_exact_draw_time_rejected',
        'test_smart_procedural_actionability_gate.py::test_freeze_window_after_draw_rejected',
        'test_smart_full_process_temporal_guard.py::test_full_process_blocks_after_deadline_before_any_freeze',
        'SMART_TEMPORAL_AUTHORITY_REVOCATION_3054.json'
      ]
    })
newreg=mdr.build_registry(entries)
(root/'SMART_MATERIAL_DEFICIENCY_REGISTRY.json').write_text(json.dumps(newreg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
loaded=mdr.load_registry(root/'SMART_MATERIAL_DEFICIENCY_REGISTRY.json',root=root)
print('QUARANTINE',qdir)
print('REVOKED_FREEZE_SHA',freeze_sha)
print('ACTIVE_EXISTS',active_path.exists())
print('REGISTRY_SHA',loaded['sha256'])
print('OPEN', [e['id'] for e in loaded['entries'] if e['status'] in loaded['rules']['open_statuses']])
