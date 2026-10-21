# SMART-MEGA

## Ordem executiva vigente — SMART_GITHUB_NATIVE_ONLY_20261021

**Repositório `andrebarros78/SMART-MEGA`, branch `main`: execução exclusivamente GitHub-native.** GitHub é a fonte de código, estado, versionamento, integração e evidências. Somente **GitHub Actions em runners hospedados pelo GitHub** executam o produto e os testes. A API/conector GitHub pode ler, editar e versionar, mas não substitui um teste de execução real.

**Rotas expressamente revogadas:** LMCP, VPS, PC Casa, PC Escola, PC Vendas, S-WMCP, runners próprios/`self-hosted`, SSH, redes federadas ou qualquer executor externo — também como solução temporária, contingência, fallback ou suposta autorização herdada. Não instalar dependências nem criar missões nesses ambientes para SMART-MEGA V6.

**Falha do GitHub Actions:** diagnosticar no GitHub; fazer somente edições e verificações permitidas pela API/conector GitHub, sem afirmar que o produto foi executado. Se não for possível testar no GitHub, registrar o gate `BLOCKED_GITHUB_ACTIONS`, manter `main` íntegra e jamais transferir a operação para outro host.

**Precedência:** esta ordem atual supersede qualquer permissão anterior para máquinas externas em documentos, prompts, memórias, roadmaps, relatórios ou outras branches. Mudança exige nova ordem explícita do proprietário e atualização versionada deste contrato em `main`. O verificador `python smart_github_native_policy.py` é obrigatório em todos os workflows e usa somente Python padrão.

SMART-MEGA é mantido no GitHub como sua única fonte canônica de projeto.

## Fonte canônica

- Repositório: `andrebarros78/SMART-MEGA`
- Branch canônica: `main`
- Política operacional: `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`
- Execução e testes do produto: exclusivamente GitHub Actions com runners hospedados pelo GitHub; código, estado e provas persistidos no GitHub

Chat, memória de IA, anexos, runners e cópias locais não substituem o estado persistido no GitHub.

## Começar

Leia:

1. `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`
2. `AI_START_HERE.md`
3. `AGENTS.md`

A baseline histórica `SMART_EXECUTIVE_PRIORITIZED_PLAN_BASELINE_2026-08-21.md` é consultada apenas quando relevante e somente no que não conflitar com a política atual.

## Execução mínima

Antes de qualquer ação: **PEDIDO OU INDISPENSÁVEL?**

Se não foi pedido e não é indispensável para atingir o objetivo atual, não executar.

Backup, snapshot, regressão ampla, refatoração, hardening, nova infraestrutura e documentação adicional não são etapas automáticas.

## Execução no GitHub

O desenvolvimento e a operação usam apenas este repositório. Os workflows em `.github/workflows/` executam CI e tarefas quando os runners estão disponíveis. Não utilizar LMCP, VPS, PC Casa, PC Escola, PC Vendas, runners `self-hosted` ou rede federada para executar SMART-MEGA V6. Somente runners hospedados pelo GitHub executam o produto e seus testes; GitHub `main` é a única moradia e autoridade persistente. Identificar o executor real, o commit e os hashes das provas, persistir as alterações no GitHub e verificar o commit remoto.

- `CI` e `Repository Integrity`: verificam o commit no GitHub.
- [SMART-MEGA GitHub Operator](https://github.com/andrebarros78/SMART-MEGA/actions/workflows/operator.yml): escolha manualmente `Run workflow` em `main`, informe a ação e o concurso quando necessário. `status` apenas observa; as demais ações seguem os contratos do operador.
- `adjudicate` e `review` exigem um arquivo de resultado ou revisão já versionado em `main`. `catch-up` pode receber um arquivo versionado. O operador verifica a entrada e só confirma alterações operacionais no GitHub quando a execução termina com sucesso.

Uma execução que falha não publica estado. Uma operação concluída precisa gerar commit em `main` e confirmar o SHA remoto. O token do workflow requer permissão `contents: write`; se uma regra de proteção impedir a gravação, o job falha sem declarar sucesso.

Testes devem ser proporcionais ao comportamento alterado. Regressão integral só é executada quando o impacto for sistêmico, quando um gate existente realmente a exigir para a mudança ou quando solicitada explicitamente.

## Contrato do cartão

O produto principal é um único cartão com seis dezenas distintas entre 1 e 60; o portfólio com vários jogos é auxiliar. Novos cartões persistidos incluem `run_id` (o identificador do epoch), `generated_utc`, estratégia/parâmetros do seletor e vínculos SHA-256 com o modelo congelado, o portfólio e os dados de origem. A resposta compacta de geração devolve o mesmo `run_id`, as seis dezenas e os hashes.

A confiança do cartão é explícita: nível `LOW`, `calibrated: false`, status `UNPROVEN_PROSPECTIVE`, `probability_six_hits: null` e `guaranteed: false`. O sistema ainda não tem probabilidade conjunta calibrada de seis acertos. Probabilidades marginais de inclusão de cada dezena, quando disponíveis, somam seis; pesos da mistura de sinais somam um. A auditoria confronta previsões congeladas com resultados e calcula Brier e acertos, sem converter aprovação de engenharia em vantagem preditiva.

Falhas do operador GitHub retornam JSON com `erro`, `causa` e `acao_sugerida`. As evidências da fixture ponta a ponta e de cada comando `--help` ficam nas propriedades do JUnit da regressão, com escopo de teste explícito.

## Operação autônoma

O agente/IA deve descobrir o estado real, fazer a menor correção suficiente, executar a validação necessária, corrigir falhas recuperáveis e persistir o resultado no GitHub sem transferir trabalho técnico rotineiro ao usuário.

Falha de ferramenta ou conector não constitui bloqueio enquanto existir rota técnica autorizada.

## Estado canônico

Estado que deva sobreviver à execução precisa estar persistido no GitHub. Uma alteração ocorrida apenas em runner, memória ou checkout local não é canônica.

Artefatos com SHA-256 declarado devem existir e corresponder ao hash declarado quando forem usados como autoridade.

## Regra científica

Nunca gerar ou reinterpretar retrospectivamente um cartão usando resultado já conhecido. Concursos sem geração prospectiva válida permanecem sem geração válida.

Os critérios 6/6 do projeto permanecem obrigatórios, mas devem ser perseguidos com a menor complexidade necessária. `MISSION_PROVEN` exige evidência fresca do estado canônico atual.
