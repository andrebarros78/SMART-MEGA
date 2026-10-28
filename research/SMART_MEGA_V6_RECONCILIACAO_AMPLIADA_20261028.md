# SMART-MEGA V6 — Reconciliação ampliada e homologação (28/10/2026)

**Escopo:** pesquisa isolada sobre o teto efetivo de pesos; nenhuma alteração ou promoção do modelo produtivo.  
**Executor auditado:** PC Casa `DESKTOP-JNS08PU`.  
**Autoridade GitHub:** `andrebarros78/SMART-MEGA`.

## Identidade canônica e limpeza

- `main`: `5f0fb091984cf37e3e411b700cde78b82d493f41`, verificada no GitHub e localmente, worktree limpo.
- `research/mega-v6-effective-cap-20261028`: `30e9484813e9ca75df32053db2fdcab04cf38307` antes deste relatório, verificada no GitHub e localmente, worktree limpo.
- Sem merge para `main`, sem alteração de pesos produtivos, sem edição de previsões congeladas, sem GitHub Actions.

## Homologação comprovada da branch de pesquisa

- Registros F01/F05/F10 reconciliados, F10 `PASS` em 11/11 verificações internas.
- Regressão focal ampliada: **34 testes aprovados, 0 falhas, 0 erros e 0 ignorados**; JUnit versionado em `research/effective_cap_homologation_20261028.xml`.
- Reteste posterior à publicação: **8 testes aprovados, 0 falhas**.
- Prova de escopo: `research/effective_cap_homologation_attestation_20261028.json`.
- Auditoria de componentes: 553 arquivos Python catalogados, 0 não classificados e 0 componentes produtivos obrigatórios inalcançáveis.
- Certificação de construção em `main`: `CONSTRUCTION_PROVEN` com 13/13 checks (verificação viva `require_current_code=True`). Ela **não certifica** o candidato de pesquisa.

## Tentativa de regressão integral — NÃO HOMOLOGADA

Em 28/10/2026, aproximadamente 14h44–14h50 (Brasília), foi iniciado o comando de pytest integral contra o checkout de pesquisa, com `--maxfail=5`, `-p no:cacheprovider`, `--disable-warnings`, saída separada e JUnit solicitado. O processo recebeu limitação de afinidade e prioridade para proteger o PC Casa.

- ID da execução: `ps-63e26e85ebe042d196bf0ab4dcfec0e7`.
- O log parcial mostrava apenas pontos de sucesso até o momento observado, mas **não existe resultado terminal**.
- JUnit final **não foi gerado**; portanto, não se pode afirmar 1786/1786 ou qualquer outro total integral.
- Processo cancelado de forma controlada e posteriormente comprovado sem filhos remanescentes.
- SHA-256 do log parcial local (143 bytes): `f7157b92124dfd5fd00fc67701bfe75eafe44a0cca7451da3ebf352c484aa49b`.
- A CPU do PC Casa estava em 100% antes e após o teste. O processo ficou em prioridade `Idle` e afinidade de um núcleo no ambiente governado.
- LMCP recusou execução Linux por `storage_pressure_command_blocked:85.1>=85.0`. Os nós remotos PC Escola e PC Vendas não estavam disponíveis como executores de comandos.

**Gate:** `FULL_REGRESSION_PENDING`. A aprovação técnica desta pesquisa permanece limitada ao escopo dos testes focalizados; não equivale à regressão integral da branch.

## Sobreposições e limites de integração

- PR #80 e PR #90 alteram ambos `SMART_COMPONENT_REACHABILITY_REGISTRY.json`, `SMART_CANONICAL_COMPONENT_REGISTRY.json` e `SMART_F10_DISCONNECTION_GATE.json`.
- PR #90 também modifica o motor, agente e gerador produtivos. PR #91 é a proposta de integração shadow dessas mudanças, ainda em rascunho em outro histórico Git.
- Não houve merge da PR #80, #90 ou #91 nesta intervenção, nem aprovação científica de seus candidatos.
- Comparação histórica do teto corrigido já documentada: 1.274 acertos na baseline vs. 1.268 na variante em 2.072 concursos. A melhora local em parte do holdout não sustenta promoção global.

## Critério de fechamento pendente

Reexecutar a suíte integral em executor com capacidade disponível; validar o JUnit completo, registrar o commit exato testado, reconciliar resultados/hashes sem autoproclamação, validar baseline limpa após a publicação e somente então decidir sobre homologação integral. A vantagem preditiva prospectiva continua `UNPROVEN`.

**STATUS:** `RECONCILED_CLEAN_RESEARCH_HOMOLOGATION_PASS__FULL_REGRESSION_PENDING__PREDICTIVE_UNPROVEN`.
