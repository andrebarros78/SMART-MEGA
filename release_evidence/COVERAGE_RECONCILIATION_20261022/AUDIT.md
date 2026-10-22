# SMART-MEGA V6 — continuação da auditoria forense

As correções de resolução de evidências e recuperação foram verificadas no commit `2aa7bedd6416b3c5924a870f8fa58e8017df8c42`. A regressão atual contém **1.711 casos aprovados, zero falhas, erros ou casos ignorados**, além de oito subtestes aprovados registrados nos relatórios brutos. A cobertura exigida alcançou **100% dos 23 módulos**, com 5830/5830 instruções e 2470/2470 ramos executados. GitHub Actions não foi usado.

## Achados corrigidos

| Prioridade | Problema comprovado | Correção e prova |
|---|---|---|
| P1 | O resolvedor verificava um caminho relativo no diretório atual e calculava o hash na raiz do módulo. Isso bloqueava a apuração ou verificava outro caminho. O mesmo defeito afetava o estado arquivado. | Retornar e hashificar o mesmo caminho absoluto. Falhas reproduzidas nos diagnósticos 01 e 07; regressões atuais cobrem resolução única, ambiguidade e arquivo de estado. |
| P2 | JSON válido que não era objeto interrompia a descoberta de uma retirada válida com `AttributeError`. | Validar o tipo antes de acessar os campos; preservar e ignorar o arquivo inválido. Diagnóstico 04 e regressão atual de artefatos inválidos. |
| P1 | A medição anterior não comprovava os cenários completos de Red Team e dois testes AST atribuíam funções do operador a nomes fictícios. | Executar os dez cenários reais, atribuir os dois corpos intactos ao arquivo original e medir novamente os 23 módulos atuais. |
| P1 | Faltavam provas de vários caminhos de CAS, autorização, reserva, recuperação e rollback, inclusive da transição terminal bem-sucedida. | Testar evidência inválida, transações concorrentes, cópias corrompidas, restauração do histórico/ponteiro e transição persistida `FROZEN → ADJUDICATED` sem duplicação na repetição. |

## Vínculo e método

Base canônica: `8b6030863a77d2f10508c8afd180f1975b5cabd6`. Fonte testada: `2aa7bedd6416b3c5924a870f8fa58e8017df8c42`. Impressão de 361 arquivos: `80965bfc4c12f27f5fccd21720e32da6bf401811aaa4ee65b07acfe466f4f03f`.

Uma coleta independente identificou os 1.711 casos. Quatro checkouts isolados executaram inventários disjuntos de 357, 465, 434 e 455 casos. Cada recibo exige código, SHA e estado científico estáveis, checkout limpo, resultado real zero e correspondência exata entre os casos coletados e os nós `testcase` do JUnit. A cobertura soma somente essas quatro execuções atuais e uma execução instrumentada dos dez cenários reais de Red Team no mesmo SHA. Nenhuma cobertura histórica ou tentativa incompleta entra no resultado.

O pytest registra oito subtestes aprovados nas contagens declaradas sem criar nós XML separados. Os XMLs brutos foram mantidos. O agregado foi construído exclusivamente com os casos reais, após confrontar coleta, inventários, resultados, ausência de falhas/ignores e o excedente de subtestes dos logs. Nenhum caso foi inventado. Os limites dos testes, as metas e as exclusões de cobertura do projeto não foram reduzidos.

A instrumentação de todos os processos tornou dois smokes de CLI próximos do limite de 30 segundos; a explicação por sobrecarga é uma inferência, pois a tentativa inicial foi interrompida. A rodada certificada mantém os limites originais e mede o processo principal, com Red Team instrumentado separadamente. Um erro posterior no executor apontou para diretórios anteriores: as quatro execuções foram interrompidas e descartadas, e alguns logs anteriores não ficaram integralmente preservados. O executor corrigido exige SHA, diretório de evidências e cwd coerentes antes de gravar. Todos os resultados certificados são posteriores e independentes dessas tentativas. A primeira preparação complementar de Red Team também falhou por omitir a cópia do próprio módulo; somente a execução corrigida e completa foi utilizada.

## Cobertura atual

| Módulo exigido | Instruções | Ramos |
|---|---:|---:|
| `adjudicate_signal_challenger.py` | 421/421 | 210/210 |
| `smart_agent_runtime.py` | 206/206 | 38/38 |
| `smart_agent_skill_functional_gate.py` | 63/63 | 20/20 |
| `smart_agent_skill_orchestration.py` | 268/268 | 100/100 |
| `smart_bounded_online_learning.py` | 133/133 | 52/52 |
| `smart_canonical_history_advance.py` | 231/231 | 108/108 |
| `smart_champion_challenger.py` | 389/389 | 148/148 |
| `smart_continuous_red_team.py` | 260/260 | 74/74 |
| `smart_data_quality_gate.py` | 85/85 | 22/22 |
| `smart_evidence_only_promotion.py` | 300/300 | 162/162 |
| `smart_global_integrity.py` | 246/246 | 126/126 |
| `smart_independent_audit.py` | 571/571 | 294/294 |
| `smart_independent_oracle.py` | 236/236 | 134/134 |
| `smart_learning_activation_authority.py` | 156/156 | 74/74 |
| `smart_learning_activation_gate.py` | 26/26 | 14/14 |
| `smart_material_deficiency_registry.py` | 144/144 | 54/54 |
| `smart_operator.py` | 1129/1129 | 436/436 |
| `smart_portfolio_optimizer.py` | 147/147 | 64/64 |
| `smart_portfolio_pipeline.py` | 89/89 | 20/20 |
| `smart_promotion_gate.py` | 64/64 | 26/26 |
| `smart_sequential_prospective_proof.py` | 286/286 | 152/152 |
| `smart_signal_expansion_governance.py` | 265/265 | 104/104 |
| `smart_v2_production.py` | 115/115 | 38/38 |

## Certificação e limites

Estado verificado: produto `CONSTRUCTION_PROVEN`, governança `PASS`, integridade global `PASS`, atualidade das autoridades `PASS` e inicialização `OK`. A reconstrução ocorreu em checkout descartável do SHA testado, com aprovação explícita desse SHA e identidade UUIDv4 do executor. Os arquivos científicos congelados, histórico, ledger e ponteiros operacionais permaneceram com os mesmos bytes. A aceitação em processo independente retornou operador `OK`, preflight `ALREADY_FROZEN` e leitura `FROZEN_MODEL_CARD_VERIFIED` para o cartão existente, sem criar autorização para o próximo ciclo. GitHub/main permanece a autoridade; os checkouts usados nesta auditoria são temporários.

Esta é uma certificação de construção e integridade. **Não promove nem comprova previsão prospectiva de 6/6.** A execução foi Linux; não substitui homologação nativa em Windows. O `pip check` atual passou; esta continuação não declara uma nova auditoria completa de CVEs. A proteção administrativa de `main` permanece uma limitação externa registrada na auditoria anterior e deve ser conferida pelo administrador do repositório.

## Evidências reproduzíveis

`EXECUTION.json` contém as contagens e recibos; `COVERAGE_SUMMARY.json` lista os arquivos e hashes medidos; `EVIDENCE.json` vincula fonte, estados e pacote bruto. O pacote mantém JUnit, logs, configurações, bases reais de cobertura, scripts executados, inventário independente e diagnósticos segregados. Os dados dos diretórios `diagnostic/` não compõem a aprovação.

Pacote: `RAW_EVIDENCE.tar.gz`, SHA-256 `c2ef5a290c6000a68281f4b6932e528d9f7a0d5456d158af20a93f9584f3dec8`, 2036929 bytes. A lista de arquivos brutos e seus hashes está em `RAW_FILE_MANIFEST.json`.
