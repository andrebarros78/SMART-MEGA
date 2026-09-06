from pathlib import Path
import subprocess, os, shutil, hashlib, json, tempfile, time, sys, ast, re
from datetime import datetime, timezone

ROOT=Path(r'C:\New Projet\SMART-MEGA')
TMP=Path(r'C:\Windows\Temp\SMART-MEGA-VALIDATION-CURRENT')
LOG=ROOT/'SMART_MISSION_CLOSURE_LOG_20260905.txt'
PROOF=ROOT/'SMART_AUDIT_SECURITY_CLOSURE_20260905.json'

def emit(msg):
    line=f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    with LOG.open('a',encoding='utf-8') as f: f.write(line+'\n')

def sha_file(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def code_rows(root):
    files=sorted(set(root.glob('smart_*.py'))|set(root.glob('test_*.py')))
    for n in ('requirements.txt','requirements.lock.txt','smart_python.cmd'):
        p=root/n
        if p.is_file(): files.append(p)
    files=sorted(set(files), key=lambda p:p.name.lower())
    return [{'path':p.name,'sha256':sha_file(p)} for p in files]

def code_fp(root):
    rows=code_rows(root)
    raw=json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return {'file_count':len(rows),'sha256':hashlib.sha256(raw).hexdigest(),'files':rows}

def run(cmd,cwd=None,env=None,timeout=1800,ok=(0,),label='cmd'):
    emit(f'START {label}')
    cp=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,timeout=timeout)
    out=cp.stdout or ''
    tail='\n'.join(out.splitlines()[-30:])
    if tail: emit(f'OUTPUT {label}\n{tail}')
    if cp.returncode not in ok:
        raise RuntimeError(f'{label} rc={cp.returncode}')
    emit(f'PASS {label}')
    return cp

def copy_snapshot():
    if TMP.exists():
        subprocess.run(['cmd','/c','rmdir','/s','/q',str(TMP)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    TMP.mkdir(parents=True,exist_ok=True)
    cp=subprocess.run(['robocopy',str(ROOT),str(TMP),'/MIR','/R:1','/W:1','/XD','.git','.venv','__pycache__','.pytest_cache','.ruff_cache','/XF','*.pyc','.smart_regression.lock','/NFL','/NDL','/NJH','/NJS','/NP'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if cp.returncode>7:
        raise RuntimeError(f'robocopy failed rc={cp.returncode}: {cp.stdout[-2000:]}')
    subprocess.run(['cmd','/c','mklink','/J',str(TMP/'.venv'),str(ROOT/'.venv')],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=True)

def scan_security(root):
    findings=[]
    for p in sorted(root.glob('smart_*.py')):
        src=p.read_text(encoding='utf-8-sig',errors='replace')
        try: tree=ast.parse(src,filename=str(p))
        except SyntaxError as e:
            findings.append({'file':p.name,'kind':'syntax','line':e.lineno}); continue
        for n in ast.walk(tree):
            if isinstance(n,ast.Call):
                fn=n.func
                name=''
                if isinstance(fn,ast.Name): name=fn.id
                elif isinstance(fn,ast.Attribute):
                    parts=[]; x=fn
                    while isinstance(x,ast.Attribute): parts.append(x.attr); x=x.value
                    if isinstance(x,ast.Name): parts.append(x.id)
                    name='.'.join(reversed(parts))
                if name in {'eval','exec','os.system'}:
                    findings.append({'file':p.name,'kind':name,'line':getattr(n,'lineno',None)})
                if name.startswith('subprocess.'):
                    for kw in n.keywords:
                        if kw.arg=='shell' and isinstance(kw.value,ast.Constant) and kw.value.value is True:
                            findings.append({'file':p.name,'kind':'subprocess_shell_true','line':getattr(n,'lineno',None)})
                if name.startswith('requests.') and name.split('.')[-1] in {'get','post','put','patch','delete','request'}:
                    if not any(k.arg=='timeout' for k in n.keywords):
                        findings.append({'file':p.name,'kind':'requests_without_timeout','line':getattr(n,'lineno',None)})
                if name=='yaml.load': findings.append({'file':p.name,'kind':'yaml_load','line':getattr(n,'lineno',None)})
                if name.startswith('pickle.') and name.split('.')[-1] in {'load','loads'}: findings.append({'file':p.name,'kind':'pickle_load','line':getattr(n,'lineno',None)})
        if re.search(r'(?i)-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',src): findings.append({'file':p.name,'kind':'private_key_literal'})
    return findings

def parse_junit(path):
    import xml.etree.ElementTree as ET
    r=ET.parse(path).getroot()
    def iv(k):
        try:return int(r.attrib.get(k,0))
        except:return 0
    return {'tests':iv('tests'),'failures':iv('failures'),'errors':iv('errors'),'skipped':iv('skipped'),'time':r.attrib.get('time')}

def py_env(worktree):
    e=os.environ.copy(); e['PYTHONPATH']=''; e['GIT_DIR']=str(ROOT/'.git'); e['GIT_WORK_TREE']=str(worktree); return e

def project_py(root): return str(root/'.venv'/'Scripts'/'python.exe')

# 1) Stable immutable validation, retry automatically if live code changes.
stable=None
for attempt in range(1,4):
    emit(f'VALIDATION_ATTEMPT {attempt}')
    before=code_fp(ROOT)
    copy_snapshot()
    snap=code_fp(TMP)
    if before['sha256']!=snap['sha256']: raise RuntimeError('snapshot fingerprint mismatch at creation')
    env=py_env(TMP); py=project_py(TMP)
    compile_targets=[p.name for p in sorted(TMP.glob('smart_*.py'))]+[p.name for p in sorted(TMP.glob('test_*.py'))]; run([py,'-E','-m','py_compile',*compile_targets],cwd=TMP,env=env,timeout=600,label='compileall_snapshot')
    run([py,'-E','-m','pip','check'],cwd=TMP,env=env,timeout=180,label='pip_check_snapshot')
    sec=scan_security(TMP)
    if sec: raise RuntimeError('security static findings: '+json.dumps(sec,ensure_ascii=False))
    emit('PASS security_static_scan')
    import xml.etree.ElementTree as ET
    parts=TMP/'.audit_parts'
    if parts.exists(): shutil.rmtree(parts,ignore_errors=True)
    parts.mkdir()
    totals={'tests':0,'failures':0,'errors':0,'skipped':0,'time':0.0}
    merged=ET.Element('testsuites')
    test_files=sorted(TMP.glob('test_*.py'))
    for idx,tp in enumerate(test_files):
        part=parts/f'{idx:03d}_{tp.stem}.xml'
        run([py,'-E','-m','pytest','-q',tp.name,f'--junitxml={part}'],cwd=TMP,env=env,timeout=240,label=f'pytest_{idx+1:02d}_{len(test_files):02d}_{tp.name}')
        sj=parse_junit(part)
        for key in ('tests','failures','errors','skipped'): totals[key]+=int(sj[key])
        try: totals['time']+=float(sj.get('time') or 0.0)
        except Exception: pass
        pr=ET.parse(part).getroot()
        if pr.tag=='testsuites':
            for child in list(pr): merged.append(child)
        elif pr.tag=='testsuite': merged.append(pr)
    for key in ('tests','failures','errors','skipped'): merged.set(key,str(totals[key]))
    merged.set('time',str(round(totals['time'],6)))
    cand=TMP/'SMART_AUDIT_JUNIT_CANDIDATE.xml'
    ET.ElementTree(merged).write(cand,encoding='utf-8',xml_declaration=True)
    js={**totals,'time':str(round(totals['time'],6))}
    if js['failures'] or js['errors'] or js['tests']<=0: raise RuntimeError('invalid junit '+json.dumps(js))
    after=code_fp(ROOT)
    if after['sha256']!=before['sha256']:
        emit('LIVE_CODE_CHANGED_DURING_VALIDATION -> RETRY')
        continue
    stable={'fingerprint':after,'junit':js,'candidate':cand,'security_findings':sec}
    break
if stable is None: raise RuntimeError('unable to obtain stable live code across 3 validation attempts')

# Promote regression evidence atomically only after stable code proof.
current=ROOT/'SMART_AUDIT_JUNIT_CURRENT.xml'; tmpcur=ROOT/'SMART_AUDIT_JUNIT_CURRENT.xml.tmp'
shutil.copy2(stable['candidate'],tmpcur); os.replace(tmpcur,current)
emit(f"PROMOTED regression tests={stable['junit']['tests']} sha={sha_file(current)}")

# 2) Fresh engineering activation if current activation fingerprint is stale.
live_py=project_py(ROOT); env_live=py_env(ROOT)
activation_path=ROOT/'SMART_FULL_ACTIVATION_EPOCH.json'; active_path=ROOT/'SMART_ACTIVE_EPOCH.json'
needs_activation=True
if activation_path.is_file():
    try:
        a=json.loads(activation_path.read_text(encoding='utf-8'))
        needs_activation=a.get('code_fingerprint',{}).get('sha256')!=stable['fingerprint']['sha256']
    except Exception: needs_activation=True
if needs_activation:
    if active_path.is_file():
        active=json.loads(active_path.read_text(encoding='utf-8'))
        if not (active.get('status')=='RESET_READY' and active.get('freeze_authority') is None and active.get('result_used') is False):
            raise RuntimeError('cannot supersede current active epoch safely')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    arc=ROOT/'archive'/'engineering_activation_epochs'/stamp; arc.mkdir(parents=True,exist_ok=True)
    if activation_path.exists(): os.replace(activation_path,arc/activation_path.name)
    if active_path.exists(): os.replace(active_path,arc/active_path.name)
    (arc/'SUPERSEDED.json').write_text(json.dumps({'reason':'code_changed_after_previous_activation','new_code_fingerprint':stable['fingerprint']['sha256'],'archived_utc':datetime.now(timezone.utc).isoformat()},indent=2),encoding='utf-8')
    emit(f'ARCHIVED stale activation to {arc}')
    run([live_py,'-E','smart_engineering_activation.py'],cwd=ROOT,env=env_live,timeout=900,label='fresh_engineering_activation')
    run([live_py,'-E','smart_learning_epoch_reset.py'],cwd=ROOT,env=env_live,timeout=300,label='fresh_learning_epoch_reset')
else:
    emit('CURRENT engineering activation fingerprint already fresh')

# 3) Verify target still unseen and freeze prospectively.
active=json.loads(active_path.read_text(encoding='utf-8'))
if active.get('status')!='RESET_READY': raise RuntimeError('active epoch is not RESET_READY before freeze')
target=int(active['target_contest']); cutoff=int(active['cutoff_contest'])
check_code=("import requests,json,sys; u='https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/%d'; "
            "r=requests.get(u,timeout=20); print(r.status_code); print(r.text[:500]); "
            "sys.exit(42 if r.status_code==200 else 0)")%target
cp=run([live_py,'-E','-c',check_code],cwd=ROOT,env=env_live,timeout=60,ok=(0,42),label='official_target_presence_check')
if cp.returncode==42: raise RuntimeError(f'official result for target {target} already available; prospective freeze prohibited')
run([live_py,'-E','smart_full_process_pipeline.py'],cwd=ROOT,env=env_live,timeout=2400,label='full_process_freeze')

# 4) Post-freeze contract/security/integration retest.
post_tests=['test_smart_current_epoch_contract.py','test_smart_agent_skill_orchestration.py','test_smart_total_integration_gate.py','test_smart_http_guard.py','test_smart_runtime_guard.py','test_data_integrity.py','test_adjudication_integrity.py','test_supersede_chain_integrity.py']
run([live_py,'-E','-m','pytest','-q',*post_tests],cwd=ROOT,env=env_live,timeout=900,label='post_freeze_regression')
contract_cp=run([live_py,'-E','-c',"import json,smart_current_epoch_contract as c; print(json.dumps(c.resolve(r'C:\\New Projet\\SMART-MEGA'),ensure_ascii=False))"],cwd=ROOT,env=env_live,timeout=120,label='current_epoch_contract')
contract=json.loads(contract_cp.stdout.strip().splitlines()[-1])
if contract.get('status')!='FROZEN' or contract.get('result_used') is not False or not contract.get('freeze_authority_present'):
    raise RuntimeError('post-freeze current epoch contract invalid')

# 5) Final proof. Scientific terminal remains governed by official future adjudication.
mission=json.loads((ROOT/'SMART_MISSION_STATUS.json').read_text(encoding='utf-8'))
proof={
 'schema':'SMART_AUDIT_SECURITY_CLOSURE_1','generated_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS',
 'code_fingerprint':stable['fingerprint'],'full_regression':stable['junit'],'regression_sha256':sha_file(current),
 'security_static_findings':stable['security_findings'],'security_static_pass':True,
 'runtime_dependency_consistency':'PASS','target_contest':target,'cutoff_contest':cutoff,
 'current_epoch_contract':contract,'mission_status':mission.get('status'),'terminal_6of6_proven':mission.get('terminal_6of6_proven'),
 'audit_criteria':{
   'code_integrity':True,'data_and_causality':True,'security_static':True,'dependency_consistency':True,'integration_and_regression':True,'prospective_freeze_integrity':True
 },
 'audit_6of6':True,
 'scientific_terminal_rule_pending_official_adjudication': not bool(mission.get('terminal_6of6_proven')),
}
raw=json.dumps(proof,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(); proof['sha256']=hashlib.sha256(raw).hexdigest()
PROOF.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
emit('AUDIT_6OF6=PASS')
emit(f"FREEZE target={target} top6={contract.get('top6')} sha={contract.get('freeze_sha256')}")
emit(f"FINAL_PROOF={PROOF} sha={proof['sha256']}")
print(json.dumps({'status':'PASS','audit_6of6':True,'tests':stable['junit']['tests'],'target':target,'top6':contract.get('top6'),'freeze_sha256':contract.get('freeze_sha256'),'proof_sha256':proof['sha256'],'mission_status':mission.get('status'),'terminal_6of6_proven':mission.get('terminal_6of6_proven')},ensure_ascii=False))
