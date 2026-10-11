# SMART-MEGA V6 — Auditoria causal, degradação e reparo de integridade

Data-base: 11/10/2026. Repositório canônico: `andrebarros78/SMART-MEGA`.

## Identidade da fonte e objetivo

- Código avaliado: commit `09081465b320aaff6544bc3cebc04187fb350944`.
- Escopo: ingestão histórica, qualidade dos sinais, pesos, cartão, congelamento, adjudicação, aprendizado e evidência da previsão.
- A correção técnica deste ciclo NÃO constitui prova de ganho preditivo, acerto de 6 dezenas ou aprovação científica 6/6.

## Fatos observados no código e nos dados

1. O concurso 3069 foi ingerido sem previsão canônica aprovada; o congelamento 3069 encontrado na VPS permanece não publicado. Um registro local não deve ser contado retroativamente como tentativa canônica.
2. Os relatos pós-resultado 3060, 3061, 3062 e 3068 foram postos em quarentena pelo verificador `smart_false_negative_rescue.py`, por indisponibilidade ou divergência dos bytes da evidência de freeze/ledger, contra os SHA-256 assinados pelos relatórios. Antes do reparo apenas 3067 era elegível entre cinco.
3. Consequência: `apply_rescue()` devolve os scores originais no estado `DEGRADED_SHADOW_ONLY` enquanto há histórico incompleto. Isso preserva a segurança mas deixa o aprendizado corretivo sem influência sobre o cartão. **As quatro evidências anteriores continuam em quarentena**, pois não se encontrou a versão exata no histórico Git examinado.
4. Nos freezes 3067 e 3068, champion e challenger devolveram as mesmas seis dezenas; em 3068 `freq1000` representava aproximadamente 46,8% do peso do champion. Esse fato exige monitoramento de diversidade/adaptação, mas não justifica reponderação sem prova fora da amostra.
5. Histórico walk-forward por `smart_v2_engine`, com atualização causal: 2.069 concursos do índice inicial 1000 até 3069, 1.272 acertos totais, contra 1.241,4 esperados para um cartão fixo aleatório; período 2801–3050: 148 contra 150; 3051–3069: 11 contra 11,4. O ganho agregado histórico não demonstra superioridade estatística robusta, especialmente após seleção/adaptação de modelos.
6. Evidências P05 (150 × 150) e P10 (1.271 × 1.271) mostram empate, não vantagem; P06 registrou Brier 0,09001357670052432 versus 0,09 uniforme em seu holdout e sua calibração foi corretamente neutralizada. Nenhuma dessas evidências autoriza promoção de uma política preditiva superior.
7. Para seis dezenas escolhidas entre sessenta em sorteio justo, P(0 acertos)=C(54,6)/C(60,6), aproximadamente 0,515884; um resultado de 0/6 isolado não prova defeito no código.

## Causa raiz reparada

O relatório assinado preservava um SHA-256 de ledger mutável sem arquivar os bytes daquela versão. O ledger podia avançar após adjudicação, e o módulo de resgate deixava de conseguir validar a versão vinculada por hash.

O produtor `smart_post_result_report.py` agora guarda uma cópia imutável, com criação exclusiva e verificação exata de SHA-256, em `SMART_STATE_ARCHIVE/hash-bound-learning/<concurso>/SMART_SIGNAL_LEDGER.<sha256>.json` antes de emitir o relatório. O consumidor `smart_false_negative_rescue.py` recupera exclusivamente a cópia com digest correto; adulteração continua em quarentena.

O publicador `smart_github_operator.py` aceita a extensão `.json` sob `SMART_STATE_ARCHIVE`, permitindo persistir o novo artefato pelo commit operacional.

## Não regressão e integridade

- `test_smart_post_result_report.py` passou a testar que o ledger original pode mudar após a adjudicação sem destruir o testemunho histórico, e que a adulteração do arquivo arquivado é rejeitada.
- Arquivos Python `smart_false_negative_rescue.py`, `smart_post_result_report.py` e `test_smart_post_result_report.py` foram fixados com `-text` em `.gitattributes` para impedir conversão LF/CRLF que invalidava os registros F01/F05/F10.
- Os registros F01, F05 e F10 foram reconstruídos e verificados.
- Suíte integral em quatro worktrees **novos e independentes**, todos no mesmo commit.
- Arquivo de evidência JUnit agregado: `SMART_AUDIT_JUNIT_CURRENT.xml` após recertificação federada, SHA-256 conferido pelo mecanismo de certificação.

## Pendências científicas e operacionais

- As evidências históricas 3060/3061/3062/3068 não podem ser substituídas por conteúdo semelhante; permanecem em quarentena. É preciso acumular novas evidências prospectivas completas e validar alternativas em dados independentes.
- Não foi promovida alteração de pesos, de heurísticas de resgate ou do algoritmo de combinação sem ganho preditivo comprovado.
- Nenhuma alegação de melhor probabilidade de Sena, de aprendizagem produtiva já recuperada ou de sucesso 6/6 é autorizada por este reparo.
- A próxima rodada científica deve avaliar hipótese e controle com `previsão congelada antes do resultado → resultado oficial → acertos reais → comparação com uniforme → OOS prospectivo`, preservando o campeão até haver ganho consistente.

## Prova da regressão de código

- Commit do código ensaiado: `09081465b320aaff6544bc3cebc04187fb350944`.
- Total de casos independentes: **1208**; falhas: **0**; erros: **0**.
- SHA-256 da evidência JUnit consolidada: **975a7bf0640e70f344322cf9452c72ef0c66ac8cff4f4a88789715f44ec96bfd**.
- Identificação do pacote de testes: `SMARTMEGA_20261011_CERTIFIED_1208_RECEIPT.json`, derivado dos quatro JUnit originais e de testes únicos.

**Estado da engenharia:** reparo verificado por regressão, sujeito a publicação/recertificação.
**Estado científico:** vantagem preditiva NÃO COMPROVADA. `MISSION_PROVEN` científico não declarado.
