import json
r=json.load(open('SMART_COVERAGE_GLOBAL_CURRENT.json',encoding='utf-8'))
for k in ['smart_agent_runtime.py','smart_agent_skill_functional_gate.py','smart_agent_skill_orchestration.py','smart_continuous_red_team.py','smart_independent_oracle.py']:
 s=r['files'][k]['summary']; print(f"{k}|{s['covered_lines']}/{s['num_statements']}|{s['covered_branches']}/{s['num_branches']}|ML={s['missing_lines']}|MB={s['missing_branches']}")
