# Aviso de supersessão — SMART_GITHUB_NATIVE_ONLY_20261021

Este arquivo contém registro histórico, **não instruções operacionais atuais**. Para SMART-MEGA V6, a única autoridade ativa é GitHub `andrebarros78/SMART-MEGA`, branch `main`, conforme `AGENTS.md` e `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md` seção 13. Indicações antigas de retomada em PC, VPS, LMCP, rede federada ou checkout local foram revogadas. Execução e testes somente no GitHub Actions com runners hospedados pelo GitHub. Não confundir relatos passados com permissões presentes.

---

# SMART-MEGA — continuidade canônica (09/10/2026)

Repositório: GitHub `andrebarros78/SMART-MEGA`, branch `main`. A raiz de execução é o Git top-level do checkout atual. O código preditivo não teve pesos alterados.

## Último ciclo concluído

- Concurso **3068** (08/10/2026): dezenas oficiais **07, 10, 39, 40, 43, 57**. Evidência publicada pela API CAIXA, HTTP 200, obtida no PC Vendas via conector e preservada sem alterar os bytes; SHA-256 da resposta `22baec9f2d61ff121b747223131672a83390e132b792d9e16d3ff159b9b95a91`. A confirmação pelo arquivo secundário da CAIXA não estava disponível.
- Cartão principal já congelado, preservado: **10, 11, 27, 35, 38, 53**. Resultado **1/6** (10). [Relatório 3068](SMART_POST_RESULT_REPORT_3068.json).
- Adjudicação original e aprendizado sequencial de 3068 foram executados, com um único evento FREEZE, ADJUDICATION, LEARNING_UPDATE e SEQUENTIAL_PROOF. [Revisão](SMART_POST_RESULT_REVIEW_3068.json) e [comprovante da ingestão](SMART_CANONICAL_HISTORY_ADVANCE_3068.json).
- Histórico canônico `Mega-Sena.xlsx`: concursos até **3068**, SHA-256 `208aff8a3c1c33293f4f903ae02fe03f6c1ca9ad4e57e5bb4265de35a345c6fd`.
- Estado 3068 arquivado com hashes em [ARCHIVE_MANIFEST.json](SMART_STATE_ARCHIVE/adjudicated-epochs/3068/operator-3068-acc6a34c9e27-20261008T222652499219Z/ARCHIVE_MANIFEST.json). Ponteiro `SMART_ACTIVE_EPOCH.json` removido pelo rollover nativo, como esperado.
- [SMART_OPERATIONAL_LIFECYCLE.json](SMART_OPERATIONAL_LIFECYCLE.json): `HOLD`, `completed_contest=3068`, `target_contest=3069`. [SMART_NEXT_CYCLE_HOLD.json](SMART_NEXT_CYCLE_HOLD.json) bloqueia preparação ou geração automática. O preflight 3069 respondeu `AWAITING_OPERATOR_AUTHORIZATION`; **não há cartão 3069 gerado**.

## Limites científicos e próximos passos

[SMART_MISSION_STATUS.json](SMART_MISSION_STATUS.json) permanece `MISSION_ACTIVE`, `UNPROVEN` e `terminal_6of6_proven=false`. Um acerto não autoriza alterar o peso de `freq1000` ou de qualquer sinal sem ganho validado fora da amostra.

A tentativa de auditoria histórica P14 identificou originais de freezes antigos ausentes (3055, 3057, 3060 e 3061). O resultado não foi mascarado nem a auditoria científica declarada PASS. A via operacional nativa independente realizou adjudicação, atualização de estado e rollover; a prova de vantagem preditiva continua não comprovada.

Para retomar, validar as três autoridades vivas (ciclo, HOLD, missão) e executar `python -E -B -X utf8 smart_operator.py preflight --target 3069` em checkout com dependências. Só autorizar preparar/gerar 3069 mediante ordem explícita; nunca reconstruir cartões já congelados após conhecer sorteios. Registro histórico de 3067 permanece disponível no Git.

## Aprendizado do YouTube: decisao auditada pre-3069

Auditoria: SMART_YOUTUBE_LEARNING_AUDIT_PRE3069.json. Os scripts de coleta do YouTube e o canal procedimental existem, mas os registros de legendas e seus manifestos nao estao presentes no checkout canonico. O observador visual v1.3.1 e seus testes estao na branch learning/video-observation-v131-20261009, ainda sem consumo preditivo no main. Foi testado isoladamente (29 testes aprovados); a via procedimental e testes adjacentes passaram (44). A integracao ja proposta na branch integration/video-authority-f01-20261009 o classifica como DIAGNOSTIC; nao ha ganho preditivo real comprovado. Os 13 checkpoints B2 citados anteriormente nao foram revalidados nesta auditoria.

Decisao operacional: manter Youtube em SHADOW_ONLY, nao usar videos posteriores ao fechamento de apostas para pesar o mesmo sorteio e nao alterar os pesos campeoes sem amostra observacional autentica, cutoff e validacao fora da amostra. O 3069 continua HOLD e nenhum cartao novo foi gerado.
