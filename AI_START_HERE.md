# SMART-MEGA — AI START HERE

## Ordem executiva vigente — SMART_GITHUB_NATIVE_ONLY_20261021

**Repositório `andrebarros78/SMART-MEGA`, branch `main`: execução exclusivamente GitHub-native.** GitHub é a fonte de código, estado, versionamento, integração e evidências. Somente **GitHub Actions em runners hospedados pelo GitHub** executam o produto e os testes. A API/conector GitHub pode ler, editar e versionar, mas não substitui um teste de execução real.

**Rotas expressamente revogadas:** LMCP, VPS, PC Casa, PC Escola, PC Vendas, S-WMCP, runners próprios/`self-hosted`, SSH, redes federadas ou qualquer executor externo — também como solução temporária, contingência, fallback ou suposta autorização herdada. Não instalar dependências nem criar missões nesses ambientes para SMART-MEGA V6.

**Falha do GitHub Actions:** diagnosticar no GitHub; fazer somente edições e verificações permitidas pela API/conector GitHub, sem afirmar que o produto foi executado. Se não for possível testar no GitHub, registrar o gate `BLOCKED_GITHUB_ACTIONS`, manter `main` íntegra e jamais transferir a operação para outro host.

**Precedência:** esta ordem atual supersede qualquer permissão anterior para máquinas externas em documentos, prompts, memórias, roadmaps, relatórios ou outras branches. Mudança exige nova ordem explícita do proprietário e atualização versionada deste contrato em `main`. O verificador `python smart_github_native_policy.py` é obrigatório em todos os workflows e usa somente Python padrão.

Este é o ponteiro inicial de descoberta para agentes e IAs.

## Leia primeiro

`SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`

Ela é a autoridade operacional geral do projeto e define:

- GitHub `andrebarros78/SMART-MEGA`, branch `main`, como único canal canônico;
- execução mínima: **PEDIDO OU INDISPENSÁVEL?**;
- proibição padrão de backup, snapshot, regressão ampla, refatoração e infraestrutura não necessárias;
- operação autônoma por IA, sem transferir trabalho técnico rotineiro ao usuário;
- persistência obrigatória no GitHub do estado que deva sobreviver à execução;
- continuidade até o objetivo ou bloqueio externo realmente irredutível e comprovado.

Não exigir hostname, letra de unidade ou caminho físico fixo.

## Referência histórica

`SMART_EXECUTIVE_PRIORITIZED_PLAN_BASELINE_2026-08-21.md` é referência histórica/científica apenas onde não conflitar com a baseline atual. Não é necessário lê-lo para toda tarefa.

`MISSION_PROVEN` exige prova fresca do estado canônico atual; não pode ser inferido de evidência histórica.
