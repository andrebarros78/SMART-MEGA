# SMART-MEGA — BASELINE OPERACIONAL GITHUB-NATIVE

**Arquivo:** `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`  
**Baseline ID:** SMART_GITHUB_NATIVE_BASELINE_2026-09-28  
**Reconciliada em:** 2026-10-03  
**Status:** AUTORIDADE OPERACIONAL GERAL DO PROJETO  
**Repositório canônico:** `andrebarros78/SMART-MEGA`  
**Branch canônica:** `main`

## 1. Autoridade canônica única

O único canal canônico do projeto é o GitHub, no repositório `andrebarros78/SMART-MEGA`, branch `main`.

Chat, memória de IA, anexos, cópias locais, worktrees, runners, arquivos temporários e saídas de conectores são apenas meios de trabalho. Nada neles se torna estado, regra, prova ou artefato canônico enquanto não estiver persistido no GitHub.

Dados externos oficiais podem ser usados como entrada e evidência, mas não substituem o estado do projeto no GitHub.

Em conflito entre fontes, `main` prevalece, salvo ordem explícita atual do usuário. Uma nova ordem só passa a integrar a autoridade persistente do projeto depois de reconciliada e gravada no GitHub.

## 2. Precedência

Aplicar nesta ordem:

1. ordem explícita atual do usuário;
2. esta baseline;
3. demais arquivos atuais em `main`;
4. baselines e planos históricos, somente no que não conflitar;
5. convenções genéricas de engenharia.

Esta baseline supersede regras históricas que imponham host/path fixo, backup, snapshot, restore drill, regressão ampla/integral, hardening, documentação adicional, nova infraestrutura ou outra cerimônia sem necessidade concreta para o objetivo atual.

## 3. Regra soberana de execução mínima

Antes de qualquer ação, alteração, ferramenta, arquivo ou comando, aplicar:

**PEDIDO OU INDISPENSÁVEL?**

A ação deve ter sido explicitamente pedida pelo usuário ou ser indispensável para concluir exatamente o objetivo pedido. Se nenhuma condição for verdadeira, **não executar**.

São proibidos por padrão, salvo pedido explícito ou necessidade técnica comprovada e imediata:

- backup, cópia preventiva e snapshot;
- branch de segurança criada apenas por precaução;
- regressão ampla/integral e suíte adicional de testes;
- refatoração não necessária;
- hardening genérico;
- nova arquitetura, banco, serviço, fila ou camada;
- nova pipeline ou dependência;
- documentação extra;
- reorganização cosmética;
- otimização prematura.

Entre soluções corretas, escolher obrigatoriamente a que usa menos arquivos, menos código, menos componentes, menos dependências, menos etapas e menos trabalho humano.

A busca por 6/6 não autoriza complexidade por si só. Cada mecanismo adicional precisa resolver uma deficiência material concreta que impeça o objetivo.

## 4. Operação autônoma por IA

O agente/IA é responsável por conduzir sozinho o trabalho técnico rotineiro até o objetivo: descobrir estado, diagnosticar, decidir a menor correção, editar, executar validação necessária, corrigir falhas, persistir no GitHub e verificar o resultado.

Não transferir ao usuário comandos, edição de arquivos, investigação, escolha técnica rotineira, recuperação de falha de ferramenta ou manutenção que o agente consiga executar com os recursos autorizados.

Falha de conector, sessão, runner ou ferramenta não é bloqueio terminal. O agente deve tentar outra rota técnica autorizada, reconsultar a autoridade GitHub, executar de forma idempotente e continuar.

Somente uma dependência externa realmente inacessível ao agente — por exemplo autorização humana obrigatória, credencial não disponível, pagamento, ação física ou permissão externa irredutível — pode exigir intervenção humana. Antes disso, o agente deve esgotar as rotas técnicas autorizadas e apresentar evidência objetiva do bloqueio.

O agente nunca deve inventar credenciais, contornar autorização ou declarar sucesso sem prova.

Erro introduzido pelo próprio agente deve ser diagnosticado e corrigido pelo próprio agente; não deve virar tarefa para o usuário.

## 5. Validação proporcional ao risco

Validar a mudança com o menor teste capaz de provar o comportamento alterado.

- mudança documental: verificar conteúdo, links/pointers e commit resultante;
- mudança localizada de código: teste focado no comportamento afetado;
- mudança transversal: ampliar testes somente até cobrir o impacto real;
- regressão integral: somente quando o impacto for realmente sistêmico, quando já for gate obrigatório existente para aquela mudança, ou quando o usuário pedir explicitamente.

Não criar novos testes ou gates apenas para satisfazer uma ideia abstrata de robustez.

PASS histórico não prova mudança nova. A evidência usada para aprovação deve corresponder ao mesmo commit que contém a alteração relevante.

## 6. Identidade e portabilidade

A identidade operacional é determinada por:

1. repositório `andrebarros78/SMART-MEGA`;
2. `main` como baseline canônica;
3. commit Git explicitamente identificado para cada prova;
4. root local resolvida dinamicamente pelo Git top-level do checkout atual;
5. nenhuma dependência normativa de hostname, letra de unidade ou caminho físico.

`DESKTOP-4T6AS9K` e `C:\SMART-MEGA` são apenas proveniência histórica e não são requisitos operacionais.

Não usar hosts Windows ou Linux persistentes para desenvolver ou operar o projeto. Os jobs efêmeros do GitHub Actions servem apenas como execução gerenciada pelo GitHub. Alterações operacionais bem-sucedidas precisam ser gravadas em `main` e verificar o commit remoto; falhas deixam o estado canônico intacto.

## 7. Estado operacional

Estado canônico que precise sobreviver à execução deve ser persistido no GitHub. Estado existente apenas em memória, workspace, runner ou arquivo local não persistido não é autoridade.

`SMART_ACTIVE_EPOCH.json` e demais artefatos operacionais só têm autoridade quando presentes na baseline canônica aplicável e coerentes com seus contratos. Arquivos com hash declarado devem corresponder ao conteúdo declarado.

Uma execução não pode avançar silenciosamente em ambiente efêmero e depois deixar `main` apontando para estado anterior.

## 8. Segurança científica

É proibido fabricar desempenho, prova ou cartão retrospectivo usando resultado já conhecido.

Concursos perdidos devem ser tratados como perdidos/sem geração válida conforme o contrato operacional; nunca preenchidos retrospectivamente para criar aparência de operação prospectiva.

Os seis critérios do projeto permanecem:

1. captação e qualidade;
2. interpretação;
3. conversão em pesos;
4. calibração e adaptação;
5. aprendizado e robustez;
6. resultado comprovado.

`6/6` é requisito de qualidade e evidência da arquitetura; não é promessa de seis acertos em loteria.

## 9. Regra de continuidade

O agente não encerra em análise quando existe correção técnica executável dentro do escopo e das permissões disponíveis.

Fluxo padrão:

**descobrir -> corrigir o mínimo -> validar o necessário -> persistir no GitHub -> verificar -> continuar**

`MISSION_PROVEN` somente pode ser declarado com evidência fresca correspondente ao estado canônico atual. Se houver deficiência material conhecida, continuar a correção sem expandir o escopo além do necessário.

## 10. Documentos históricos e externos

`SMART_EXECUTIVE_PRIORITIZED_PLAN_BASELINE_2026-08-21.md` permanece como referência histórica e científica apenas no que não conflitar com esta baseline.

Roadmaps, anexos ou documentos mantidos fora do GitHub são referências de trabalho, não autoridade canônica. Se uma regra externa precisar governar o projeto, ela deve ser reconciliada em `main`.
