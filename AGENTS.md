# AGENTS.md — SMART-MEGA

## Ordem executiva vigente — SMART_GITHUB_NATIVE_ONLY_20261021

**Repositório `andrebarros78/SMART-MEGA`, branch `main`: execução exclusivamente GitHub-native.** GitHub é a fonte de código, estado, versionamento, integração e evidências. Somente **GitHub Actions em runners hospedados pelo GitHub** executam o produto e os testes. A API/conector GitHub pode ler, editar e versionar, mas não substitui um teste de execução real.

**Rotas expressamente revogadas:** LMCP, VPS, PC Casa, PC Escola, PC Vendas, S-WMCP, runners próprios/`self-hosted`, SSH, redes federadas ou qualquer executor externo — também como solução temporária, contingência, fallback ou suposta autorização herdada. Não instalar dependências nem criar missões nesses ambientes para SMART-MEGA V6.

**Falha do GitHub Actions:** diagnosticar no GitHub; fazer somente edições e verificações permitidas pela API/conector GitHub, sem afirmar que o produto foi executado. Se não for possível testar no GitHub, registrar o gate `BLOCKED_GITHUB_ACTIONS`, manter `main` íntegra e jamais transferir a operação para outro host.

**Precedência:** esta ordem atual supersede qualquer permissão anterior para máquinas externas em documentos, prompts, memórias, roadmaps, relatórios ou outras branches. Mudança exige nova ordem explícita do proprietário e atualização versionada deste contrato em `main`. O verificador `python smart_github_native_policy.py` é obrigatório em todos os workflows e usa somente Python padrão.

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
