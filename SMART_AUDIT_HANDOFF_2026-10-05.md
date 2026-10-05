# SMART-MEGA V6 — auditoria e retomada — 05/10/2026

**Estado da missão: BLOCKED_EXTERNAL_CONNECTION. Produto NÃO declarado operacional ponta a ponta.**

## 1. Produto e cartão

É um produto Python/CLI experimental para gerar prospectivamente um único jogo de Mega-Sena: seis dezenas distintas entre 1 e 60, para o operador do projeto. O histórico validado alimenta Champion/Challenger; os scores congelados alimentam o seletor e o portfólio. “Cartão” é o produto principal de seis dezenas, criado por `smart_portfolio_pipeline.py`, vinculado ao freeze/ledger e persistido como `runtime/learning_epochs/<epoch>/SMART_<concurso>_PRIMARY_CARD.json` pelo processo completo. O operador devolve o cartão; a adjudicação e os relatórios consomem a previsão e o resultado. Portfólio com vários jogos é auxiliar.

Stack descoberta: Python, NumPy/pandas, River, componentes estatísticos e OR-Tools; processamento batch, sem servidor web identificado. Persistência principal em XLSX/JSON/ledger e commits no GitHub. Autoridade: `andrebarros78/SMART-MEGA`, `main`, runners efêmeros. Não houve aquisição de funcionalidades ou código de outro projeto.

## 2. Defeitos encontrados e evidência

| ID / gravidade | Encontrado → causa | Correção / estado | Evidência |
|---|---|---|---|
| D01 bloqueante | `smart_github_operator.py:240`: publicação rejeitava CRLF de evidências imutáveis como trailing whitespace | ✅ `f96aab6`: Git reconhece CRLF, continua rejeitando espaços finais reais | Git bare + nova clonagem LF/CRLF idênticos; caso com espaço rejeitado sem alterar remoto; JUnit |
| D02 alto | `smart_primary_card_selector.py:41,90`: pesos/objetivo não finitos podiam produzir PASS com NaN | ✅ `f96aab6`: validação de configuração, faixa normalizada e objetivo finitos | Casos inválidos e overflow aprovados |
| D03 alto | `smart_primary_card_selector.py:105`: ausência de combinação válida devolvia Top-6 que violava restrições | ✅ `f96aab6`: erro acionável; nenhum cartão inválido inventado | `test_selector_refuses_infeasible_card_instead_of_passing_invalid_fallback` |
| D04 alto | `smart_primary_card_selector.py:45`: coerção aceitava bool/fração como dezena | ✅ `f96aab6`: identificadores inteiros estritos | Casos `1.5` e `True` rejeitados |
| D05 alto | `smart_primary_card_selector.py:57`: chaves distintas podiam colidir após normalização | ✅ `f96aab6`: duplicação normalizada rejeitada | `test_selector_rejects_duplicate_normalized_number` |
| D06 médio | `smart_primary_card_selector.py:99`: expansão em passos de dois não tentava o limite ímpar configurado | ✅ `f96aab6`: tenta também o limite exato | `test_selector_expands_through_exact_odd_pool_limit` |
| D07 médio | `smart_github_operator.py:59,66,211`: subprocessos Git/operador sem limites | ✅ `f96aab6`: Git limitado a 60 s; ação a 4.800 s | Teste de timeout aprovado; workflow limitado a 90 min |
| D08 médio | `smart_github_operator.py:279`: exceções operacionais devolviam texto sem contrato de erro | ✅ `f96aab6`: JSON `{erro, causa, acao_sugerida}` | `test_operator_cli_failure_returns_standardized_error` |
| D09 alto | `smart_full_process_pipeline.py:349` / `smart_github_operator.py:265`: cartão standalone/resposta compacta omitiam identidade de execução | Implementado no PR #21, head `8dfdf65`; **NÃO VERIFICADO na suíte completa nem integrado** | 24 testes direcionados aprovados; nova fixture/CI pendentes |
| D10 alto | `smart_full_process_pipeline.py:349` / `smart_github_operator.py:265`: confiança conjunta de seis acertos não era exposta; não existe calibração demonstrada | PR #21 persiste/devolve `LOW`, `calibrated:false`, `UNPROVEN_PROSPECTIVE`, probabilidade null, garantia false; **pendente** | Rejeição de confiança fabricada/identidade divergente aprovada localmente; E2E pendente |
| D11 médio | `test_smart_operator_e2e_recovery.py:18,34`: testes denominados E2E substituíam etapas ou verificavam texto-fonte | PR #21 amplia fixture realista de 120 sorteios até cartão persistido, replay, resultado, Brier e duplicação; **NÃO VERIFICADO** | Implementação testável existente; runner ainda indisponível |
| D12 bloqueante operacional | `SMART_OPERATIONAL_LIFECYCLE.json:3`: lifecycle continua ADJUDICATED para 3062; sequência/recuperação até 3066 não foi persistida | `catch-up 3066` solicitado e repetição solicitada; **NÃO VERIFICADO** | Workflow `37366096200` falhou antes de iniciar qualquer passo: runner não adquirido |
| EX01 externo | GitHub Actions não atribuiu runner após várias tentativas; também afetou Repository Integrity | **BLOCKED_EXTERNAL_CONNECTION**; não é correção no código | Anotação do job e [incidente oficial](https://www.githubstatus.com/) |

## 3. Componentes

[Inventário completo de comandos, nove executores e 41 capacidades, com escopo de evidência](SMART_AUDIT_COMPONENTS_2026-10-05.md). O registro único existente foi preservado; 37 aliases nativos e quatro fontes em quarentena. Não foram ativadas referências externas nem criados agentes LLM.

## 4. Verificação realizada

- [PR #20](https://github.com/andrebarros78/SMART-MEGA/pull/20) integrado: `f96aab608ad020df86204b52721785059f504b22`.
- [CI de main](https://github.com/andrebarros78/SMART-MEGA/actions/runs/37364388633): **946 passed em 183,69 s**; job de certificação repetiu **946 passed em 139,39 s**. Zero falhas, erros ou skips.
- Certificação persistida no commit `93c6a8ee68b60fad8894650018d975179f15cf39`: `CONSTRUCTION_PROVEN`, startup `OK`, JUnit SHA-256 `52041fb0e242acf1dd4288eaeecd0c9502a6e4a5316263edc53f43ea65dd6a41`.
- Testes direcionados mais recentes, incluindo identidade/confiança do PR #21: **24 passed em 1,39 s** em ambiente efêmero. Isso não substitui a regressão nem o E2E no GitHub.
- [CI do PR #21](https://github.com/andrebarros78/SMART-MEGA/actions/runs/37367726502): pendente para head `8dfdf65a1335bafecb3e0c56961aaf22cc426c01`.
- [Recuperação de produção](https://github.com/andrebarros78/SMART-MEGA/actions/runs/37366096200): não executou. Anotação: “The job was not acquired by Runner of type hosted even after multiple attempts”. Repetição solicitada após confirmar ausência de passos executados e main inalterada.
- Cartão final de nova execução, Brier da nova fixture, todas as CLI `--help`, recuperação de produção e persistência após novo runner/redeploy: **NÃO VERIFICADOS**.
- Evidência científica existente: `SMART_MISSION_STATUS.json` mantém `UNPROVEN`/`INSUFFICIENT_EVIDENCE`. A auditoria histórica de 353 concursos mostra Brier dos candidatos entre aproximadamente 0,0919 e 0,0945, contra 0,09 uniforme; não demonstra vantagem. Nenhuma garantia de acerto foi criada.

## 5. Decisões conservadoras

Priorizar main sobre documentos/checkouts históricos e anexos; preservar hashes e bytes de arquivos históricos; rejeitar entrada/inviabilidade em vez de inventar cartão; manter quarentena declarada; não gerar cartões retrospectivos para concursos perdidos. Probabilidades marginais de inclusão somam seis; pesos da mistura somam um. Confiança desconhecida fica explícita, sem percentual inventado. Não foi selecionado/autorizado novo concurso de geração nesta missão.

## 6. Pendências e retomada exata

Não foi identificada necessidade de nova chave, compra ou permissão do usuário. O bloqueio é a atribuição de runners pelo GitHub. A seleção explícita do próximo concurso continua sendo uma decisão operacional, depois da recuperação.

1. Ler este relatório e conferir main/PR/jobs atuais; este documento é snapshot, não substitui estado real.
2. Aguardar/verificar a repetição de `37366096200`. Não duplicar recuperação se já houver job em execução. Após sucesso, exigir commit remoto, histórico até 3066, HOLD/next target 3067 e ausência de previsões retroativas.
3. Verificar `37367726502` no head exato `8dfdf65`; corrigir falhas técnicas reais e repetir testes necessários. Não usar como evidência runs supersedidos/cancelados.
4. **Somente após a recuperação terminar e os checks do PR #21 passarem**, integrar o PR; não mover main durante uma operação de publicação ativa. Renovar/verificar a certificação de main para o código integrado.
5. Ler as propriedades `fixture_e2e` e `cli_smoke` do novo JUnit canônico; registrar cartão, run_id, confiança, Brier, replay e evidência dos 28 comandos. O bypass temporal da fixture é explicitamente TEST_ONLY.
6. Executar `status` em novo runner; verificar os mesmos hashes/dados e startup OK. Exercitar `preflight` para o próximo target sem autorizar geração silenciosamente.
7. Atualizar este relatório somente com evidência. Não declarar SCOPE_SEALED, operação ponta a ponta ou vantagem científica enquanto faltar a prova correspondente.

Snapshot consultado em 05/10/2026, aproximadamente 17h11, Brasília. O GitHub registrou incidente de atribuição de runners em 05/10/2026 às 19h11/19h15 UTC.
