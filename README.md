# SMART-MEGA

SMART-MEGA é mantido no GitHub como sua única fonte canônica de projeto.

## Fonte canônica

- Repositório: `andrebarros78/SMART-MEGA`
- Branch canônica: `main`
- Política operacional: `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`
- Execução: GitHub Actions em runner efêmero gerenciado pelo GitHub

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

O desenvolvimento e a operação usam apenas este repositório e os workflows em `.github/workflows/`. Não há estação Windows ou Linux, VPS ou checkout persistente como ambiente do projeto. Os runners efêmeros do GitHub executam CI e tarefas; seu disco é descartável.

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
