# Componentes e alcance da evidência — SMART-MEGA — 05/10/2026

Fonte testada: 6262cdcbd5be7a5ca73bcfc01c4d2e70868a93d2; 989 testes aprovados no PC Escola. Registro existente: smart_agent_skill_orchestration.py + SmartSkillRuntime.registrations(). Nenhum registro paralelo. Sem servidor HTTP/OpenAPI identificado.

## 28 comandos CLI com parser

Entrada --help, subprocesso real, limite de 30 s; saída e stderr completos/resumidos nas propriedades cli_smoke do JUnit e no JSON de evidência federada. Smoke prova abertura/importação/contrato de argumentos, não todas as operações em produção.

| Comando | Entrada | Status / tempo | Cobertura funcional atribuída |
|---|---|---|---|
| adjudicate_signal_challenger.py | --help | ✅ exit 0 / 3.806 s | NÃO ATRIBUÍDA por nome; não inferir ausência de testes indiretos |
| freeze_next_research.py | --help | ✅ exit 0 / 0.862 s | NÃO ATRIBUÍDA por nome; não inferir ausência de testes indiretos |
| smart_3054_terminal_executor.py | --help | ✅ exit 0 / 3.739 s | 8 casos |
| smart_agent_runtime.py | --help | ✅ exit 0 / 0.426 s | 5 casos |
| smart_agent_skill_functional_gate.py | --help | ✅ exit 0 / 0.422 s | 3 casos |
| smart_agent_skill_orchestration.py | --help | ✅ exit 0 / 0.347 s | 5 casos |
| smart_ai_fine_tuning.py | --help | ✅ exit 0 / 3.044 s | 5 casos |
| smart_champion_challenger.py | --help | ✅ exit 0 / 3.582 s | NÃO ATRIBUÍDA por nome; não inferir ausência de testes indiretos |
| smart_falsification_lab.py | --help | ✅ exit 0 / 3.287 s | 11 casos |
| smart_frontier_adjudicator.py | --help | ✅ exit 0 / 2.98 s | 10 casos |
| smart_frontier_signal_lab.py | --help | ✅ exit 0 / 3.053 s | 10 casos |
| smart_github_operator.py | --help | ✅ exit 0 / 0.139 s | 9 casos |
| smart_historical_training_intake.py | --help | ✅ exit 0 / 0.909 s | 4 casos |
| smart_official_dataset_reconcile.py | --help | ✅ exit 0 / 1.139 s | 7 casos |
| smart_official_result_ingest.py | --help | ✅ exit 0 / 1.241 s | 13 casos |
| smart_operator.py | --help | ✅ exit 0 / 3.565 s | 41 casos |
| smart_portfolio_backtest.py | --help | ✅ exit 0 / 2.708 s | NÃO ATRIBUÍDA por nome; não inferir ausência de testes indiretos |
| smart_portfolio_backtest_merge.py | --help | ✅ exit 0 / 2.415 s | NÃO ATRIBUÍDA por nome; não inferir ausência de testes indiretos |
| smart_portfolio_pipeline.py | --help | ✅ exit 0 / 1.021 s | 6 casos |
| smart_probability_audit.py | --help | ✅ exit 0 / 3.287 s | 5 casos |
| smart_procedural_youtube_batch.py | --help | ✅ exit 0 / 0.687 s | NÃO ATRIBUÍDA por nome; não inferir ausência de testes indiretos |
| smart_prospective_cycle.py | --help | ✅ exit 0 / 0.139 s | 4 casos |
| smart_rag_excel.py | --help | ✅ exit 0 / 1.07 s | 5 casos |
| smart_randomness_cartography.py | --help | ✅ exit 0 / 0.92 s | 17 casos |
| smart_regression_evidence.py | --help | ✅ exit 0 / 0.178 s | 3 casos |
| smart_total_integration_gate.py | --help | ✅ exit 0 / 0.386 s | 3 casos |
| smart_v2_engine.py | --help | ✅ exit 0 / 0.898 s | 5 casos |
| smart_v2_production.py | --help | ✅ exit 0 / 0.116 s | 11 casos |

smart_operator.py expõe status, preflight, prepare, withdraw, recover-missed, catch-up, authorize-next-cycle, authorize-generation, freeze, adjudicate, post-result-report, review, hold e terminal. Fixtures testam roteamento, idempotência, rollback e transições; não se alega execução de todos os comandos em produção. Produção observada: catch-up até 3066 concluído; HOLD 3067. Checkout novo: status OK e preflight 3067 AWAITING_OPERATOR_AUTHORIZATION, ambos exit 0 e sem mutação; prova em SMART_RESTORE_VERIFICATION_2026-10-05.json.

## Nove executores e todas as 41 capacidades


A regressão atual e a certificação federada executaram probes, aliases e handoffs. Casos do JUnit atual: test_runtime_executes_all_agents_and_capabilities (3.450 s); test_every_declared_handoff_is_acknowledged (3.419 s); test_functional_gate_proves_full_matrix (9.132 s); test_every_pertinent_capability_alias_resolves_through_owner_contract (9.000 s); test_every_pertinent_capability_is_individually_callable (6.236 s).

**Limite:** são executores determinísticos de papéis, não agentes autônomos LLM. Os 37 nomes pertinentes são aliases de metodologia para probes/funções nativas; aprovação não significa executar diretamente os SDKs/skills de terceiros com esses nomes. As quatro referências do curator ficam intencionalmente sem execução externa. Essa quarentena é validada, não tratada como capacidade produtiva ativa.

| Executor/owner | Probe | Capacidades declaradas | Estado comprovado |
|---|---|---|---|
| `quarantine_curator` | `quarantine_manifest_integrity` | `bridging-online-offline-rl`, `growth-experimenter`, `kaggle-learner`, `visiontrim-unified-vision-token` | ✅ Probe nativa no BUILD; sem autoridade preditiva/LLM |
| `research_scout` | `research_registry_read_validation` | `dianoia`, `thinktank-me-multi-expert-framework-middle`, `ml-engineer`, `pymc` | ✅ Probe nativa no BUILD; sem autoridade preditiva/LLM |
| `data_guardian` | `canonical_draw_quality_audit` | `openai-analyze-data-quality`, `openai-validate-data`, `pandera-data-contracts`, `data-analysis` | ✅ Probe nativa no BUILD; sem autoridade preditiva/LLM |
| `null_model_cartographer` | `synthetic_cartography_execution` | `aeon`, `regime-detection`, `time-series-forecasting`, `networkx`, `statsmodels`, `ruptures` | ✅ Probe nativa no BUILD; sem autoridade preditiva/LLM |
| `falsification_auditor` | `synthetic_falsification_execution` | `experiment-design`, `simulation`, `statistical-analysis`, `multiple-testing-fdr-statsmodels`, `bayesian-workflow`, `machine-learning-model-validation`, `mlflow` | ✅ Probe nativa no BUILD; sem autoridade preditiva/LLM |
| `learning_calibration_governor` | `bounded_learning_and_calibration_execution` | `evo-memory`, `model-drift-management`, `hyperparameter-tuning-optuna`, `conformal-risk-control-mapie`, `live-evo-online-evolution-agentic`, `benchmarking-uncertainty-calibration-long-form`, `superforecasting`, `extremizing-forecasts` | ✅ Probe nativa no BUILD; sem autoridade preditiva/LLM |
| `robustness_red_team` | `red_team_safety_execution` | `property-based-testing-hypothesis`, `test-gap-analysis`, `mutmut-mutation` | ✅ Probe nativa no BUILD; sem autoridade preditiva/LLM |
| `combinatorial_solver` | `or_tools_portfolio_execution` | `combinatorialist`, `operations-research-algorithm-developer`, `google-or-tools`, `z3-formal-verification`, `nisan-et-al-2007-algorithmic-game-theory` | ✅ Probe nativa no BUILD; sem autoridade preditiva/LLM |
| `mission_governor` | `canonical_mission_status_resolution` | Sem alias; consome handoffs e lê missão canônica | ✅ Probe nativa no BUILD; sem autoridade preditiva/LLM |


## 42 entradas sem parser: manutenção, pesquisa e histórico

Identificadas estaticamente; não foram executadas indiscriminadamente contra estado canônico. A coluna funcional registra apenas casos associados por nome no JUnit. Entrada direta NÃO VERIFICADA, salvo integridade e API de certificação observadas separadamente. Não se afirma que funções sem associação nominal estejam sem cobertura indireta.

| Script | Evidência funcional atual | Entrada direta |
|---|---|---|
| smart_3054_adjudication_preflight.py | ✅ 5 casos | ❌ NÃO VERIFICADA |
| smart_3054_full_cycle_sandbox.py | ✅ 2 casos | ❌ NÃO VERIFICADA |
| smart_50_round_simulation.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_adversarial_claim_audit.py | ✅ 1 casos | ❌ NÃO VERIFICADA |
| smart_agent_ecosystem_governance.py | ✅ 6 casos | ❌ NÃO VERIFICADA |
| smart_canonical_result_store_reconcile.py | ✅ 3 casos | ❌ NÃO VERIFICADA |
| smart_canonical_root_rebind.py | ✅ 2 casos | ❌ NÃO VERIFICADA |
| smart_capability_integration_v2.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_cartography_extended.py | ✅ 3 casos | ❌ NÃO VERIFICADA |
| smart_causal_shadow_runner.py | ✅ 1 casos | ❌ NÃO VERIFICADA |
| smart_context_calibration_confirm.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_context_calibration_confirm_v2.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_continuity_consolidator.py | ✅ 3 casos | ❌ NÃO VERIFICADA |
| smart_continuous_red_team.py | ✅ 5 casos | ❌ NÃO VERIFICADA |
| smart_engineering_activation.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_execution_checkpoint.py | ✅ 1 casos | ❌ NÃO VERIFICADA |
| smart_extended_falsification.py | ✅ 3 casos | ❌ NÃO VERIFICADA |
| smart_falsification_power_audit.py | ✅ 1 casos | ❌ NÃO VERIFICADA |
| smart_finalize_capability_integration_v3.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_finalize_deployment.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_full_process_pipeline.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_github_certify.py | ❌ NÃO ATRIBUÍDA | ✅ refresh(..., executor_host=...) PASS; __main__ Actions não exercitado aqui |
| smart_hypothesis_state_reconciler.py | ✅ 4 casos | ❌ NÃO VERIFICADA |
| smart_learning_epoch_reset.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_monte_carlo_convergence.py | ✅ 2 casos | ❌ NÃO VERIFICADA |
| smart_procedural_caption_extract.py | ✅ 1 casos | ❌ NÃO VERIFICADA |
| smart_procedural_coverage_gate.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_procedural_cronogram_acquire.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_procedural_cronogram_build_dataset.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_procedural_youtube_recent_acquire.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_product_certification.py | ✅ 10 casos | ❌ NÃO VERIFICADA |
| smart_promote_cartography_1000.py | ✅ 1 casos | ❌ NÃO VERIFICADA |
| smart_prospective_authority.py | ✅ 4 casos | ❌ NÃO VERIFICADA |
| smart_prospective_authority_lock.py | ✅ 3 casos | ❌ NÃO VERIFICADA |
| smart_refresh_falsification_report.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_regression_runner.py | ✅ 9 casos | ❌ NÃO VERIFICADA |
| smart_repository_integrity.py | ✅ 6 casos | ✅ PASS, HOLD 3067 |
| smart_runtime_guard.py | ✅ 2 casos | ❌ NÃO VERIFICADA |
| smart_signal_2000_simulation.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_signal_50_round_simulation.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_signal_drift_calibration.py | ❌ NÃO ATRIBUÍDA | ❌ NÃO VERIFICADA |
| smart_skill_runtime.py | ✅ 4 casos | ❌ NÃO VERIFICADA |

## Jobs, armazenamento e contratos

- ci.yml: contrato de regressão/certificação preservado; evidência nova executada diretamente, não apresentada como CI hospedado.
- repository-integrity.yml: validador real PASS no PC Escola após corrigir HOLD sem epoch; indisponibilidade anterior de runner não é resultado de teste.
- operator.yml: recuperação real 37366096200 SUCCESS; mutações via wrapper continuam exigindo dispatch explícito em main. A CLI nativa e a API de certificação permitem a execução federada autorizada, com publicação Git supervisionada.
- XLSX/JSON/snapshots causais; ledger append-only, CAS, journal e locks. SQLite/MLflow é auxiliar.
- GITHUB_REPOSITORY/REF/EVENT_NAME/SHA/RUN_ID validados no caminho Actions; origem Git, hostname e UUID no caminho federado. Nenhuma chave nova. SMART_CHECKPOINT_OUTPUT é saída auxiliar.
- API CAIXA e PDF oficial: resultados até 3066 recuperados e persistidos, com prova/hashes; concursos perdidos não criaram previsão. Disponibilidade da API em outro instante não é inferida desse sucesso.
- Unicidade, probabilidades, idempotência, rollback, estados, erro padronizado e confiança não fabricada: casos do JUnit atual.
