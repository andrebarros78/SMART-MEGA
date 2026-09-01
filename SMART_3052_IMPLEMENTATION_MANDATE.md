# SMART — Gate obrigatório pré-concurso 3052

Registrado em 30/08/2026 às 13h43 (America/Sao_Paulo).

## Regra executiva

Os 15 pontos abaixo são requisitos obrigatórios de arquitetura e governança para o SMART antes da freeze do concurso 3052. Nenhuma freeze do 3052 deve ser considerada pronta enquanto os 15 itens não estiverem **implementados, testados e comprovados**. Resultado parcial não libera o gate.

1. Atribuição marginal e contrafactual permanente.
2. Utilidade marginal por sinal.
3. Penalização de redundância e consenso falso.
4. Interações entre sinais.
5. Meta-pesos condicionais ao contexto.
6. Calibração das 60 posições/scores.
7. Múltiplos Challengers especializados.
8. Meta-governador Champion-of-Challengers.
9. Red Team adversarial contínuo.
10. Aprendizado incremental com proteção contra sobre-reação.
11. Expansão criteriosa de novos sinais.
12. Prova prospectiva sequencial.
13. Gate de promoção.
14. Auditoria independente e não regressão.
15. Promoção somente com evidência.

## Critério de liberação

A freeze do concurso 3052 somente é liberada quando `SMART_3052_IMPLEMENTATION_GATE.json` registrar os 15 itens com `status = PROVEN` e evidências verificáveis. Itens 12 a 15 significam que os mecanismos de prova, promoção e auditoria devem estar implementados antes do 3052; não autorizam fabricar ou antecipar evidência prospectiva ainda inexistente.

## Guardrails

- Nenhum resultado posterior pode entrar antes da freeze correspondente.
- O concurso 3051 e suas freezes permanecem imutáveis.
- Champion permanece ativo até promoção prospectiva comprovada.
- Ganho histórico ou sintético não equivale a prova prospectiva.
- Mudanças devem obedecer medir antes -> alterar -> medir depois -> comparar -> reverter se houver regressão.

## Estado de implementação — P02 concluído

- **P01 — Atribuição marginal e contrafactual permanente: PROVEN.** Evidência preservada em `SMART_P01_COUNTERFACTUAL_ATTRIBUTION_PROOF.json`.
- **P02 — Utilidade marginal por sinal: PROVEN.** Leave-one-out causal OOS por sinal, Δ hits do ensemble, lift de rank, média/variância/EWMA/confiança, estado incremental e evento append-only `MARGINAL_UTILITY`. Evidência: `SMART_P02_MARGINAL_SIGNAL_UTILITY_PROOF.json`.
- **P03–P15: pendentes.** A freeze 3052 permanece bloqueada.

O P02 mede utilidade marginal e a expõe ao agente, mas permanece com `weight_effect_enabled = false`. Isso impede transformar medição pós-resultado em alteração automática de pesos antes dos pontos posteriores de governança/calibração.

## Estado de implementação — P03

- **P03 — Penalização de redundância e consenso falso: PROVEN.** Implementado `smart_signal_redundancy_consensus.py` com penalização por novidade global e anti-multiplicidade de clusters correlacionados. O limiar pré-declarado `0,90` foi mantido; o candidato exploratório `0,95` foi rejeitado por regressão no holdout. Em teste sintético com quatro cópias redundantes, a massa conjunta caiu de `0,80` para `0,58` e o sinal independente subiu de `0,20` para `0,42`. Evidência principal: `SMART_P03_FALSE_CONSENSUS_REDUNDANCY_PROOF.json`.
- **Progresso do gate: 3/15 PROVEN; P04–P15 pendentes.** A freeze 3052 permanece bloqueada.

O ganho histórico do P03 (+2 hits no total e +2 no holdout versus a política legada) é apenas evidência de não regressão de engenharia e não é tratado como prova preditiva prospectiva.


## Estado de implementação — 30/08/2026 17h24 BRT

- **P04 — Interações entre sinais: PROVEN.** Motor permanente `smart_signal_interactions.py`; 66 pares acompanhados causalmente em 2.050 concursos OOS; diagnóstico pós-resultado de pares e tríades; evento `INTERACTIONS` append-only no 3051 preservado e correção versionada `INTERACTIONS_CORRECTION` anexada sem reescrita, com equivalência semântica comprovada; `weight_effect_enabled = false`, mantendo a fronteira P04→P05. Evidência: `SMART_P04_SIGNAL_INTERACTIONS_PROOF.json`.
- **P01–P04: PROVEN. P05–P15: pendentes.** A freeze 3052 permanece bloqueada.

O P04 aprende sinergia/antagonismo entre sinais, mas não converte essas interações em alteração de pesos. Essa conversão contextual pertence ao P05 e permanece proibida até sua implementação e prova.


## Atualização P05 — 30/08/2026

- P05_CONTEXTUAL_META_WEIGHTS: **PROVEN**.
- Implementação: `smart_contextual_meta_weights.py`.
- Política adotada: `meta_strength = 0.06`, escolhida somente em calibração OOS 1001–2200.
- Candidato `0.08`: rejeitado por regressão no holdout.
- Holdout final 2801–3050: P05 150 hits vs baseline 150, sem regressão.
- Total histórico OOS: P05 1271 vs baseline 1271.
- Cobertura crítica: 1604/1604 statements e 514/514 branches.
- Prova: `SMART_P05_CONTEXTUAL_META_WEIGHTS_PROOF.json`.
- Estado do gate: 5/15 PROVEN; P06–P15 permanecem obrigatórios; freeze 3052 continua bloqueada.
