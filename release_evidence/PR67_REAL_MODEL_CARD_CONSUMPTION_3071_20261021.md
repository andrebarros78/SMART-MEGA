# SMART-MEGA V6 — recuperação do cartão preditivo congelado e diagnóstico do consumidor

**Data da inspeção:** 21/10/2026, horário de Brasília. **Ambiente:** VPS Linux `wmcp-cloud-01`. **Repositório privado:** `andrebarros78/SMART-MEGA`. **PR de engenharia:** #67, sem merge na main.

## Defeito funcional identificado

O operador possuía o cartão gerado pelo motor, mas não disponibilizava sua sequência de dezenas ao usuário após o congelamento. A via `smart_github_operator` para operações de somente leitura descarta `observation` na formatação do JSON final. O fluxo `generate-card` para concursos seguintes sob `FROZEN` só tinha contingência aleatória explicitamente não preditiva, e a adjudicação antiga permanecia em aberto.

**Correção implementada:** `smart_frozen_card_reader.py`, leitor independente de dependências pesadas (Python stdlib), valida a integridade do `SMART_ACTIVE_EPOCH.json`, congelamento, `FULL_PROCESS_PROOF.json`, portfólio e `SMART_3071_PRIMARY_CARD.json`. Valida SHA-256 dos arquivos, hashes dos documentos, datas-alvo/cutoff, seletor/números e origem `result_used=false`; rejeita symlinks, adulteração, target futuro, leitura de card não congelado. **Não escreve em produção, não recalcula após o resultado, não muda pesos e não conclui adjudicação.**

Integração concluída:
- Ação `show-card` adicionada ao contrato do operador e ao `smart_operator.py`.
- Ação somente leitura integrada a `smart_github_operator.py` com execução direta do leitor Python, **sem GitHub Actions** e sem importar o runtime preditivo.
- Corrigido o renderizador do operador: agora devolve `model_card`, inclusive as **seis dezenas**, em vez de descartar o objeto de observação.

Comando real executado:

```shell
python3 smart_github_operator.py --operation show-card --target 3071
```

**Resultado:** `model_card.status = FROZEN_MODEL_CARD_VERIFIED`; cartão `[10,11,27,38,43,53]`, originado de 15/10/2026, cutoff 3070, com artefatos SHA-256 íntegros:
- Freeze: `5bd372977cb5c5f36358f31997ab05e9da38f8d010d6badf2e8abceaef0b4fab`
- Primary card: `cb0f8d53873f2f91a06233399509a2e4aaa35fe5d102ee91dc455fe6a2731d5c`
- Portfolio: `58b55b111c743e3c03705746eee036e51c2e803514b7a268403df7593c1eb04c`
- Full process proof: `3f8bf78ccc4b312231304292a81a0981253fce30cea799f9de0659c0119897f5`
- Resposta do leitor auto-hash SHA-256: `126f04ba7dff08d090b0d1b7e03194fc1384411593989e9efa1a9a449bb9a527`.

## Medição objetiva do resultado do concurso 3071

Resultado divulgado pela CAIXA para o concurso 3071 (18/10/2026): **12, 22, 41, 45, 51, 52**. Conferência externa: https://loterias.caixa.gov.br/Paginas/Mega-Sena.aspx (página de resultados, concurso 3071, observação datada deste gate).

O arquivo do repositório `SMART_OPERATOR_RESULT_3071.json` contém exatamente as mesmas seis dezenas, mas **`source_independently_verified=false` no contrato interno**. A verificação externa deste relatório não modifica automaticamente essa autoridade interna.

Comparação objetiva: conjunto previsto `{10,11,27,38,43,53}` versus conjunto sorteado `{12,22,41,45,51,52}`: **0/6 acertos**. Isso é um dado de desempenho, **não** certificação de utilidade preditiva ou justificativa para atribuir mérito a sinais específicos sem atribuição causal testada. Nenhuma previsão congelada foi alterada ou retroajustada.

O concurso 3072 também já foi sorteado em 20/10/2026 (`02,06,09,16,31,40` segundo imprensa), portanto gerar agora um novo cartão para o 3072 e chamá-lo de previsão prospectiva seria inválido. A construção prospectiva atual deve preparar concurso posterior com os resultados intermediários realmente verificados, sem pular o cutoff exigido pelo produto.

## Testes na VPS

- Ação `show-card` real: **PASS**, incluindo resultado JSON com dezenas.
- Testes específicos do leitor e integração: **11/11 PASS** (adulteração de freeze/cartão/portfólio, target errado, symlink, não mutação, integração).
- Pipeline Linux `smart_linux_ci.py --profile focused`: **75 testes PASS** no commit de código `23d96c0591476fa2b5d8eccd6770ccf324ecf331`.
- Recibo focused `release_evidence/ci_linux/SMART_LINUX_CI_focused_ad1fed1958174bf886d86198eae0dee3.json`, SHA `449e2e09c16d9c9b35922e6bf7d2809f3592c19951b7339c142c3a8b463f5831`.
- Perfil `full --certify`: `BLOCKED_DEPENDENCIES`; recibo `release_evidence/ci_linux/SMART_LINUX_CI_full_778a982de182470ea7720f4e9fb959c8.json`, SHA `41b05503eccc696f45962741279de61199a413aca40faef34090fd8cd2f9764e`.

## O que permanece materialmente pendente

A leitura do cartão **já criado** agora funciona sem adjudicação. A **geração prospectiva de um novo cartão de modelo** para o próximo concurso ainda exige resultados anteriores incorporados e um runtime com as dependências do sistema, além da autorização de avanço do lifecycle. A sequência 3071→3072 não foi formalmente encerrada no produto. Não tratar contingência aleatória como previsão do motor.

A autorização LMCP `capreq_68e0d83804ad4d7d895f7371b2a715ef` para as dependências isoladas permanecia pendente. **Não contornar uma negativa**, não recorrer aos PCs excluídos nem declarar que há homologação integral.

**Critérios SMART 6/6:** não comprovados — além das lacunas de homologação, houve zero acertos reais na previsão avaliada.

**Status do gate:** `FROZEN_MODEL_CARD_READ_PROVEN; NEXT_PROSPECTIVE_CARD_NOT_READY; NO_MISSION_PROVEN`.
