from __future__ import annotations
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''): h.update(b)
 return h.hexdigest()

def events_for(j,t): return [e for e in j.get('events',[]) if int(e.get('target_contest',-1))==t]

signal=json.loads(Path('SMART_SIGNAL_LEDGER.json').read_text(encoding='utf-8'))
legacy=json.loads(Path('SMART_PROSPECTIVE_LEDGER.json').read_text(encoding='utf-8'))
audit=json.loads(Path('SMART_P14_INDEPENDENT_AUDIT_CURRENT.json').read_text(encoding='utf-8'))
summary={}
for t in range(3051,3055):
 es=events_for(signal,t); summary[str(t)]={'event_types':[e.get('event_type') for e in es], 'active_or_latest_freeze_hash': next((e.get('freeze_sha256') for e in reversed(es) if e.get('event_type')=='FREEZE'),None), 'adjudicated':any(e.get('event_type')=='ADJUDICATION' for e in es), 'sequential_proof':any(e.get('event_type')=='SEQUENTIAL_PROOF' for e in es)}
obj={'schema':'SMART_PROSPECTIVE_EVIDENCE_AUTHORITY_V1','created_brasilia':datetime.now(timezone(timedelta(hours=-3))).isoformat(),
 'canonical_sequential_ledger':'SMART_SIGNAL_LEDGER.json','canonical_sequential_ledger_sha256':sha('SMART_SIGNAL_LEDGER.json'),'canonical_schema':signal.get('schema'),
 'legacy_ledger':'SMART_PROSPECTIVE_LEDGER.json','legacy_ledger_sha256':sha('SMART_PROSPECTIVE_LEDGER.json'),'legacy_role':'COMPATIBILITY_ONLY_NON_AUTHORITATIVE_FOR_CURRENT_SEQUENTIAL_PROOF',
 'targets':summary,
 'independent_audit':{'file':'SMART_P14_INDEPENDENT_AUDIT_CURRENT.json','sha256':sha('SMART_P14_INDEPENDENT_AUDIT_CURRENT.json'),'status':audit.get('prospective_ledger',{}).get('status'),'pair_count':audit.get('prospective_ledger',{}).get('pair_count'),'no_future_leakage':audit.get('prospective_ledger',{}).get('no_future_leakage'),'hash_integrity':audit.get('prospective_ledger',{}).get('hash_integrity'),'e_process_recomputed':audit.get('prospective_ledger',{}).get('e_process_recomputed')},
 'policy':{'retroactive_legacy_backfill_prohibited':True,'all_future_freeze_adjudication_learning_proof_events_go_to_canonical_signal_ledger':True,'legacy_records_do_not_create_promotion_evidence':True}}
Path('SMART_PROSPECTIVE_EVIDENCE_AUTHORITY.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'canonical_events':len(signal['events']),'legacy_records':len(legacy.get('records',[])),'p14_pairs':obj['independent_audit']['pair_count'],'3054_adjudicated':summary['3054']['adjudicated']}))
