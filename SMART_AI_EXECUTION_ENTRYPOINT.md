# SMART AI EXECUTION ENTRYPOINT

## Ordem executiva vigente — SMART_GITHUB_NATIVE_ONLY_20261021

**Repositório `andrebarros78/SMART-MEGA`, branch `main`: execução exclusivamente GitHub-native.** GitHub é a fonte de código, estado, versionamento, integração e evidências. Somente **GitHub Actions em runners hospedados pelo GitHub** executam o produto e os testes. A API/conector GitHub pode ler, editar e versionar, mas não substitui um teste de execução real.

**Rotas expressamente revogadas:** LMCP, VPS, PC Casa, PC Escola, PC Vendas, S-WMCP, runners próprios/`self-hosted`, SSH, redes federadas ou qualquer executor externo — também como solução temporária, contingência, fallback ou suposta autorização herdada. Não instalar dependências nem criar missões nesses ambientes para SMART-MEGA V6.

**Falha do GitHub Actions:** diagnosticar no GitHub; fazer somente edições e verificações permitidas pela API/conector GitHub, sem afirmar que o produto foi executado. Se não for possível testar no GitHub, registrar o gate `BLOCKED_GITHUB_ACTIONS`, manter `main` íntegra e jamais transferir a operação para outro host.

**Precedência:** esta ordem atual supersede qualquer permissão anterior para máquinas externas em documentos, prompts, memórias, roadmaps, relatórios ou outras branches. Mudança exige nova ordem explícita do proprietário e atualização versionada deste contrato em `main`. O verificador `python smart_github_native_policy.py` é obrigatório em todos os workflows e usa somente Python padrão.

CANONICAL_REPOSITORY=`andrebarros78/SMART-MEGA`  
CANONICAL_BRANCH=`main`  
CANONICAL_ROOT=`git rev-parse --show-toplevel`  
CANONICAL_POLICY=`SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`

Leia primeiro `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md` e obedeça sua precedência.

Regra de decisão antes de qualquer ação: **PEDIDO OU INDISPENSÁVEL?** Se não, não executar.

GitHub é o único canal canônico. Estado em chat, memória, anexo, runner ou checkout local só se torna autoridade quando persistido no GitHub.

O agente conduz autonomamente a execução técnica rotineira, usa a menor correção suficiente, valida proporcionalmente ao risco, corrige os próprios erros e persiste o resultado. Falha recuperável de ferramenta/conector não deve ser transferida ao usuário.

`SMART_EXECUTIVE_PRIORITIZED_PLAN_BASELINE_2026-08-21.md` é referência histórica/científica somente no que não conflitar com a baseline atual e deve ser consultado apenas quando relevante à tarefa.

Não exigir `DESKTOP-4T6AS9K`, `C:\SMART-MEGA` ou qualquer host/path físico fixo.
