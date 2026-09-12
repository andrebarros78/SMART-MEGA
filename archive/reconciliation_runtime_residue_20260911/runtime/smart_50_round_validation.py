from __future__ import annotations
import hashlib, json, math, statistics, sys, time
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import smart_runtime_guard as runtime_guard
import smart_current_epoch_contract as epoch_contract
import smart_prospective_authority_lock as authority_lock
import smart_3054_adjudication_preflight as preflight
import smart_champion_challenger as cc
import smart_agent_runtime as agent_runtime
import smart_total_integration_gate as total_gate
EXPECTED_FREEZE='503dc4e99db017a4c6954709e40ea707878faf1601d9ee690d1ea409d452a816'
REPORT=ROOT/'runtime'/'SMART_50_ROUND_VALIDATION_20260906.json'

def sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
 return h.hexdigest()

def percentile(xs:list[float],q:float)->float:
 if not xs:return 0.0
 ys=sorted(xs); pos=(len(ys)-1)*q; lo=math.floor(pos); hi=math.ceil(pos)
 if lo==hi:return ys[lo]
 return ys[lo]+(ys[hi]-ys[lo])*(pos-lo)

def timed(fn):
 t=time.perf_counter(); value=fn(); return value,time.perf_counter()-t

def compile_architecture():
 files=sorted(ROOT.glob('smart_*.py'))
 errors=[]
 for p in files:
  try: compile(p.read_text(encoding='utf-8-sig'),str(p),'exec')
  except Exception as e: errors.append({'file':p.name,'error':f'{type(e).__name__}: {e}'})
 return {'files':len(files),'errors':errors,'pass':not errors}

def verify_production():
 current=epoch_contract.resolve(ROOT)
 lock=authority_lock.verify_lock(ROOT/'SMART_PROSPECTIVE_AUTHORITY_LOCK.json',root=ROOT)
 pf=preflight.build_preflight(ROOT)
 ledger=cc.load_ledger(ROOT/'SMART_SIGNAL_LEDGER.json')
 active=cc.active_freeze(ledger,3054)
 freeze_path=ROOT/current['freeze_file']
 freeze_hash=sha(freeze_path)
 top6=sorted(int(x) for x in current['top6'])
 lock_exp=lock['experiment_authority']
 checks={
  'epoch_frozen':current['status']=='FROZEN',
  'target_3054_cutoff_3053':current['target_contest']==3054 and current['cutoff_contest']==3053,
  'result_not_used':current['result_used'] is False,
  'carry_forward_mode':current['authority_mode']=='CARRY_FORWARD_UNRESOLVED_PROSPECTIVE',
  'engineering_shadow':current['current_engineering_role']=='SHADOW_ONLY_FOR_LOCKED_TARGET',
  'next_authoritative_3055':current['first_possible_authoritative_target_for_current_engineering']==3055,
  'freeze_hash_exact':freeze_hash==EXPECTED_FREEZE==current['freeze_sha256'],
  'top6_exact':top6==[10,11,27,30,35,38],
  'lock_exact':lock['status']=='LOCKED_UNRESOLVED_PROSPECTIVE' and lock_exp['freeze_sha256']==EXPECTED_FREEZE,
  'lock_forbids_mutation':lock['current_engineering_policy']['may_mutate_locked_freeze'] is False,
  'lock_forbids_retroclaim':lock['current_engineering_policy']['may_claim_generation_of_locked_freeze'] is False,
  'ledger_active_freeze_exact':active is not None and active.get('freeze_sha256')==EXPECTED_FREEZE,
  'preflight_pass':pf.get('readiness_status')=='PASS' and all(pf.get('checks',{}).values()),
  'preflight_carry_forward':pf.get('generation_authority',{}).get('mode')=='CARRY_FORWARD_AUTHORITY_LOCK',
 }
 return {'pass':all(checks.values()),'checks':checks,'preflight_status':pf.get('readiness_status'),'freeze_sha256':freeze_hash,'top6':top6}

rows=[]; heavy=[]; failures=[]
started=datetime.now(timezone.utc).isoformat()
for i in range(1,51):
 row={'round':i,'started_utc':datetime.now(timezone.utc).isoformat(),'checks':{},'timings_s':{}}
 try:
  sysres,dt=timed(lambda:runtime_guard.audit(ROOT)); row['timings_s']['system']=dt
  row['checks']['system']=sysres.get('status')=='PASS' and all(sysres.get('checks',{}).values())
  arch,dt=timed(compile_architecture); row['timings_s']['architecture']=dt
  row['checks']['architecture']=arch['pass']; row['architecture_files']=arch['files']; row['architecture_errors']=arch['errors']
  prod,dt=timed(verify_production); row['timings_s']['production']=dt
  row['checks']['production']=prod['pass']; row['production']=prod
  ar,dt=timed(lambda:agent_runtime.SmartAgentRuntime(ROOT,phase='POST_FREEZE').run()); row['timings_s']['agent_runtime']=dt
  row['checks']['agent_runtime']=ar.get('status')=='PASS'
  if i in (1,10,20,30,40,50):
   tg,dt=timed(lambda:total_gate.evaluate(ROOT,phase='POST_FREEZE'))
   row['timings_s']['heavy_gate']=dt; row['checks']['heavy_gate']=tg.get('status')=='PASS' and tg.get('health')=='HEALTHY' and all(v for g in tg.get('gates',{}).values() for v in g.values())
   heavy.append({'round':i,'status':tg.get('status'),'health':tg.get('health'),'seconds':dt,'sha256':tg.get('sha256')})
  row['total_s']=sum(row['timings_s'].values()); row['pass']=all(row['checks'].values())
 except Exception as e:
  row['pass']=False; row['exception']=f'{type(e).__name__}: {e}'
 rows.append(row)
 if not row['pass']: failures.append({'round':i,'checks':row.get('checks'),'exception':row.get('exception'),'production':row.get('production')})
 if i%5==0 or not row['pass']:
  print(json.dumps({'progress_round':i,'passed':sum(1 for r in rows if r['pass']),'failed':sum(1 for r in rows if not r['pass']),'last_total_s':round(row.get('total_s',0),3)},ensure_ascii=False),flush=True)

totals=[r.get('total_s',0.0) for r in rows]
prod_times=[r.get('timings_s',{}).get('production',0.0) for r in rows]
agent_times=[r.get('timings_s',{}).get('agent_runtime',0.0) for r in rows]
summary={
 'schema':'SMART_50_ROUND_VALIDATION_1','started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),
 'rounds_requested':50,'rounds_executed':len(rows),'rounds_passed':sum(1 for r in rows if r['pass']),'rounds_failed':sum(1 for r in rows if not r['pass']),
 'success_rate':sum(1 for r in rows if r['pass'])/len(rows),
 'production_freeze_sha256':EXPECTED_FREEZE,'production_target':3054,'production_cutoff':3053,'production_result_used':False,
 'heavy_gate_checkpoints':heavy,
 'efficiency':{
  'round_total_p50_s':percentile(totals,.50),'round_total_p95_s':percentile(totals,.95),'round_total_p99_s':percentile(totals,.99),'round_total_mean_s':statistics.fmean(totals),
  'production_p50_s':percentile(prod_times,.50),'production_p95_s':percentile(prod_times,.95),'production_p99_s':percentile(prod_times,.99),
  'agent_runtime_p50_s':percentile(agent_times,.50),'agent_runtime_p95_s':percentile(agent_times,.95),'agent_runtime_p99_s':percentile(agent_times,.99),
 },
 'failures':failures,'rounds':rows,
}
summary['status']='PASS' if summary['rounds_failed']==0 and len(heavy)==6 and all(x['status']=='PASS' and x['health']=='HEALTHY' for x in heavy) else 'FAIL'
REPORT.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ('rounds','failures')},ensure_ascii=False,indent=2),flush=True)
if summary['status']!='PASS': raise SystemExit(1)