# AGENTS.md — SMART-MEGA

## Ordem executiva vigente — SMART_GITHUB_CANONICAL_EXTERNAL_EXECUTION_NO_ACTIONS_20261021

GitHub andrebarros78/SMART-MEGA, branch main: autoridade canônica exclusiva de código, versionamento, integração, estado e evidências.

GitHub Actions é PROIBIDO. Remover todos os workflows executáveis de .github/workflows. Não executar GitHub Actions nem utilizá-lo como fallback.

Executores externos autorizados: LMCP, VPS, PC Casa, PC Escola, PC Vendas e outros executores autorizados podem realizar testes, compilação e homologação temporariamente e isoladamente. Nenhum executor externo é dependência permanente ou autoridade canônica. Vincular recibos ao SHA do GitHub, preservar resultados e provas no repositório.

A política substitui SMART_GITHUB_NATIVE_ONLY_20261021 e todas as orientações anteriores conflitantes. Nenhuma certificação, merge ou promoção automática sem testes reais vinculados ao commit.
Todos os agentes e IAs que atuarem neste repositório devem começar por:

1. `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`
2. `AI_START_HERE.md`

## Autoridade

- Único canal canônico: GitHub
- Repositório: `andrebarros78/SMART-MEGA`
- Branch canônica: `main`
- Root local: Git top-level do checkout atual

Chat, memória, anexos, runners e cópias locais não são autoridade enquanto não forem persistidos no GitHub.

## Regra operacional

Aplicar antes de qualquer ação: **PEDIDO OU INDISPENSÁVEL?**

Se não foi pedido e não é indispensável ao objetivo, não fazer.

Backup, snapshot, regressão ampla, refatoração, hardening, nova infraestrutura, documentação adicional e outras cerimônias são proibidos por padrão. Só entram por ordem explícita ou necessidade técnica concreta.

O agente deve executar autonomamente decisões e tarefas técnicas rotineiras, corrigir os próprios erros e persistir o resultado no GitHub. Falha de ferramenta/conector não é bloqueio enquanto existir rota técnica autorizada.

Planos históricos só valem no que não conflitar com a baseline GitHub-native atual. Não criar plano concorrente. Não promover PASS antigo como prova atual. `MISSION_PROVEN` somente com evidência fresca do estado canônico atual.

## Fronteira dos eventos de negócio do V6 — 2026-11-13

- **Autoridade de domínio exclusiva:** o SMART-MEGA V6 mantém seus próprios resultados, previsões, adjudicações, avaliações, pesos, histórico e eventos. O repositório `andrebarros78/SMART-MEGA` e seus fluxos internos são os únicos destinos admissíveis; `main` continua sendo a autoridade publicada após integração aprovada.
- **Pesquisa ≠ operação oficial:** eventos experimentais devem ser registrados em `evidence/research/<concurso>/SMART_V6_NATIVE_EVENT_<concurso>.json`, vinculados aos arquivos e hashes originais pré-resultado e pós-resultado. A operação oficial continua exclusivamente sob os comandos, estados e validações existentes de `smart_operator`, `smart_transaction_journal` e demais módulos V6; um evento de pesquisa nunca altera o histórico canônico por si só.
- **Executores ≠ registradores do domínio:** S-WMCP, WMCP, LMCP, VPS e computadores federados podem executar código, inspecionar arquivos e devolver recibos técnicos (exit code, SHA, JUnit, logs), mas suas filas e trilhas de eventos NÃO são barramentos de eventos, memória, histórico, aprendizado ou autoridade do SMART-MEGA V6.
- **Proibição objetiva:** nunca registrar evento de negócio do V6 por `ProjectRecordMissionEvidence`, `ProjectEvents`, `mission_checkpoint`, `mission_events` ou qualquer equivalente do executor. O identificador ou número de sequência de uma ferramenta externa nunca é o identificador ou a sequência de evento do V6. Recibos técnicos do executor são apenas evidência auxiliar que pode ser referenciada pelo próprio V6.
- **Falha fechada:** se não for possível persistir o evento no próprio V6 com integridade verificável, informar `V6_EVENT_NOT_PERSISTED` e conservar o trabalho pendente. Não substituir por registro externo nem promover registros de pesquisa a adjudicação oficial, pesos produtivos ou aprendizado.
- Não apagar nem reescrever trilhas técnicas históricas dos executores para ocultar erros anteriores. A correção consiste em registrar corretamente no V6 e desconsiderar os registros externos como fonte de verdade do domínio.
