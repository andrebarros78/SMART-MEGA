import json,hashlib,pathlib
r=json.load(open('runtime/SMART_GLOBAL_TAG_V620.json',encoding='utf-8-sig'))
for f in ['smart_agent_runtime.py','smart_agent_skill_functional_gate.py','smart_agent_skill_orchestration.py','smart_continuous_red_team.py','smart_independent_oracle.py']:
 cur=hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest(); old=r.get('critical_source_hashes',{}).get(f); print(f'{f}|current={cur}|proof={old}|match={cur==old}')
print('coverage_count',len(r.get('coverage',[])))
