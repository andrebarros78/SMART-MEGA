import json
req=['smart_bounded_online_learning.py','smart_signal_expansion_governance.py','smart_sequential_prospective_proof.py','smart_promotion_gate.py','smart_independent_audit.py','smart_evidence_only_promotion.py','smart_continuous_red_team.py','smart_global_integrity.py','smart_champion_challenger.py','adjudicate_signal_challenger.py','smart_v2_production.py','smart_portfolio_optimizer.py','smart_portfolio_pipeline.py','smart_agent_skill_orchestration.py','smart_agent_runtime.py','smart_agent_skill_functional_gate.py','smart_learning_activation_gate.py','smart_learning_activation_authority.py','smart_data_quality_gate.py','smart_independent_oracle.py','smart_material_deficiency_registry.py']
d=json.load(open('SMART_COVERAGE_GLOBAL_CURRENT.json',encoding='utf-8'))
bad=[]
for m in req:
 f=d.get('files',{}).get(m); s=f.get('summary',{}) if f else {}
 ok=f is not None and s.get('missing_lines')==0 and s.get('missing_branches')==0 and s.get('covered_lines')==s.get('num_statements') and s.get('covered_branches')==s.get('num_branches')
 print(f"{m}|{s.get('covered_lines')}/{s.get('num_statements')}|{s.get('covered_branches')}/{s.get('num_branches')}|{'PASS' if ok else 'FAIL'}")
 if not ok: bad.append(m)
print('TOTAL',len(req),'PASS',len(req)-len(bad),'BAD',len(bad))
print('BADLIST',bad)
