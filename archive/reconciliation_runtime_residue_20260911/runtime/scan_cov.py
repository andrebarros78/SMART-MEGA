import json
req=['smart_bounded_online_learning.py','smart_signal_expansion_governance.py','smart_sequential_prospective_proof.py','smart_promotion_gate.py','smart_independent_audit.py','smart_evidence_only_promotion.py','smart_continuous_red_team.py','smart_global_integrity.py','smart_champion_challenger.py','adjudicate_signal_challenger.py','smart_v2_production.py','smart_portfolio_optimizer.py','smart_portfolio_pipeline.py','smart_agent_skill_orchestration.py','smart_agent_runtime.py','smart_agent_skill_functional_gate.py','smart_learning_activation_gate.py','smart_learning_activation_authority.py','smart_data_quality_gate.py','smart_independent_oracle.py','smart_material_deficiency_registry.py']
r=json.load(open('SMART_COVERAGE_GLOBAL_CURRENT.json',encoding='utf-8-sig'))
for src in req:
    x=r.get('files',{}).get(src)
    if not x:
        print(f'{src}|MISSING')
        continue
    s=x.get('summary',{})
    print(f"{src}|{s.get('covered_lines')}/{s.get('num_statements')}|{s.get('covered_branches')}/{s.get('num_branches')}|missingL={s.get('missing_lines')}|missingB={s.get('missing_branches')}")
