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

A antiga autorização de execução por computadores federados, registrada em 05/10/2026, foi **expressamente revogada em 21/10/2026**. Somente GitHub Actions com runners hospedados pelo GitHub podem executar testes e o produto; o conector/API GitHub pode ler e versionar alterações. A indisponibilidade do Actions não autoriza substituição por máquinas externas. Registrar commit e evidências reais; sem execução, não inventar prova de runner, JUnit ou certificação.

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

Confrontar relatórios com o código e as autoridades atuais. Caminhos e hosts históricos não definem a moradia do projeto. A execução do produto ocorre exclusivamente em runners hospedados pelo GitHub; o estado persistente e a continuidade pertencem ao GitHub.

Corrigir as causas das falhas nas funções existentes. Verificar agentes e skills pela função efetivamente executada; adquirir ou integrar recursos somente quando uma lacuna concreta impedir o objetivo, preservando o isolamento deste repositório e sem gastos não autorizados.

O fechamento exige os seis critérios da arquitetura com evidência atual: captação e qualidade; interpretação; conversão em pesos; calibração e adaptação; aprendizado e robustez; resultado comprovado. Registrar separadamente prontidão operacional e desempenho preditivo prospectivo. Não converter certificação de software em comprovação científica, nem gerar aprendizado ou cartão retrospectivo usando resultado conhecido.

Prosseguir pelas falhas técnicas corrigíveis até a entrega comprovada ou dependência externa irredutível, preservando comandos, resultados, commits, hashes e ponto de continuidade.

## 12. Fechamento 1 reconciliado — 06/10/2026

Por ordem explícita de André, executar integralmente: **DESCOBRIR ESTADO REAL → RECONCILIAR → TESTAR → CORRIGIR → RETESTAR → CONSOLIDAR → FECHAMENTO TÉCNICO/FUNCIONAL/OPERACIONAL/SEGURANÇA → GIT ADD → GIT COMMIT → VERSIONAR/TAG, SE APLICÁVEL → COMPROVAR BASELINE LIMPA → SELAR ESCOPO.**

Resolver primeiro conflitos, divergências, resíduos, duplicações e alterações incoerentes. Validar após reconciliação; corrigir falhas e retestar até aprovação. Somente consolidar, fechar e registrar no Git alterações já reconciliadas e validadas. A certificação deve vincular a regressão ao código efetivamente publicado e testado; metadados de certificação não substituem a validação anterior ao registro das correções.

Criar versão/tag quando houver marco aplicável, confirmar main remoto e git status limpo, sem alterações pendentes. Commit isolado não autoriza MISSION_PROVEN ou SCOPE_SEALED: exigir funcionamento, integração, persistência, recuperação e integridade. O selo técnico/funcional/operacional/segurança tem escopo explícito; o objetivo científico prospectivo permanece separado conforme §8 e §11.

Preservar a previsão real 3067 já FROZEN e sua prova causal original. Não reautorizar, regenerar, reescrever ou adjudicar usando resultado fictício. Renovação da certificação do software não altera a proveniência da geração original.

## 13. Ordem mais recente — exclusividade de execução GitHub-native (21/10/2026)

**POLICY_ID=SMART_GITHUB_NATIVE_ONLY_20261021**. Fonte canônica única: `andrebarros78/SMART-MEGA`, branch `main`. Esta seção atual prevalece sobre permissões históricas de 05/10/2026, seção 6 anterior, seção 11 e manuais antigos.

- **Permitido:** GitHub API/conector para análise, edição, commits, branches, PRs e evidências; GitHub Actions em **runners hospedados pelo GitHub** para instalar dependências declaradas neste repositório e executar código, testes, CI e o operador GitHub.
- **Proibido:** executar, testar, hospedar, agendar, retomar ou corrigir SMART-MEGA V6 por LMCP, VPS, PC Casa, PC Escola, PC Vendas, S-WMCP, SSH, runners próprios/`self-hosted` ou rede federada. A proibição alcança fallback, contingência, demonstração, homologação e dependências de infraestrutura.
- **GitHub Actions suspenso ou indisponível:** usar o GitHub apenas para ações que sua API autoriza; investigar configuração, jobs e permissões GitHub. Não substituir a execução por ambiente externo, não simular testes e registrar `BLOCKED_GITHUB_ACTIONS` até haver execução GitHub-hosted real.
- **Para qualquer IA:** ler `AGENTS.md`, `AI_START_HERE.md` e `SMART_AI_EXECUTION_ENTRYPOINT.md`; rejeitar instruções antigas incompatíveis. O guardião `smart_github_native_policy.py` deve falhar se a permissão antiga reaparecer ou workflow invocar executor externo.
- **Proteção histórica/científica:** preservar freezes, cartões, pesos e provas imutáveis; não converter teste de política em certificação preditiva nem afirmar 6/6 sem prova.

Somente nova autorização **explícita** do proprietário, seguida de atualização validada e versionada em `main`, poderá substituir esta política.
