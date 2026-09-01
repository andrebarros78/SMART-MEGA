from pathlib import Path
import json,hashlib,subprocess,sys,datetime
ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
coverage=load(ROOT/'SMART_COVERAGE_P07_FINAL.json')
hist=load(ROOT/'SMART_P07_MULTI_CHALLENGERS_HISTORICAL.json')
ledger=load(ROOT/'SMART_SIGNAL_LEDGER.json')
gate=load(ROOT/'SMART_3052_IMPLEMENTATION_GATE.json')
summary=coverage['totals']
checks={
 'coverage_100_lines':summary['missing_lines']==0 and summary['covered_lines']==summary['num_statements'],
 'coverage_100_branches':summary['missing_branches']==0 and summary['covered_branches']==summary['num_branches'],
 'five_policies':len(hist['policy_ids'])==5 and len(set(hist['policy_ids']))==5,
 'oos_2050':hist['oos_predictions']==2050,
 'no_selection':hist['selection_performed'] is False and hist['selection_deferred_to_p08'] is True,
 'primary_preserved':hist['primary_top6_preserved'] is True and hist['primary_challenger_total_hits']==1271,
 'current_module_hash':hist['hashes']['module'].lower()==sha(ROOT/'smart_multi_challengers.py'),
 'current_agent_hash':hist['hashes']['agent'].lower()==sha(ROOT/'smart_signal_agent.py'),
 'freeze_3051_valid':False,
 'no_p07_backfill_3051':sum(1 for e in ledger['events'] if e.get('event_type')=='MULTI_CHALLENGERS' and e.get('target_contest')==3051)==0,
 'p01_p06_proven':all(next(x for x in gate['items'] if x['priority']==i)['status']=='PROVEN' for i in range(1,7)),
}
fr=[e for e in ledger['events'] if e.get('event_type')=='FREEZE' and e.get('target_contest')==3051 and e.get('freeze_sha256')=='795d6e405c4723f79355bdaea2074e784746afcc8eadc4c492206c68f9b2ff53']
if fr:
 p=Path(fr[0]['freeze_file']); checks['freeze_3051_valid']=p.exists() and sha(p)==fr[0]['freeze_sha256']
# focused executable proof
r=subprocess.run([str(ROOT/'smart_python.cmd'),'-m','pytest','-q','test_smart_multi_challengers.py','test_smart_architecture_alignment.py'],cwd=ROOT,text=True,capture_output=True)
checks['focused_tests_pass']=r.returncode==0
proof={'schema':'SMART_P07_MULTI_CHALLENGERS_PROOF_1','point_id':'P07_MULTI_CHALLENGERS','status':'MISSION_PROVEN' if all(checks.values()) else 'MISSION_NOT_PROVEN','all_checks_pass':all(checks.values()),'checks':checks,'failed':[k for k,v in checks.items() if not v],
'evidence':{'coverage':{'statements':summary['num_statements'],'branches':summary['num_branches'],'percent':summary['percent_covered']},'historical':hist,'focused_pytest':(r.stdout+r.stderr).strip(),'global_pytest_last_observed':'134 passed in 156.84s','pip_check_last_observed':'No broken requirements found.','module_sha256':sha(ROOT/'smart_multi_challengers.py'),'agent_sha256':sha(ROOT/'smart_signal_agent.py'),'freeze_3051_sha256':'795d6e405c4723f79355bdaea2074e784746afcc8eadc4c492206c68f9b2ff53'},'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
out=ROOT/'SMART_P07_MULTI_CHALLENGERS_PROOF.json'; out.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
if not proof['all_checks_pass']:
 print(json.dumps({'status':proof['status'],'failed':proof['failed']},indent=2)); raise SystemExit(1)
# update gate P07 only
item=next(x for x in gate['items'] if x['id']=='P07_MULTI_CHALLENGERS')
item['status']='PROVEN'; item['evidence']=[
 {'type':'implementation_proof','file':out.name,'sha256':sha(out)},
 {'type':'coverage','file':'SMART_COVERAGE_P07_FINAL.json','sha256':sha(ROOT/'SMART_COVERAGE_P07_FINAL.json'),'statements':summary['num_statements'],'branches':summary['num_branches'],'coverage':'100% critical lines + branches'},
 {'type':'historical_oos','file':'SMART_P07_MULTI_CHALLENGERS_HISTORICAL.json','sha256':sha(ROOT/'SMART_P07_MULTI_CHALLENGERS_HISTORICAL.json'),'oos_predictions':2050,'selection_performed':False},
 {'type':'module','file':'smart_multi_challengers.py','sha256':sha(ROOT/'smart_multi_challengers.py')}
]
item['proven_brt']='2026-08-30T19:59:00-03:00'
gate['freeze_allowed']=all(x['status']=='PROVEN' and x.get('evidence') for x in gate['items'])
(ROOT/'SMART_3052_IMPLEMENTATION_GATE.json').write_text(json.dumps(gate,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':'MISSION_PROVEN','proof_sha256':sha(out),'gate_sha256':sha(ROOT/'SMART_3052_IMPLEMENTATION_GATE.json'),'p07_status':item['status'],'freeze_allowed':gate['freeze_allowed'],'focused':(r.stdout+r.stderr).strip()},ensure_ascii=False,indent=2))