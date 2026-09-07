@echo off
cd /d "C:\New Projet\SMART-MEGA"
set COVERAGE_FILE=C:\New Projet\SMART-MEGA\runtime\.coverage_smart_closure
set SRC=smart_bounded_online_learning,smart_signal_expansion_governance,smart_sequential_prospective_proof,smart_promotion_gate,smart_independent_audit,smart_evidence_only_promotion,smart_continuous_red_team,smart_global_integrity,smart_champion_challenger,adjudicate_signal_challenger,smart_v2_production,smart_portfolio_optimizer,smart_portfolio_pipeline,smart_agent_skill_orchestration,smart_agent_runtime,smart_agent_skill_functional_gate,smart_learning_activation_gate,smart_learning_activation_authority,smart_data_quality_gate,smart_independent_oracle,smart_material_deficiency_registry
.venv\Scripts\python.exe -E -m pytest -q test_smart_current_continuity_generation.py > runtime\v6_fix_targeted.log 2>&1
if errorlevel 1 (echo TARGETED_FAIL>runtime\v6_fix_stage.txt & echo 1>runtime\v6_fix.exit & exit /b 1)
echo TARGETED_PASS>runtime\v6_fix_stage.txt
.venv\Scripts\python.exe -E -m coverage run --append --branch --source=%SRC% -m pytest -q test_smart_coverage_core.py test_smart_coverage_governance.py test_smart_11of10_critical_path_coverage.py test_p14_critical_branch_coverage.py test_smart_global_integrity.py test_smart_independent_audit.py test_smart_continuous_red_team.py test_smart_sequential_prospective_proof.py test_smart_bounded_online_learning.py test_smart_signal_expansion_governance.py test_smart_evidence_only_promotion.py test_smart_portfolio_optimizer.py test_smart_portfolio_pipeline.py test_smart_agent_skill_orchestration.py test_smart_agent_runtime.py test_smart_agent_skill_functional_gate.py test_smart_learning_activation_gate.py test_smart_learning_activation_authority.py test_smart_data_quality_gate.py test_smart_architecture_corrections_20260905.py test_smart_material_deficiency_registry.py test_smart_architecture_hardening_20260905.py > runtime\v6_fix_cov_targeted.log 2>&1
if errorlevel 1 (echo COVERAGE_TARGETED_FAIL>runtime\v6_fix_stage.txt & echo 2>runtime\v6_fix.exit & exit /b 2)
echo COVERAGE_TARGETED_PASS>runtime\v6_fix_stage.txt
.venv\Scripts\python.exe -E -m coverage json -o runtime\SMART_COVERAGE_CLOSURE.json > runtime\v6_fix_cov_json.log 2>&1
if errorlevel 1 (echo COVERAGE_JSON_FAIL>runtime\v6_fix_stage.txt & echo 3>runtime\v6_fix.exit & exit /b 3)
echo COVERAGE_READY>runtime\v6_fix_stage.txt
echo 0>runtime\v6_fix.exit
