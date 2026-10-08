# SMART-MEGA V6 — PROJETO EXECUTIVO DE CORREÇÃO TECNOLÓGICA

- **IANE exclusiva:** `IANE-SMART-MEGA-TECH-DEBT-CORRECTION-20261010`
- **Repositório canônico:** `andrebarros78/SMART-MEGA`
- **Branch canônica:** `main`
- **Baseline HEAD registrada na F00:** `44964a0c1f0133a034a3700614266bc1ad79ac42`
- **Registro efetivo:** `2026-10-08T06:57:15-03:00`
- **Data formal do projeto executivo:** `2026-10-10`
- **Registro antecipado:** autorizado por ordem explícita do usuário em 2026-10-08.
- **Estado após F00:** `F00_PROVEN`
- **Próxima fase autorizável:** `F01_GRAFO_E_REACHABILITY`

## Objetivo

Eliminar a diferença entre componente existente, componente declarado como integrado, componente realmente alcançável, componente realmente consumido e componente com contribuição controlada e comprovada para o produto.

O fluxo alvo permanece:

`dados → sinais/features → fine-tuning causal → calibração → probabilidades/ranking → candidatos → seleção robusta → cartão primário → freeze → resultado → adjudicação → aprendizado → recalibração`.

## Regras executivas

1. GitHub `andrebarros78/SMART-MEGA/main` é a autoridade persistente.
2. Cada fase redescobre o HEAD corrente antes de mutação.
3. Prova histórica não fecha fase nova.
4. `ACTIVE` exige alcance e consumo comprováveis.
5. Skill metodológica não pode ser apresentada como execução direta.
6. Executor determinístico não pode ser apresentado como LLM/autonomous agent.
7. SDK instalado sem consumo não conta como integração.
8. LLM não recebe autoridade direta sobre pesos, probabilidades, ranking ou cartão sem gate quantitativo.
9. Toda mudança segue `MEDIR → ALTERAR → TESTAR → COMPARAR → RETER OU REVERTER`.
10. Nenhuma mudança pode introduzir leakage, informação futura ou recalibração retrospectiva.
11. Integração arquitetural não equivale a melhoria preditiva.
12. Resultado inferior a 6/6 comprovado não fecha a missão.

## Ordem imutável

F00 — REGISTRO_CANONICO_E_IANE
F01 — GRAFO_E_REACHABILITY
F02 — DEPENDENCIA_CIRCULAR
F03 — EXECUTOR_LEGADO
F04 — FINE_TUNING_NO_CICLO
F05 — REGISTRY_CANONICA
F06 — AGENTES_E_HANDOFFS_REAIS
F07 — SKILLS_E_ADAPTERS
F08 — COMPONENTES_PARALELOS
F09 — SDK_LLM_SELETIVO
F10 — TESTES_DE_DESCONEXAO
F11 — VALIDACAO_PREDITIVA_E_NAO_REGRESSAO
F12 — RECONCILIACAO_CONSOLIDACAO_SELO

## Gates resumidos

- **F00:** identidade exclusiva, baseline, escopo e ledger persistidos sem alteração funcional.
- **F01:** grafo executável; zero componente de produção inalcançável ou não classificado.
- **F02:** eliminar ciclo `operator ↔ full_process_pipeline`.
- **F03:** retirar `smart_3054_terminal_executor.py` do runtime canônico.
- **F04:** fine-tuning causal integrado ao ciclo pré-freeze com holdout e fallback.
- **F05:** registry única de componentes e autoridades.
- **F06:** handoffs materiais, consumidos e verificáveis.
- **F07:** separar reference/quarantine/native adapter/active skill.
- **F08:** integrar, sombrear, fundir ou arquivar componentes paralelos.
- **F09:** SDK/LLM somente por lacuna objetiva e inicialmente sem autoridade preditiva direta.
- **F10:** CI falha para falsos ACTIVE, desconexões, aliases indevidos e legado runtime.
- **F11:** comparar baseline × candidato e provar não regressão.
- **F12:** reconciliar arquitetura × runtime × provas × Git e selar.

## Regra terminal

`F00..F12 PASS + zero deficiência material conhecida + não regressão + baseline Git canônica coerente = PROJETO_EXECUTIVO_CORRECAO_PROVEN`.

Vantagem preditiva científica continua exigindo prova prospectiva independente.

## F00 — execução observada

A F00 foi registrada antecipadamente em 2026-10-08 por ordem explícita do usuário. Esta antecipação limita-se aos artefatos de governança da missão. Nenhum código funcional, workflow, runtime, modelo, peso, dataset ou autoridade preditiva foi alterado pela F00.
