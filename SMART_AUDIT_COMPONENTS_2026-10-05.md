# Componentes e escopo da evidência — SMART-MEGA — 05/10/2026

Snapshot: fonte corrigida `f96aab608ad020df86204b52721785059f504b22`, certificação persistida em `93c6a8ee68b60fad8894650018d975179f15cf39`. Registro: `smart_agent_skill_orchestration.py` + `SmartSkillRuntime.registrations()` em `smart_skill_runtime.py`. Não foi criado registro concorrente.

## Comandos

Foram encontrados 28 parsers na raiz por inspeção dos 135 módulos Python. Não há aplicação HTTP/OpenAPI identificada. A coluna de testes refere-se a casos efetivamente aprovados no [JUnit canônico](SMART_AUDIT_JUNIT_CURRENT.xml), não à execução completa de cada comando em produção. A descoberta/subprocesso de todos os `--help`, com entrada, saída e duração nas propriedades JUnit, está implementada em `test_smart_cli_entrypoints.py`, mas **NÃO VERIFICADA** enquanto o CI do PR #21 aguarda runner.

| Entrypoint | Evidência automatizada já aprovada | Exercício CLI uniforme |
|---|---|---|
| `adjudicate_signal_challenger.py` | ❌ NÃO VERIFICADO Cobertura direta específica não atribuída nesta auditoria | ❌ Smoke `--help` pendente no PR #21 |
| `freeze_next_research.py` | ❌ NÃO VERIFICADO Cobertura direta específica não atribuída nesta auditoria | ❌ Smoke `--help` pendente no PR #21 |
| `smart_3054_terminal_executor.py` | ✅ test_smart_3054_terminal_executor (8 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_agent_runtime.py` | ✅ test_smart_agent_runtime (5 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_agent_skill_functional_gate.py` | ✅ test_smart_agent_skill_functional_gate (3 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_agent_skill_orchestration.py` | ✅ test_smart_agent_skill_orchestration (5 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_ai_fine_tuning.py` | ✅ test_smart_ai_fine_tuning (5 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_champion_challenger.py` | ❌ NÃO VERIFICADO Cobertura direta específica não atribuída nesta auditoria | ❌ Smoke `--help` pendente no PR #21 |
| `smart_falsification_lab.py` | ✅ test_smart_falsification_lab (11 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_frontier_adjudicator.py` | ✅ test_smart_frontier_adjudicator (10 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_frontier_signal_lab.py` | ✅ test_smart_frontier_signal_lab (10 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_github_operator.py` | ✅ test_smart_github_operator (9 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_historical_training_intake.py` | ✅ test_smart_historical_training_intake (4 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_official_dataset_reconcile.py` | ✅ test_smart_official_dataset_reconcile (7 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_official_result_ingest.py` | ✅ test_smart_official_result_ingest (13 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_operator.py` | ✅ test_smart_operator_adjudicate_atomicity, test_smart_operator_e2e_recovery, test_smart_operator_missed_recovery_20260910, test_smart_operator_preflight, test_smart_operator_reauthorization, test_smart_operator_seed_rollover_20260910, test_smart_operator_unprepared_missed_recovery_20260915 (41 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_portfolio_backtest.py` | ❌ NÃO VERIFICADO Cobertura direta específica não atribuída nesta auditoria | ❌ Smoke `--help` pendente no PR #21 |
| `smart_portfolio_backtest_merge.py` | ❌ NÃO VERIFICADO Cobertura direta específica não atribuída nesta auditoria | ❌ Smoke `--help` pendente no PR #21 |
| `smart_portfolio_pipeline.py` | ✅ test_smart_portfolio_pipeline (6 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_probability_audit.py` | ✅ test_smart_probability_audit (5 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_procedural_youtube_batch.py` | ❌ NÃO VERIFICADO Cobertura direta específica não atribuída nesta auditoria | ❌ Smoke `--help` pendente no PR #21 |
| `smart_prospective_cycle.py` | ✅ test_smart_prospective_cycle (4 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_rag_excel.py` | ✅ test_smart_rag_excel (5 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_randomness_cartography.py` | ✅ test_smart_randomness_cartography (17 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_regression_evidence.py` | ✅ test_smart_regression_evidence (3 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_total_integration_gate.py` | ✅ test_smart_total_integration_gate (3 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_v2_engine.py` | ✅ test_smart_v2_engine (5 casos) | ❌ Smoke `--help` pendente no PR #21 |
| `smart_v2_production.py` | ✅ test_smart_v2_production (11 casos) | ❌ Smoke `--help` pendente no PR #21 |

`smart_operator.py` expõe: `status`, `preflight`, `prepare`, `withdraw`, `recover-missed`, `catch-up`, `authorize-next-cycle`, `authorize-generation`, `freeze`, `adjudicate`, `post-result-report`, `review`, `hold`, `terminal`. O roteamento/contrato e várias regras de estado têm fixtures aprovadas em `test_smart_operator_*.py`; isso não comprova todas essas operações em produção. Na missão atual, `status` foi observado em runner, a renovação executou startup real `OK`, e `catch-up` foi solicitado, mas não chegou a executar por falta de runner.

## Nove executores e todas as 41 capacidades

A certificação renovada executou probes nativas e validou aliases/handoffs. Evidências aprovadas: `test_runtime_executes_all_agents_and_capabilities` (1,394 s), `test_every_declared_handoff_is_acknowledged` (1,507 s), `test_functional_gate_proves_full_matrix` (4,022 s), `test_every_pertinent_capability_alias_resolves_through_owner_contract` (3,976 s), `test_every_pertinent_capability_is_individually_callable` (2,719 s).

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

## Jobs, dados e contratos

- `ci.yml`: regressão e renovação/persistência da certificação, ✅ 946 testes; último source certificado `f96aab6`.
- `repository-integrity.yml`: ✅ PR #20; ❌ job do push em main não recebeu runner. Não confundir falha de infraestrutura com falha de código.
- `operator.yml`: ✅ status/importação em main; ❌ recuperação e teste de persistência após nova execução ainda não concluídos.
- Dados operacionais: `Mega-Sena.xlsx`, snapshots causais, JSON self-hashed, ledger append-only, lifecycle com revisão/CAS, diário transacional e locks. SQLite/MLflow é superfície de experimentação auxiliar, não banco principal do cartão.
- Variáveis identificadas no fluxo GitHub: `GITHUB_REPOSITORY`, `GITHUB_REF`, `GITHUB_EVENT_NAME`, `GITHUB_SHA`, `GITHUB_RUN_ID`; o operador exige o repositório/ref/evento apropriados. `SMART_CHECKPOINT_OUTPUT` controla saída auxiliar. Nenhuma chave nova foi identificada como necessária nesta missão.
- Fonte oficial: API CAIXA e PDFs de cronograma arquivados. Timeout e lote oficial versionado/validado já existem na ingestão. Disponibilidade atual da API e continuidade completa da recuperação: **NÃO VERIFICADAS** nesta tentativa.
- Casos aprovados relevantes: `test_ingest_is_atomic_and_refuses_overwrite`, `test_register_is_idempotent`, `test_registration_rejects_bad_probability_sum`, `test_adjudicate_operation_rolls_back_ledger_lifecycle_and_report_on_report_failure`, `test_reviewed_to_hold_validates_previous_target_and_writes_next_target`.
