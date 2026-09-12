import json
r=json.load(open('SMART_COVERAGE_GLOBAL_CURRENT.json',encoding='utf-8'))
for k in ['smart_agent_runtime.py','smart_agent_skill_functional_gate.py','smart_agent_skill_orchestration.py','smart_continuous_red_team.py','smart_independent_oracle.py']:
 f=r['files'][k]
 print('\n###',k)
 print('missing_lines',f.get('missing_lines'))
 print('missing_branches',f.get('missing_branches'))
