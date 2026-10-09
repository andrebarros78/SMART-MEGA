# SMART-MEGA V6 — preparação para consumo do resultado 3068

## Escopo e fronteira
- Repositório exclusivo: andrebarros78/SMART-MEGA, branch main.
- Concurso: **3068**. Histórico congelado até **3067**.
- Data constante da autoridade prospectiva: **08/10/2026**.
- Freeze definido no documento SMART_ACTIVE_EPOCH.json, com referência ao arquivo imutável e SHA-256.
- Esta preparação **não ingere o resultado, não adjudica, não atualiza pesos e não avança o histórico**.
- A operação result-preflight é somente leitura; o workflow GitHub utiliza a escolha já existente preflight, que verifica o estado FROZEN e invoca o gate de resultado sem gravar nada.
- Apenas a ação explícita terminal, autorizada na main, pode iniciar o consumo e mutações operacionais.

## Gate de prontidão (somente leitura)
No GitHub Actions, workflow **SMART-MEGA GitHub Operator**, selecionar:
- operation = preflight
- target = 3068
- payload_path vazio
- Ref: main
- No log, inspecionar o campo result_readiness_status e o documento result_preflight.

GitHub CLI: gh workflow run operator.yml --repo andrebarros78/SMART-MEGA --ref main -f operation=preflight -f target=3068

Verificações:
1. Reconciliação de startup OK e ausência de transação pendente.
2. Lifecycle FROZEN e epoch 3068 validados por SHA-256.
3. Freeze e histórico prefixado 3067 preservados; sem geração retroativa.
4. Leitura da CAIXA com concurso, seis dezenas únicas e data compatíveis com a autoridade congelada.
5. Consenso entre canais quando disponível; canal secundário indisponível não equivale a consenso.
6. Ausência de escrita persistente, adjudicação ou consumo para aprendizado.

Resultados possíveis:
- READY_TO_CONSUME: leitura oficial validada, sem mutação, com estado explícito da dupla corroboração (campo result_readiness_status).
- WAITING_OFFICIAL_RESULT: não consumir; verificar publicação/conectividade.
- RECOVERY_REQUIRED, BLOCKED_INTEGRITY ou BLOCKED_OFFICIAL_EVIDENCE: corrigir a causa; não acionar terminal.

## Consumo posterior — execução separada e explícita
Somente após READY_TO_CONSUME, e autorização operacional:

1. gh workflow run operator.yml --repo andrebarros78/SMART-MEGA --ref main -f operation=terminal -f target=3068
2. O executor existente executa **consenso CAIXA → ingestão append-only XLSX → adjudicação do cartão congelado → atualização causal de sinais e provas sequenciais → auditoria independente → atualização canônica do resultado**, preservando o freeze.
3. Validar no commit operacional: resultado, hashes, adjudicação única, eventos de aprendizado, prefixo histórico e não regressão. Em caso de erro, não considerar arquivos parciais como ciclo concluído.
4. Se o lifecycle estiver em ADJUDICATED, emitir/revalidar relatório via operation=post-result-report, target=3068; conferir SMART_POST_RESULT_REPORT_3068.json e sua cadeia de hashes.
5. Review e hold exigem os artefatos de revisão e autorização; não preparar nem congelar 3069 automaticamente.

## Restrições de segurança e ciência
- Resultado do concurso 3068 jamais recalcula, edita ou substitui o cartão congelado 3068.
- Uma observação não autoriza alterar pesos. Os gates F12/F13, não regressão, aprendizado F14 e promoção prospectiva continuam vinculantes.
- 6/6 é um resultado eventual verificável após o sorteio, nunca uma garantia da implementação.
- Alterações críticas somente por PR, CI, certificação e histórico Git íntegro.
