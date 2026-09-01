from __future__ import annotations
import hashlib, json, os, sys
from datetime import datetime
from pathlib import Path
ROOT=Path(r'C:\New Projet\SMART-MEGA'); os.chdir(ROOT); sys.path.insert(0,str(ROOT))
GATE=ROOT/'SMART_3052_IMPLEMENTATION_GATE.json'
P09=ROOT/'SMART_P09_RED_TEAM_LATEST.json'
P14=ROOT/'SMART_P14_INDEPENDENT_AUDIT_CURRENT.json'

def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def jsha(o): return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

g=json.loads(GATE.read_text(encoding='utf-8'))
r=json.loads(P09.read_text(encoding='utf-8'))
a=json.loads(P14.read_text(encoding='utf-8'))
# P09 exact validation
assert r.get('schema')=='SMART_CONTINUOUS_RED_TEAM_1' and r.get('status')=='PASS'
assert r.get('all_checks_pass') is True and r.get('failed')==[]
checks=r.get('checks'); assert isinstance(checks,dict) and checks and all(v is True for v in checks.values())
obs=r.get('sha256'); canon=dict(r); canon.pop('sha256',None); assert isinstance(obs,str) and obs==jsha(canon)
from smart_continuous_red_team import verify_latest_report
vr=verify_latest_report(P09,ROOT); assert vr.get('status')=='PASS'
# P14 exact validation
assert a.get('schema')=='SMART_INDEPENDENT_AUDIT_1' and a.get('status')=='PASS'
obs=a.get('sha256'); canon=dict(a); canon.pop('sha256',None); assert isinstance(obs,str) and obs==jsha(canon)
assert a.get('material_deficiencies')==[] and all(v is True for v in a.get('checks',{}).values())
assert a['prospective_ledger']['status']=='PASS' and a['prospective_ledger']['no_future_leakage'] is True and a['prospective_ledger']['hash_integrity'] is True
assert a['deterministic_replay']['status']=='PASS' and a['deterministic_replay']['deterministic'] is True and a['deterministic_replay']['causal_cutoff_verified'] is True
assert a['independence']['status']=='PASS' and a['independence']['forbidden_dependencies_found']==[]
for row in a['coverage']['bindings']:
 assert row['status']=='PASS' and row['covered_lines']==row['statements'] and row['covered_branches']==row['branches']
now=datetime.now().astimezone().isoformat()
# Write dedicated registration proof before mutating gate
proof={
 'schema':'SMART_P09_P14_GATE_REGISTRATION_PROOF_1','created_brt':now,
 'p09':{'file':P09.name,'file_sha256':sha(P09),'self_sha256':r['sha256'],'verified':True,'all_checks_pass':True,'checks':checks},
 'p14':{'file':P14.name,'file_sha256':sha(P14),'self_sha256':a['sha256'],'verified':True,'material_deficiencies':[],'checks':a['checks'],'coverage_bindings':len(a['coverage']['bindings']),'deterministic':True,'no_future_leakage':True},
}
proofp=ROOT/'SMART_P09_P14_GATE_REGISTRATION_PROOF.json'; proofp.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
# Update only P09/P14; intentionally keep freeze false until P15 is resealed current.
by={x['id']:x for x in g['items']}
by['P09_CONTINUOUS_RED_TEAM']['status']='PROVEN'; by['P09_CONTINUOUS_RED_TEAM']['proven_brt']=now
by['P09_CONTINUOUS_RED_TEAM']['evidence']=[
 {'type':'continuous_red_team','file':P09.name,'sha256':sha(P09),'report_sha256':r['sha256'],'all_checks_pass':True},
 {'type':'registration_proof','file':proofp.name,'sha256':sha(proofp)},
 {'type':'context_regime_module','file':'smart_context_regime.py','sha256':sha(ROOT/'smart_context_regime.py'),'calibration_id':'SMART_CONTEXT_CAL_20260831_C'},
 {'type':'red_team_module','file':'smart_continuous_red_team.py','sha256':sha(ROOT/'smart_continuous_red_team.py')},
]
by['P14_INDEPENDENT_AUDIT_NONREGRESSION']['status']='PROVEN'; by['P14_INDEPENDENT_AUDIT_NONREGRESSION']['proven_brt']=now
by['P14_INDEPENDENT_AUDIT_NONREGRESSION']['evidence']=[
 {'type':'independent_audit','file':P14.name,'sha256':sha(P14),'report_sha256':a['sha256'],'material_deficiencies':[]},
 {'type':'registration_proof','file':proofp.name,'sha256':sha(proofp)},
 *[{'type':'coverage_binding','file':row['binding_file'],'sha256':row['binding_sha256'],'source_file':row['source_file'],'covered_lines':row['covered_lines'],'statements':row['statements'],'covered_branches':row['covered_branches'],'branches':row['branches']} for row in a['coverage']['bindings']],
 {'type':'critical_branch_regression','file':'test_p14_critical_branch_coverage.py','sha256':sha(ROOT/'test_p14_critical_branch_coverage.py')},
]
proven=sum(1 for x in g['items'] if x.get('status')=='PROVEN' and isinstance(x.get('evidence'),list) and x['evidence'])
g['progress']={'proven_items':proven,'total_items':15,'remaining_items':15-proven,'remaining_ids':[x['id'] for x in g['items'] if x.get('status')!='PROVEN' or not x.get('evidence')]}
g['freeze_allowed']=False
g['last_updated_brt']=now; g['updated_brt']=now
GATE.write_text(json.dumps(g,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'p09':'PROVEN','p14':'PROVEN','proven':proven,'freeze_allowed':g['freeze_allowed'],'gate_sha256':sha(GATE),'registration_proof_sha256':sha(proofp)},ensure_ascii=False))


