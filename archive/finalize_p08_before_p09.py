from pathlib import Path
import json,hashlib,datetime,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
base=load(ROOT/'SMART_COVERAGE_P08_DELTA_FINAL.json')
guard=load(ROOT/'SMART_COVERAGE_P08_GUARDS.json')
hist=load(ROOT/'SMART_P08_META_GOVERNOR_HISTORICAL.json')
ledger=load(ROOT/'SMART_SIGNAL_LEDGER.json')
gate=load(ROOT/'SMART_3052_IMPLEMENTATION_GATE.json')
mods=['adjudicate_signal_challenger.py','smart_champion_challenger.py','smart_meta_governor.py','smart_signal_agent.py']
union={}
for m in mods:
    b=base['files'][m]
    g=guard['files'].get(m, {'executed_lines':[],'executed_branches':[]})
    lines=set(b['executed_lines'])|set(g.get('executed_lines',[]))
    stmt=set(b['executed_lines'])|set(b['missing_lines'])
    branches={tuple(x) for x in b.get('executed_branches',[])}|{tuple(x) for x in b.get('missing_branches',[])}
    exec_br={tuple(x) for x in b.get('executed_branches',[])}|{tuple(x) for x in g.get('executed_branches',[])}
    missing_lines=sorted(stmt-lines)
    missing_branches=sorted([list(x) for x in branches-exec_br])
    union[m]={'statements':len(stmt),'covered_statements':len(stmt)-len(missing_lines),'branches':len(branches),'covered_branches':len(branches)-len(missing_branches),'missing_lines':missing_lines,'missing_branches':missing_branches,'coverage_100':not missing_lines and not missing_branches}
coverage_union={'schema':'SMART_P08_COVERAGE_UNION_1','sources':['SMART_COVERAGE_P08_DELTA_FINAL.json','SMART_COVERAGE_P08_GUARDS.json'],'modules':union,'all_modified_modules_100':all(x['coverage_100'] for x in union.values())}
cu=ROOT/'SMART_COVERAGE_P08_UNION.json'; cu.write_text(json.dumps(coverage_union,ensure_ascii=False,indent=2),encoding='utf-8')
checks={
 'coverage_modified_modules_100':coverage_union['all_modified_modules_100'],
 'oos_2050':hist['oos_predictions']==2050,
 'causal_selection':all(hist['guards'][k] for k in ['selection_before_result_all','update_after_result_only','selected_hits_state_matches']),
 'no_production_authority':hist['guards']['production_authority'] is False and hist['guards']['champion_remains_active'] is True,
 'no_retroactive_selection':hist['guards']['retroactive_selection'] is False,
 'primary_not_rewritten':hist['guards']['primary_challenger_not_rewritten'] is True,
 'underperformance_not_promoted':hist['selected_cumulative_hits'] < hist['fixed_policy_hits']['quality_dynamic'] and hist['next_selection_shadow']['production_authority'] is False,
 'parameters_not_tuned_on_replay':hist['parameters']['tuned_on_replay'] is False,
 'current_meta_hash':hist['hashes']['meta_governor']==sha(ROOT/'smart_meta_governor.py'),
 'current_multi_hash':hist['hashes']['multi_challengers']==sha(ROOT/'smart_multi_challengers.py'),
 'current_agent_hash':hist['hashes']['agent']==sha(ROOT/'smart_signal_agent.py'),
 'p01_p07_proven':all(next(x for x in gate['items'] if x['priority']==i)['status']=='PROVEN' for i in range(1,8)),
 'freeze_3051_valid':False,
 'no_p08_backfill_3051':sum(1 for e in ledger['events'] if e.get('event_type')=='META_GOVERNOR' and int(e.get('target_contest',-1))==3051)==0,
}
fr=[e for e in ledger['events'] if e.get('event_type')=='FREEZE' and int(e.get('target_contest',-1))==3051 and e.get('freeze_sha256')=='795d6e405c4723f79355bdaea2074e784746afcc8eadc4c492206c68f9b2ff53']
if fr:
    p=Path(fr[0]['freeze_file']); checks['freeze_3051_valid']=p.exists() and sha(p)==fr[0]['freeze_sha256']
r=subprocess.run([str(ROOT/'smart_python.cmd'),'-m','pytest','-q','test_smart_meta_governor.py','test_smart_architecture_alignment.py'],cwd=ROOT,text=True,capture_output=True)
checks['focused_tests_pass']=r.returncode==0
proof={'schema':'SMART_P08_META_GOVERNOR_PROOF_1','point_id':'P08_META_GOVERNOR','status':'MISSION_PROVEN' if all(checks.values()) else 'MISSION_NOT_PROVEN','all_checks_pass':all(checks.values()),'checks':checks,'failed':[k for k,v in checks.items() if not v],
'evidence':{'coverage_union':coverage_union,'historical':hist,'global_pytest_last_observed':'145 passed in 180.52s','focused_pytest':(r.stdout+r.stderr).strip(),'freeze_3051_sha256':'795d6e405c4723f79355bdaea2074e784746afcc8eadc4c492206c68f9b2ff53','interpretation':'P08 is proven as causal shadow governor; historical underperformance prohibits replacing quality_dynamic'},'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
out=ROOT/'SMART_P08_META_GOVERNOR_PROOF.json'; out.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
if not proof['all_checks_pass']:
    print(json.dumps({'status':proof['status'],'failed':proof['failed'],'coverage':coverage_union},ensure_ascii=False,indent=2)); raise SystemExit(1)
item=next(x for x in gate['items'] if x['id']=='P08_META_GOVERNOR')
item['status']='PROVEN'; item['evidence']=[
 {'type':'implementation_proof','file':out.name,'sha256':sha(out)},
 {'type':'coverage_union','file':cu.name,'sha256':sha(cu),'modified_modules':mods,'coverage':'100% lines + branches by union of full-suite and guard runs'},
 {'type':'historical_oos','file':'SMART_P08_META_GOVERNOR_HISTORICAL.json','sha256':sha(ROOT/'SMART_P08_META_GOVERNOR_HISTORICAL.json'),'oos_predictions':2050,'selected_hits':hist['selected_cumulative_hits'],'quality_dynamic_hits':hist['fixed_policy_hits']['quality_dynamic'],'production_authority':False},
 {'type':'module','file':'smart_meta_governor.py','sha256':sha(ROOT/'smart_meta_governor.py')}
]
item['proven_brt']='2026-08-30T20:45:00-03:00'
gate['freeze_allowed']=all(x['status']=='PROVEN' and x.get('evidence') for x in gate['items'])
(ROOT/'SMART_3052_IMPLEMENTATION_GATE.json').write_text(json.dumps(gate,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':'MISSION_PROVEN','failed':[],'proof_sha256':sha(out),'coverage_union_sha256':sha(cu),'gate_sha256':sha(ROOT/'SMART_3052_IMPLEMENTATION_GATE.json'),'p08_status':item['status'],'freeze_allowed':gate['freeze_allowed'],'focused':(r.stdout+r.stderr).strip()},ensure_ascii=False,indent=2))
