# SMART-MEGA — BASELINE OPERACIONAL GITHUB-NATIVE

**Arquivo:** `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`  
**Baseline ID:** SMART_GITHUB_NATIVE_BASELINE_2026-09-28  
**Reconciliada em:** 2026-10-05  
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

**Regra vigente de 21/10/2026 (seção 14):** o GitHub `andrebarros78/SMART-MEGA`, branch `main`, é a única autoridade persistente de código, estado operacional e evidências; **não é um requisito de hospedagem da CPU**. GitHub Actions é **proibido**. LMCP, VPS e PCs autorizados são executores **externos, transitórios e substituíveis** para testes e operações. Nenhum hostname, equipamento ou caminho local é pré-requisito permanente. O ponto de entrada existente para executar operações e publicar o resultado no GitHub é `smart_github_operator.py`, em checkout isolado da `main` com SHA e origem remota verificados. Provas só valem vinculadas ao commit testado e publicadas no GitHub; não inventar runner, JUnit, cartão ou certificação.

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


## 11. Missão executiva reconciliada — 05/10/2026

Por ordem atual de André, o objetivo é entregar o SMART-MEGA existente como produto preditivo operacional e integrado, com correções e evidências persistidas e verificadas no GitHub, em `andrebarros78/SMART-MEGA`, branch `main`.

Comprovar o ciclo completo: dados oficiais → sinais → qualidade e interpretação → pesos dinâmicos → previsão congelada antes do resultado → resultado observado → medição → calibração e aprendizado → próximo ciclo. Aprovação isolada de testes não substitui a prova desse fluxo.

Confrontar relatórios com o código e as autoridades atuais. Caminhos e hosts históricos não definem a moradia do projeto. **A execução é feita pelo operador existente `smart_github_operator.py` em executor externo autorizado disponível**, usando checkout transitório da `main`; a persistência, os commits, as provas e a continuidade pertencem exclusivamente ao GitHub. Não condicionar a geração de cartão ao PC Escola/B2, PC Casa ou GitHub Actions. Distinguir sempre disponibilidade do executor, prontidão do operador e prova de vantagem preditiva. Não abrir outra infraestrutura quando o operador existente atender ao objetivo.

Corrigir as causas das falhas nas funções existentes. Verificar agentes e skills pela função efetivamente executada; adquirir ou integrar recursos somente quando uma lacuna concreta impedir o objetivo, preservando o isolamento deste repositório e sem gastos não autorizados.

O fechamento exige os seis critérios da arquitetura com evidência atual: captação e qualidade; interpretação; conversão em pesos; calibração e adaptação; aprendizado e robustez; resultado comprovado. Registrar separadamente prontidão operacional e desempenho preditivo prospectivo. Não converter certificação de software em comprovação científica, nem gerar aprendizado ou cartão retrospectivo usando resultado conhecido.

Prosseguir pelas falhas técnicas corrigíveis até a entrega comprovada ou dependência externa irredutível, preservando comandos, resultados, commits, hashes e ponto de continuidade.

## 12. Fechamento 1 reconciliado — 06/10/2026

Por ordem explícita de André, executar integralmente: **DESCOBRIR ESTADO REAL → RECONCILIAR → TESTAR → CORRIGIR → RETESTAR → CONSOLIDAR → FECHAMENTO TÉCNICO/FUNCIONAL/OPERACIONAL/SEGURANÇA → GIT ADD → GIT COMMIT → VERSIONAR/TAG, SE APLICÁVEL → COMPROVAR BASELINE LIMPA → SELAR ESCOPO.**

Resolver primeiro conflitos, divergências, resíduos, duplicações e alterações incoerentes. Validar após reconciliação; corrigir falhas e retestar até aprovação. Somente consolidar, fechar e registrar no Git alterações já reconciliadas e validadas. A certificação deve vincular a regressão ao código efetivamente publicado e testado; metadados de certificação não substituem a validação anterior ao registro das correções.

Criar versão/tag quando houver marco aplicável, confirmar main remoto e git status limpo, sem alterações pendentes. Commit isolado não autoriza MISSION_PROVEN ou SCOPE_SEALED: exigir funcionamento, integração, persistência, recuperação e integridade. O selo técnico/funcional/operacional/segurança tem escopo explícito; o objetivo científico prospectivo permanece separado conforme §8 e §11.

Preservar a previsão real 3067 já FROZEN e sua prova causal original. Não reautorizar, regenerar, reescrever ou adjudicar usando resultado fictício. Renovação da certificação do software não altera a proveniência da geração original.

## 13. Histórico substituído

A política antiga de uso exclusivo de GitHub Actions e proibição de executores externos foi revogada por nova ordem expressa do proprietário em 21/10/2026. O texto anterior da seção 13 deixa de ser operacional.

## 14. Regra operativa vigente — SMART_GITHUB_CANONICAL_EXTERNAL_EXECUTION_NO_ACTIONS_20261021

Repositório canônico: `andrebarros78/SMART-MEGA`. Branch produtiva canônica: `main`.

**GitHub Actions é proibido**, inclusive para testes, CI, operação, contingência ou fallback. Nenhum arquivo YAML executável pode permanecer ativo em `.github/workflows/`.

**Executores externos são autorizados**, incluindo LMCP, VPS, PC Casa, PC Escola e PC Vendas, para trabalho isolado e temporário. São meios de execução; não constituem dependências permanentes do produto ou autoridade concorrente ao GitHub.

Para homologar: registrar o commit exato obtido do GitHub, ambiente, dependências do repositório, comandos, resultados completos (incluindo falhas e erros), JUnit e hashes; publicar evidências no repositório canônico. Não promover testes sintéticos ou históricos como prova da revisão atual. A produção somente muda após validação real, regressão e comparação com a baseline certificada.

A seção 14 prevalece sobre qualquer seção histórica, comentário, PR, skill ou memória conflitante. Nova mudança requer autorização explícita do proprietário e versionamento no GitHub.
