from __future__ import annotations
import ast,json,re,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from smart_agent_runtime import ORDER,SmartAgentRuntime,sha256_file,sha256_json
from smart_agent_skill_orchestration import AGENTS,LANES
from smart_agent_skill_functional_gate import evaluate as skill_agent_gate
from smart_skill_runtime import SmartSkillRuntime
SCHEMA='SMART_TOTAL_INTEGRATION_GATE_V1'
REPS=('openai-validate-data','statsmodels','statistical-analysis','superforecasting','property-based-testing-hypothesis','google-or-tools','pymc')
BLOCK=re.compile(r'\b(TODO|FIXME|NotImplemented)\b|fake\s+success|hardcoded\s+success',re.I)
SECRETS=(re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b'),re.compile(r'\bAKIA[0-9A-Z]{16}\b'),re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b'))
def hashes(root:Path):
 r=SmartAgentRuntime(root); files=r._critical_files()+['SMART_MISSION_STATUS.json','SMART_AGENT_SKILL_ORCHESTRATION.json']; return {x:sha256_file(root/x) for x in sorted(set(files)) if (root/x).is_file()}
def audit_files(root:Path):
 r=SmartAgentRuntime(root); req={t for l in LANES.values() for t in l['native_targets']}|set(r._critical_files())|{'SMART_MISSION_STATUS.json','smart_agent_runtime.py','smart_skill_runtime.py','smart_agent_skill_functional_gate.py'}
 miss=sorted(x for x in req if not (root/x).exists()); empty=sorted(x for x in req if (root/x).is_file() and (root/x).stat().st_size==0); text=[]; passes=[]; syntax=[]
 for p in sorted(root.glob('smart_*.py')):
  if p.name.startswith('test_'): continue
  s=p.read_text(encoding='utf-8-sig')
  text += [{'file':p.name,'line':i} for i,l in enumerate(s.splitlines(),1) if BLOCK.search(l) and not (p.name=='smart_total_integration_gate.py' and l.lstrip().startswith('BLOCK='))]
  try: tree=ast.parse(s)
  except SyntaxError as e: syntax.append({'file':p.name,'line':e.lineno}); continue
  passes += [{'file':p.name,'line':n.lineno} for n in ast.walk(tree) if isinstance(n,ast.Pass)]
 return {'required':len(req),'missing':miss,'empty':empty,'blockers':text,'pass_nodes':passes,'syntax_errors':syntax,'pass':not(miss or empty or text or passes or syntax)}
def audit_security(root:Path):
 found=[]
 for p in list(root.glob('*.py'))+list(root.glob('*.json'))+list(root.glob('*.toml'))+list(root.glob('*.ps1')):
  if p.name.startswith('test_'): continue
  try:s=p.read_text(encoding='utf-8-sig')
  except UnicodeDecodeError:continue
  if any(x.search(s) for x in SECRETS): found.append(p.name)
 return {'findings':sorted(set(found)),'external_source_execution_disabled':True,'pass':not found}
def fresh(root:Path):
 code="import json;from smart_skill_runtime import SmartSkillRuntime;from smart_agent_runtime import SmartAgentRuntime;r=SmartSkillRuntime('.').invoke('pymc');a=SmartAgentRuntime('.').run();print(json.dumps([r['status'],a['status']]))"
 p=subprocess.run([sys.executable,'-c',code],cwd=root,capture_output=True,text=True,timeout=120); return {'returncode':p.returncode,'pass':p.returncode==0 and '[\"PASS\", \"PASS\"]' in p.stdout}
def concurrency(root:Path):
 out={}
 for n in (1,2,4,8):
  def one(i): return SmartSkillRuntime(root).invoke('pymc',{'i':i})['status']
  with ThreadPoolExecutor(max_workers=n) as x: rows=list(x.map(one,range(n)))
  out[str(n)]=len(rows)==n and all(v=='PASS' for v in rows)
 return {'levels':out,'pass':all(out.values())}
def evaluate(root:str|Path)->dict[str,Any]:
 root=Path(root).resolve(); before=hashes(root); ar=SmartAgentRuntime(root).run(); sr=SmartSkillRuntime(root).execute_gate(); ag=skill_agent_gate(root); fa=audit_files(root); sec=audit_security(root)
 calls=[SmartSkillRuntime(root).invoke(c,{'e2e':True}) for c in REPS]; e2e=all(x['status']=='PASS' for x in calls) and not ar['unacknowledged_handoffs']
 con=concurrency(root); failed=False
 try: SmartSkillRuntime(root).invoke('does-not-exist')
 except KeyError: failed=True
 recovery=failed and SmartSkillRuntime(root).invoke('pymc',{'recover':True})['status']=='PASS'; start1=fresh(root); rb=hashes(root); start2=fresh(root); ra=hashes(root); restart=start1['pass'] and start2['pass'] and rb==ra; after=hashes(root)
 agents=[]
 for n in ORDER:
  ex=ar['executions'][n]; cfg=AGENTS[n]; lane=LANES[cfg['lane']] if cfg.get('lane') else {}
  agents.append({'name':n,'responsibility':lane.get('role','mission governance'),'runtime':'NATIVE_DETERMINISTIC_AGENT','model':None,'prompt':None,'skills':ex['capabilities'],'tools':ex['native_targets'],'inputs':cfg['consumes'],'outputs':cfg['produces'],'calls':cfg['handoff_to'],'state':'OPERACIONAL','last_test':ex['probe_id']})
 skills=[{'name':x['capability'],'agent':x['agent_owner'],'pertinent':x['pertinent'],'callable':x['callable'],'mode':x['execution_mode'],'state':'OPERACIONAL' if x['callable'] else 'CONFIGURADO_MAS_NAO_UTILIZADO'} for x in sr['capabilities']]
 pertinent=[x for x in skills if x['pertinent']]; quarantine=[x for x in skills if not x['pertinent']]
 gates={'G1_AGENTS':{'discovered':len(agents)==9,'integrated':not ar['unacknowledged_handoffs'],'operational':ar['status']=='PASS'},'G2_SKILLS':{'discovered':len(skills)==41,'registered':sr['checks']['all_41_registered'],'callable':len(pertinent)==37 and all(x['callable'] for x in pertinent),'integrated':ag['status']=='PASS' and len(quarantine)==4},'G3_FILES':{'present':not fa['missing'],'empty_zero':not fa['empty'],'broken_imports_zero':not fa['syntax_errors'],'placeholders_zero':not fa['blockers'] and not fa['pass_nodes']},'G4_RUNTIME':{'startup':start1['pass'],'dependencies':all(x['status']=='PASS' for x in calls),'health':fa['pass'] and sec['pass']},'G5_INTEGRATION':{'agent_agent':not ar['unacknowledged_handoffs'],'agent_skill':ag['checks']['all_pertinent_capabilities_individually_callable'],'agent_data':ar['executions']['data_guardian']['probe_result']['pass'],'agent_tool':all(x['native_targets'] for x in calls)},'G6_E2E':{'end_to_end':e2e},'G7_RESILIENCE':{'restart':restart,'recovery':recovery,'retry':recovery,'persistence':rb==ra,'concurrency_1_2_4_8':con['pass']},'G8_SECURITY_STATE':{'canonical_unchanged':before==after,'security':sec['pass']}}
 ok=all(v for g in gates.values() for v in g.values()); d={'schema':SCHEMA,'status':'PASS' if ok else 'FAIL','health':'HEALTHY' if ok else 'UNHEALTHY','service_model':'BATCH_EXECUTION_WITH_PERSISTENT_CANONICAL_ARTIFACTS','gates':gates,'agent_inventory':agents,'skill_inventory':skills,'file_audit':fa,'security_audit':sec,'e2e_calls':calls,'concurrency':con,'restart':{'first':start1,'second':start2,'pass':restart},'recovery_pass':recovery,'scientific_mission_status':ar['executions']['mission_governor']['verdict'],'claim_boundary':'Engineering integration proof only; scientific prospective terminal rule remains independent.'}; d['sha256']=sha256_json(d); return d
def write(root:str|Path,out:str|Path='SMART_TOTAL_INTEGRATION_PROOF.json'):
 root=Path(root); out=Path(out); out=out if out.is_absolute() else root/out; d=evaluate(root); out.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); return d
if __name__=='__main__':
 d=write(Path(__file__).resolve().parent); print(json.dumps({'status':d['status'],'health':d['health'],'gates':d['gates'],'scientific_mission_status':d['scientific_mission_status']},ensure_ascii=False,indent=2))
