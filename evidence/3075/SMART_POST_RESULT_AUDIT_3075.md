# SMART-MEGA V6 — resultado e diagnóstico técnico do concurso 3075

**Data da auditoria:** 27/10/2026 (Brasília)  
**Repositório:** `andrebarros78/SMART-MEGA`  
**Versão da previsão originalmente executada:** `4223265a9b9b6d342a0e9c5e9615880ddbb5db21`  
**Concurso:** 3075, sorteado em 26/10/2026  
**Resultado:** **07, 10, 14, 27, 36, 55**  
**Cartão imutavelmente congelado:** **10, 11, 27, 38, 43, 53**  
**Acertos:** **2/6 (10 e 27)**

## 1. Ingestão executada e conferida

Foi acessada diretamente a API da Caixa para o concurso 3075:
`https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/3075`, com número, data e seis dezenas validados. O lote local mantém `raw_api_independently_verified=false`, pois o seu hash de arquivo não certifica o transporte HTTPS, apesar de a consulta efetivamente ter sido feita.

O operador nativo `smart_fast_result_ingest.py --target 3075 --payload-file SMART_RESULT_BATCH_3075_CAIXA_CAPTURE.json --apply` encerrou com `INGESTED_TO_HOLD`. A verificação independente posterior encerrou com `VERIFY_EXIT=0`.

| Evidência | Resultado |
|---|---|
| `SMART_OPERATIONAL_LIFECYCLE.json` | `HOLD`, `target_contest=3076`, `completed_contest=3075`, revisão 69, hash válido |
| `SMART_NEXT_CYCLE_HOLD.json` | próximo alvo 3076, hash válido |
| `SMART_POST_RESULT_REPORT_3075.json` | `PASS`, hash válido |
| `SMART_POST_RESULT_REVIEW_3075.json` | `POST_RESULT_REVIEW_COMPLETE`, hash válido |
| `SMART_CANONICAL_HISTORY_ADVANCE_3075.json` | `PASS`, hash válido |
| `Mega-Sena.xlsx` | 3.075 concursos, última linha 3075 contendo exatamente 07, 10, 14, 27, 36, 55 |
| Cartão 3075 recuperado pelo leitor imutável | `FROZEN_MODEL_CARD_VERIFIED`, dezenas preservadas |
| SHA-256 do histórico após a ingestão | `1340f65c0ffe5cb4e11d465547425043f2ec1474e43b182dc2234d89f025b6b9` |

Nenhum cartão foi gerado retroativamente; nenhuma aposta foi realizada; nenhum peso/modelo foi automaticamente promovido.

## 2. Auditoria do congelamento anterior ao sorteio

A previsão foi gerada em **2026-10-26T08:51:01Z**, com `target_contest=3075`, `cutoff_contest=3074`, `frozen_before_result=true` e `result_used=false`.

| Dezena do resultado | Ranking do campeão (1–60) | Dentro do pool de 18 | Selecionada |
|---|---:|---|---|
| 07 | 50 | Não | Não |
| 10 | 2 | Sim | Sim |
| 14 | 15 | Sim | Não |
| 27 | 5 | Sim | Sim |
| 36 | 36 | Não | Não |
| 55 | 56 | Não | Não |

O seletor considerou inicialmente 18 dezenas, avaliou **18.564 combinações**, das quais **10.256 viáveis**, sem fallback. Escolheu exatamente o top 6 do campeão. Os pesos somavam 1 e a ordenação das 60 dezenas correspondia à ordenação decrescente dos escores. **Não há evidência de erro de soma, troca de posições ou de perda do cartão no consumidor.**

### Restrições estruturais

Os limites de faixas utilizados são: 2–4 números de 01–20; 1–3 de 21–40; 0–2 de 41–60; pelo menos um dos três primeiros colocados. Só **47,965%** das combinações legalmente possíveis satisfazem os limites de faixas. A limitação **não reduz a chance matemática de um cartão individual** sob sorteios independentes uniformes, mas restringe a busca em caso de verdadeiro sinal não uniforme.

No concurso 3075, a distribuição real (3 baixas, 2 médias, 1 alta) era permitida: **os limites de faixas não são a causa direta dos quatro números perdidos**. O pool inicial/ranking descartou 07, 36 e 55 antes da otimização.

### Limitação do aprendizado

O resgate de falsos negativos permaneceu em `DEGRADED_SHADOW_ONLY` por evidências históricas 3060/3061 não homologadas; suas sugestões **não influenciaram** o cartão oficial. Essa quarentena não deve ser removida sem comprovar a proveniência.

## 3. Defeito aritmético de limite encontrado

`smart_v2_engine.py` declara `EXPERT_CAP_WITHIN_FAMILY = 0.60`. Na geração do campeão, porém, a rotina aplicava o teto **antes** de multiplicar pelos fatores de redundância; a normalização subsequente anulava parcialmente o limite.

Valores observados no congelamento 3075:
- Família `freq`: **70,0000%** do peso agregado.
- Sinal `freq1000`: **45,9125%** do peso agregado.
- Participação condicional na família: **65,5893%**, acima de **60%**.

A violação foi reproduzida com teste determinístico: **RED 1 FAIL** (`76,923%` condicional), **1 PASS**. Correção na branch `fix/mega-3075-expert-weight-cap-20261027`, commit `f047530289e57c7e427c048313c21f62f9c5f670`: reprojeção dos **pesos efetivos finais** no simplex com limite. Resultado: **GREEN 2 PASS** e **40 testes focados PASS** (um aviso Pydantic não fatal).

**PR #90 (draft):** https://github.com/andrebarros78/SMART-MEGA/pull/90  
**Não incorporada à produção nem ao congelamento original.**

## 4. Comparação temporal, sem resultado 3075 no replay

Foram usados somente concursos até **3074**, com mesmo histórico e cortes temporais para motor original e candidato corrigido.

| Janela | Motor original | Peso efetivo corrigido |
|---|---:|---:|
| Calibração, 1.000 concursos | 607 | 597 |
| Validação, 351 concursos | 244 | 244 |
| Holdout, 224 concursos | 128 | 131 |
| Global, 2.074 concursos | **1.274** | **1.268** |

No holdout: **5 vitórias, 2 derrotas, 217 empates** por concurso; teste de sinal unilateral exato **p=0,2265625**. Melhora de três acertos insuficiente para comprovar superioridade; queda global de seis acertos. **A promoção do candidato está bloqueada**.

O motor original apresentou média `1274/2074 = 0,6143`, contra `0,6` por concurso para um cartão uniforme. A diferença é de aproximadamente **0,925 desvio-padrão**, abaixo de limiares usuais de evidência estatística. Seu holdout ficou em **128/224 = 0,5714**, abaixo da expectativa uniforme de `134,4` acertos nesse período.

**Importante:** o relatório `SMART_AI_FINE_TUNING_CURRENT.json` de ajuste do agente apresenta **1.246** acertos para uma configuração distinta. Não confundir esse replay com os **1.274** acertos do motor campeão `smart_v2_engine.walk_forward`.

## 5. Diagnóstico e decisão

- **Ingestão, congelamento, validação de ranking e consumo do cartão:** funcionaram neste concurso, com evidências.
- **Defeito real de cálculo:** teto de influência por especialista pode ser ultrapassado após correção de redundância. Corrigido em branch isolada, RED→GREEN, sem promoção.
- **Problema de engenharia preditiva:** concentração de pesos históricos, limitação do pool (18 dezenas), ganho global não comprovado, salvaguardas de aprendizado em shadow.
- **Omissões no cartão:** 07, 36 e 55 mal ranqueados; 14 era candidata, mas preterida. O resultado do sorteio não prova que elas poderiam ter sido ranqueadas corretamente antes do sorteio.
- **Evidência estatística e regra de não regressão:** o experimento corrigido **não está apto a substituir** o motor atual. Mesmo o motor atual carece de vantagem prospectiva comprovada sobre o acaso.
- **Próximo concurso:** 3076 em `HOLD`, sem nova previsão autorizada por esta ingestão.

A PR #80 de governança estatística está separada e também não foi incorporada ao código executado. O sistema **não está homologado como preditor 6/6**.
