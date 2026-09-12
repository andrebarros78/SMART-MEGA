import json,hashlib,subprocess,pathlib
root=pathlib.Path('.')
missing=['smart_agent_runtime.py','smart_agent_skill_functional_gate.py','smart_agent_skill_orchestration.py','smart_continuous_red_team.py','smart_independent_oracle.py']
r=json.load(open('runtime/SMART_COVERAGE_TAG_V620.json',encoding='utf-8-sig'))
print('TAG_KEYS',list(r.get('files',{}).keys()))
for f in missing:
    cur=hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()
    old=subprocess.check_output(['git','show',f'SMART-MEGA-v6.2.0-MISSION-PROVEN:{f}'])
    oldh=hashlib.sha256(old).hexdigest()
    row=r.get('files',{}).get(f)
    if row:
      s=row['summary']; cov=f"{s['covered_lines']}/{s['num_statements']} lines; {s['covered_branches']}/{s['num_branches']} branches; ML={s['missing_lines']} MB={s['missing_branches']}"
    else: cov='NOT_IN_TAG_REPORT'
    print(f'{f}|hash_match={cur==oldh}|cur={cur}|tag={oldh}|cov={cov}')
