# SMART-MEGA — Preparação de ingestão e auditoria científica 3071

**Registro de preparação:** 19/10/2026, após publicação do resultado.  
**Baseline inspecionada:** `main@01ae8d2f4c9be6b21b98d5e9e33e464dae0db340`.  
**Escopo:** preparação operacional e auditoria *ex-post*; **não é ingestão, adjudicação, autorização de pesos nem conclusão científica**.

## Resultado e proveniência

- Sorteio 3071 em 18/10/2026: **12, 22, 41, 45, 51, 52**; acumulado. Próximo sorteio anunciado para 20/10/2026, prêmio estimado R$ 185.000.000,00.
- Comprovação visual enviada pelo operador, corroborada pela página pública oficial CAIXA (consulta em 19/10/2026): https://loterias.caixa.gov.br/Paginas/Mega-Sena.aspx .
- Arquivo preparado para o consumidor existente: `SMART_3071_RESULT_INPUT.json`, contrato `SMART_OPERATOR_RESULT_INPUT_1`. **Não confundir** a confirmação visual/WEB desta auditoria com resposta bruta assinada ou capturada pela API primária. O registro via operador será classificado no código como `source_independently_verified=false`; corroboração dual não foi comprovada.

## Autoridades anteriores ao resultado (preservar)

- `SMART_ACTIVE_EPOCH.json`: target 3071, cutoff 3070, estado `FROZEN`, ID `operator-3071-10553e1b5911-20261015T184134194917Z`.
- Freeze de 15/10/2026 18:49:21 UTC: `runtime/learning_epochs/operator-3071-10553e1b5911-20261015T184134194917Z/SMART_3071_CHAMPION_CHALLENGER_FREEZE.json`; SHA-256 declarada `5bd372977cb5c5f36358f31997ab05e9da38f8d010d6badf2e8abceaef0b4fab`.
- Cartão principal já congelado: **10, 11, 27, 38, 43, 53**. Não recalcular, substituir, escolher outro cartão ou atribuir retrospectivamente autoridade produtiva a candidatos sombra.
- Data exata de sorteio **não estava verificada na autoridade temporal do freeze** (`OPERATOR_UNVERIFIED_DRAW_TIME`); a data posterior foi corroborada apenas na presente auditoria. Não usar isso para criar prova temporal retroativa.

## Auditoria preliminar observacional (não substituir adjudicação canônica)

- Cartão principal: **0/6**. Top-6 campeão e challenger: **0/6**.
- Quatro cartões auxiliares imutáveis: **0/6 cada**.
- Posições das dezenas oficiais no ranking campeão (1=maior): 12→60, 22→43, 41→42, 45→50, 51→54, 52→48. Nenhuma das seis ficou no Top-40.
- Peso `freq1000` entre especialistas no freeze: **0,460816055980125**; família `freq`: **0,7**. A concentração é hipótese para ablação controlada, **não causa provada**.
- `false_negative_rescue`: `DEGRADED_SHADOW_ONLY`, 2 observações, 4 itens em quarentena; nenhuma promoção preditiva autorizada.
- Cálculo auditável: `Brier = sum_{n=1}^{60}(p_n - 1[n sorteado])²/60`, com probabilidades registradas antes do sorteio. Referência uniforme: `0,09`.

| Candidato prospectivo congelado | Top-6 acertos | Brier 3071 | Delta vs uniforme |
| --- | ---: | ---: | ---: |
| Uniforme (referência) | não aplicável | 0,090000 | 0 |
| `frontier_cooccurrence_graph` | 0 | 0,092281 | +0,002281 |
| `frontier_transition_markov` | 0 | 0,097008 | +0,007008 |
| `frontier_gap_hazard` | 0 | 0,097042 | +0,007042 |
| `frontier_recent_lift` | 0 | 0,101205 | +0,011205 |
| `frontier_weekday_bayes` (uniforme) | 0 | 0,090000 | 0 |

A amostra é **um único sorteio**. A diferença observada não demonstra tendência, causalidade, ganho ou regressão estatisticamente generalizável. O resultado **não autoriza** recalibração de pesos, troca de campeão ou atualização de performance prospectiva já registrada.

## Fluxo operacional existente, em ordem, a executar no checkout governado

1. Consultar estado remoto fresco (`main`, lifecycle, active epoch, transação pendente, histórico, congelamento e hashes). Evitar concorrência e atualizar a operação se outro executor já tiver consumido 3071.
2. Executar **somente leitura** `python smart_github_operator.py --operation preflight --target 3071`. O fluxo nativo encadeia `result-preflight` quando encontra época já congelada. Registrar saída real. Sem `SMART_OPERATOR_RESULT_3071.json`, o código atual prevê `WAITING_OPERATOR_RESULT`; não alegar que o preflight foi executado neste registro.
3. Registrar a entrada preservada, usando o executor oficial `python smart_github_operator.py --operation register-result --target 3071 --payload SMART_3071_RESULT_INPUT.json`. Esperar um novo commit contendo `SMART_OPERATOR_RESULT_3071.json` com hash e procedência `OPERATOR`.
4. Repetir `preflight`. Somente `READY_TO_CONSUME` com checagem de freeze/hashes, seis dezenas/dia corretos e contrato `canonical_writes_performed=false` permite prosseguir. `BLOCKED_*`, `RECOVERY_REQUIRED`, `WAITING_*` impedem o consumo.
5. Consumir resultado pela ação **explícita**, independente, `python smart_github_operator.py --operation terminal --target 3071` somente após a prontidão: usar append-only, um evento de adjudicação, um aprendizado observacional, provas, histórico até 3071 e nenhuma mutação do cartão de 15/10.
6. Somente após terminal validado, emitir `post-result-report`, conferir pontuação real e atribuição de sinais, gerar/revisar artefatos de aprendizado e review/hold canônicos. Não preparar ou gerar cartão 3072 automaticamente.
7. Auditar commits GitHub, alterações estritamente esperadas, hash do dataset, cardinalidade dos eventos e comparação entre 60 probabilidades originais e resultado. Registrar falhas, data, diferenças e executor real. Não confundir preparação com os passos executados.

## Ajuste e calibração propostos (ainda não aplicados)

1. Medir, por concurso, cobertura, integridade e recência dos sinais; contribuição marginal, redundância, intensidade, consistência e impacto em ranking, Brier e cartão.
2. Diagnosticar especificamente o **colapso de recall no Top-40**, a dominância do `freq1000`, os sinais de curta janela e as entradas de `false_negative_rescue` em quarentena. Controlar cenário de sorteios especiais e mudança de calendário.
3. Criar candidatos `SHADOW_ONLY` com ablação de `freq1000`, limites de concentração e recuperação de sinais; pré-registrar os parâmetros **sem usar 3071 para decidir a versão vencedora**. Tratar 3071 exclusivamente como observação anterior para estudos futuros, nunca como amostra independente se influenciar a hipótese.
4. Usar walk-forward com cutoff temporal rigoroso e holdout não utilizado na seleção. Exigir menor perda prospectiva global e não regressão demonstradas sobre a política uniforme e o campeão antes de qualquer promoção. Rejeitar ganhos locais sem evidência; manter `strength=0` em produção enquanto não aprovado.
5. Preservar estado científico `MISSION_ACTIVE / UNPROVEN`; sem 6/6 comprovado nos critérios de arquitetura não declarar `MISSION_PROVEN`.

## Pendências verificáveis

- **Preparado:** input de resultado, reconciliação read-only de referências e cálculo observacional dos candidatos.
- **Não executado:** registro do resultado pelo operador; preflight em runner; terminal/ingestão; relatório pós-resultado canônico; revisão/hold; ensaios OOS e promoção de pesos.
- GitHub Actions é rota existente no código, mas **execução real não foi observada** nesta preparação. Via executor federado é válida somente se operar no mesmo repositório/commit e publicar recibos no GitHub.
