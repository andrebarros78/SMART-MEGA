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

## Local development location — owner order 2026-11-09

The **only authorized PC Casa SMART-MEGA V6 development root** is
`C:\New Projet\SMART-MEGA-V6-CANONICAL`.

- Create/update code, branches, worktrees, local scripts, test fixtures, caches
  and generated local development artifacts **only under this directory**.
  `main\` is the active checkout; isolated worktrees belong in `_worktrees\`.
- Never create another V6 checkout or run V6 development from
  `C:\Windows\Temp`, `C:\SMV6-*`, `C:\SMART-MEGA`, Desktop or
  another folder. Do not re-use previous temp copies as development sources.
- A historical `C:\SMART-MEGA` field in immutable authority documents is
  **provenance**, not a writable development path. Preserve old hashes and
  audit receipts; do not rewrite them to make a path policy appear satisfied.
- The `smart_canonical_identity.py` guard denies executable checkouts
  located outside the approved tree **on PC Casa**. A sandbox inside pytest is
  not a development worktree. Linux/VPS and other approved remote executors
  remain capable of running portable tests, not independent local development.
- GitHub `andrebarros78/SMART-MEGA` branch `main` remains the durable source.
  This local path policy must not be confused with any authorization to
  fast-forward stale work or merge unreviewed branches.
- No agent, chat or tool may silently weaken this rule. Changing it requires
  the owner's explicit direction and fresh RED/GREEN/regression tests.
