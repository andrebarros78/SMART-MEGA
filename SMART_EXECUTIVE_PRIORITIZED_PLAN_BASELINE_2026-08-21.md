# SMART-MEGA V6 — BASELINE EXECUTIVA EXCLUSIVA

**Baseline ID:** SMART_EXECUTIVE_PRIORITIZED_PLAN_BASELINE_2026-08-21  
**Data nominal solicitada da baseline:** 21/08/2026  
**Data real de instalação no sistema:** 21/09/2026  
**Status documental:** NORMATIVA / FONTE ÚNICA DO PLANO EXECUTIVO PRIORIZADO  
**Projeto:** SMART-MEGA V6  
**Host canônico operacional:** DESKTOP-4T6AS9K  
**Root canônica obrigatória:** `C:\SMART-MEGA`  
**Python canônico:** `C:\SMART-MEGA\.venv\Scripts\python.exe`  
**Caminho proibido/inexistente como root canônica:** `C:\SMART-MEGA V6`

> Esta baseline é a fonte normativa única do Plano Executivo Priorizado. Arquivos de descoberta como `AGENTS.md`, `AI_START_HERE.md` e `SMART_AI_EXECUTION_ENTRYPOINT.md` são somente ponteiros e não possuem autoridade para alterar este plano.

---

## 1. OBJETIVO

Garantir que qualquer IA, agente, operador automatizado ou processo de engenharia que atue no SMART-MEGA V6 consiga:

1. localizar inequivocamente o projeto correto;
2. identificar esta baseline como autoridade executiva;
3. executar o plano completo por prioridade;
4. não deixar módulo bloqueado por ausência de testes intermediários;
5. implementar e integrar toda a arquitetura antes da campanha de testes;
6. executar os testes somente na fase final;
7. somente declarar `MISSION_PROVEN` depois de todos os gates finais terem sido comprovados.

A regra operacional é:

`IMPLEMENTAR TUDO -> INTEGRAR TUDO -> FECHAR TODAS AS LACUNAS -> IMPLEMENTATION_COMPLETE -> TESTAR TUDO -> CORRIGIR -> RETESTAR -> REGRESSÃO -> CHAOS -> RECOVERY -> REPRODUTIBILIDADE -> AUTORIDADES FRESCAS -> BASELINE LIMPA -> 6/6 COMPROVADO -> MISSION_PROVEN`

**Interpretação obrigatória:** testes não podem bloquear implementação de módulos. Porém `MISSION_PROVEN` é um estado de prova e, portanto, somente pode ser emitido após a campanha final de testes e validações.

---

## 2. PROTOCOLO DE DESCOBERTA PARA QUALQUER IA

Ao iniciar trabalho no SMART-MEGA:

1. Confirmar que o host alvo é `DESKTOP-4T6AS9K`.
2. Confirmar que a root operacional é exatamente `C:\SMART-MEGA`.
3. Não usar `C:\SMART-MEGA V6` como root.
4. Ler integralmente este arquivo antes de executar alterações estruturais.
5. Tratar este arquivo como a única baseline executiva do plano.
6. Não substituir prioridades por interpretação própria.
7. Não executar pytest, regressão, sandbox, Monte Carlo, E2E, chaos ou campanha de testes durante P0–P2 de implementação.
8. Verificações estruturais mínimas necessárias para continuar a edição — existência de arquivo, parsing, import necessário, hash, leitura de estado — não são classificadas como campanha de testes.
9. Nenhum módulo deve ficar aguardando um teste intermediário para ser implementado.
10. Ao chegar a `IMPLEMENTATION_COMPLETE`, congelar o candidato e somente então iniciar a campanha final.
11. Qualquer falha final deve retornar a missão a `MISSION_ACTIVE`, corrigir a causa e repetir a validação pertinente.
12. Nunca emitir `MISSION_PROVEN` por inferência, intenção, documento antigo ou PASS armazenado sem comprovação fresca.

---

## 3. PLANO EXECUTIVO PRIORIZADO

### P0 — IDENTIDADE, AUTORIDADE E LIFECYCLE

**1. Congelar a identidade canônica do SMART-MEGA.**  
Fixar formalmente `DESKTOP-4T6AS9K` + `C:\SMART-MEGA` como identidade operacional. Eliminar referências operacionais ativas a roots concorrentes. Centralizar resolução de root, hostname e identidade Git em contrato único fail-closed.

**2. Criar uma única autoridade de lifecycle.**  
Unificar a fase operacional em máquina de estados canônica: `IDLE -> AUTHORIZED -> PREPARING -> PREPARED -> FREEZING -> FROZEN -> ADJUDICATED -> REVIEWED -> HOLD`. ACTIVE, HOLD e AUTHORITY tornam-se evidências subordinadas, não autoridades concorrentes.

**3. Resolver estruturalmente ACTIVE-N x HOLD-N+1.**  
Epoch adjudicado deve ser arquivado como histórico imutável. O ponteiro ativo não pode continuar representando concurso concluído quando o próximo HOLD já existe. Preservar evidências históricas byte a byte.

**4. Tornar rollover uma transação única.**  
Criar operação canônica de encerramento/rollover: validar adjudicação -> fechar evidências -> arquivar active -> gerar review -> gerar HOLD -> atualizar autoridade. Proibir writers paralelos de lifecycle.

**5. Implantar journal transacional.**  
Toda mutação crítica deve possuir `transaction_id`, estado anterior esperado, hashes de entrada e fases `BEGIN`, `PREPARED`, `COMMITTING`, `COMMITTED` ou `ROLLED_BACK`.

**6. Corrigir consumo prematuro de autorização.**  
Adotar `AUTHORIZED -> RESERVED(transaction_id) -> CONSUMED`, com recuperação de reserva após crash e sem consumo duplo.

**7. Adicionar exclusão mútua interprocesso.**  
Toda operação mutável crítica deve possuir lock exclusivo com host, PID, target, epoch, transaction ID e metadados de recuperação.

**8. Adicionar CAS/versionamento de estado.**  
Cada documento de autoridade deve ter revision/hash esperado. Escritas sobre revisão divergente devem falhar fechadas.

**9. Separar runtime, evidência e código.**  
Usar superfícies explícitas para código, runtime ativo, transactions, locks, epochs, evidência current/history e archive non-runtime. Produção não deve descobrir estado por glob amplo.

**10. Transformar portfólio no artefato final de primeira classe.**  
Criar contrato `SMART_PORTFOLIO_ARTIFACT` com portfolio_id, target, freeze SHA, source SHA, configuração, solver, game_id, dezenas, hashes e métricas. Champion top6 permanece evidência preditiva, não substituto do produto multicartão.

**11. Corrigir adjudicação e pós-resultado multicartão.**  
Calcular separadamente `champion_hits`, `hits_per_game`, `best_game_hits`, cobertura de união e exposição por dezena. Não recalibrar automaticamente pesos com base em um único concurso.

**12. Eliminar autoridades falsas-verdes.**  
Product Certification, Global Integrity, Agent Governance, Material Registry e Mission Status devem verificar freshness real, fingerprint, upstream hashes e código atual. PASS armazenado não é suficiente.

**13. Resolver D037 pela causa.**  
Status `OPEN` ou `REOPENED` invalida automaticamente autoridades incompatíveis. D037 somente pode ser marcado resolvido depois da causa estrutural ter sido removida e provada na fase final.

**14. Unificar fingerprint de código crítico.**  
Criar manifest canônico de superfícies críticas: entrypoints, contratos, schemas, requirements, configs, locks e módulos operacionais. Alteração material precisa modificar o fingerprint global.

### P1 — TRANSAÇÃO, IDEMPOTÊNCIA, CONTRATOS E RECUPERAÇÃO

**15. Tornar gravações críticas crash-safe.**  
Usar temp no mesmo volume, flush/fsync quando aplicável, hash antes de commit e replace atômico. Ponteiro nunca referencia artefato não durável.

**16. Fechar estado global do terminal executor.**  
Preferir contexto explícito por objeto. Globals legados devem ser confinados, protegidos pelo lock e restaurados deterministicamente.

**17. Padronizar idempotência.**  
Authorize, prepare, freeze, adjudicate, review, rollover e terminal devem aceitar chave idempotente derivada de target/epoch/transaction.

**18. Consolidar contratos e schemas.**  
Versionar documentos críticos e declarar required fields, invariantes, upstream hashes e transições válidas. Parser deve ser fail-closed.

**19. Introduzir invariantes de startup.**  
Antes de comando mutável, reconciliar root, journal, active/HOLD, authority, hashes, lock, target monotônico e dataset. Inconsistência produz `RECOVERY_REQUIRED`.

**20. Separar estado científico de estado operacional.**  
Ledger científico append-only, estado aprendido e evidências prospectivas não podem ser alterados por conveniência operacional.

**21. Consolidar histórico 3060 sem retroatividade.**  
Preservar freeze, portfolio, ledger, adjudicação e resultado oficial do 3060. Novos metadados somente podem referenciar hashes existentes.

**22. Atualizar documentação executável e CLI.**  
Remover suposições de root incorreta, target fixo ou versão antiga. Comando de status deve mostrar visão reconciliada única.

**23. Fazer preflight representar o estado inteiro.**  
Preflight deve avaliar identidade, lifecycle, journal, lock, authority, certification freshness, dataset/cutoff e janela temporal. Não deve corrigir automaticamente.

**24. Preparar invalidação e regeneração ordenada de provas.**  
A cadeia futura será: código/manifest -> regression authority -> Canonical Root -> Product Certification -> Global Integrity -> Governance -> Material Registry -> Mission/Continuity -> Release Attestation. Nesta fase, implementar geradores e verificadores; não emitir prova final ainda.

### P2 — HIGIENE E REPRODUTIBILIDADE DE BUILD

**25. Higienizar workspace e build surface.**  
Classificar caches, pycache, coverage, logs, patches aplicados, outputs auxiliares e backups. Produção não pode depender de cache ou arquivo temporário.

**26. Consolidar dependências e ambiente.**  
Garantir que venv, requirements e locks descrevem exatamente o runtime usado. Remover resolução implícita de dependência por sys.path externo.

**27. Finalizar código antes da suíte de testes.**  
Todas as alterações arquiteturais, migrations, schemas, recovery paths, documentação e entrypoints devem estar implementados. Não executar campanha de testes durante P0–P2.

### MARCO DE IMPLEMENTAÇÃO

**28. Emitir `IMPLEMENTATION_COMPLETE / READY_FOR_FINAL_TESTS`.**  
Inventariar arquivos modificados, calcular fingerprint do candidato e congelar alterações funcionais. Este estado não é `MISSION_PROVEN`.

### P0 FINAL — CAMPANHA DE PROVA

**29. Executar testes funcionais finais.**  
Rodar testes unitários/targeted de módulos alterados, contratos e integração do lifecycle. Falhou -> corrigir -> retornar a `MISSION_ACTIVE`.

**30. Executar regressão integral.**  
Gerar JUnit novo, comprovar zero failures/errors e skips não autorizados, além da cobertura exigida. A prova deve ser posterior ao último byte funcional alterado.

**31. Executar campanha de concorrência.**  
Disparar authorize/prepare/freeze/rollover concorrentes e comprovar exatamente um commit lógico.

**32. Executar campanha de crash/recovery.**  
Interromper cada boundary transacional e provar recuperação determinística após reinício.

**33. Executar restart e persistência.**  
Recriar processos e, quando aplicável, reiniciar host de teste. Estado reconstruído deve depender somente de persistência governada.

**34. Executar teste de contaminação.**  
Injetar stale authority, root concorrente, cache, HOLD incompatível, active antigo, dataset alterado, hash quebrado e journal incompleto. Todos devem falhar fechados.

**35. Executar E2E multicartão.**  
Executar ciclo completo sandbox desde dataset até portfolio, adjudicação, review e rollover, validando todos os cartões como produto final.

**36. Executar reprodutibilidade.**  
Em checkout limpo e ambiente reconstruído, usar mesmo commit, dataset, configurações e sementes; outputs determinísticos devem coincidir onde o contrato exige.

**37. Regenerar autoridades frescas.**  
Somente após todos os testes aprovados gerar JUnit canônico, Canonical Root, Product Certification, Global Integrity, Agent Governance, Material Registry, Mission Status/Continuity e Release Attestation.

**38. Consolidar Git e release.**  
Revisar diff, remover resíduos, git add, commit técnico, comprovar que o commit é o candidato testado, tag coerente e git status limpo.

**39. Executar Gate 6/6.**  
Confirmar simultaneamente: 1/6 captação e qualidade; 2/6 interpretação; 3/6 conversão em pesos; 4/6 calibração/adaptação; 5/6 aprendizado/robustez; 6/6 resultado comprovado. Exigir ausência de deficiência material, authority stale, lifecycle divergente ou dirty baseline.

**40. Estado terminal.**  
Somente com evidência fresca e todos os gates aprovados emitir `MISSION_PROVEN`. Qualquer falha mantém ou retorna a `MISSION_ACTIVE`.

---

## 4. REGRAS DE NÃO BLOQUEIO DURANTE IMPLEMENTAÇÃO

- Um módulo não pode aguardar pytest para que o próximo seja implementado.
- Dependências arquiteturais devem ser resolvidas pela ordem P0 -> P1 -> P2.
- Quando uma etapa exigir contrato ainda não existente, criar primeiro o contrato mínimo canônico e continuar.
- Quando uma etapa depender de artefato histórico, preservar o artefato e construir adaptação ao redor dele.
- Não alterar retrospectivamente freeze, portfolio ou ledger histórico para fazer a nova arquitetura parecer consistente.
- Não promover um PASS antigo para prova atual.
- Não recalibrar pesos por resultado isolado.
- Não mascarar bloqueio estrutural com fallback silencioso.
- Não criar segunda baseline concorrente.

---

## 5. ENDEREÇOS CANÔNICOS

| Finalidade | Endereço |
|---|---|
| Root SMART-MEGA | `C:\SMART-MEGA` |
| Baseline executiva | `C:\SMART-MEGA\SMART_EXECUTIVE_PRIORITIZED_PLAN_BASELINE_2026-08-21.md` |
| Entrada para IA | `C:\SMART-MEGA\AI_START_HERE.md` |
| Ponteiro de agentes | `C:\SMART-MEGA\AGENTS.md` |
| Ponteiro explícito SMART | `C:\SMART-MEGA\SMART_AI_EXECUTION_ENTRYPOINT.md` |
| Manifest da baseline | `C:\SMART-MEGA\SMART_EXECUTIVE_BASELINE_MANIFEST.json` |
| Python | `C:\SMART-MEGA\.venv\Scripts\python.exe` |

---

## 6. PRECEDÊNCIA

Em caso de conflito entre instruções internas do repositório relativas a este plano:

1. preservar dados/evidências imutáveis e regras de segurança;
2. esta baseline define a ordem executiva;
3. contratos canônicos de integridade/lifecycle definem invariantes técnicas;
4. arquivos de descoberta apenas apontam para esta baseline;
5. documentos antigos não substituem esta baseline sem uma migração explícita, versionada e autorizada.

---

## 7. CRITÉRIO DE CONCLUSÃO

`RESULTADO < 6/6 -> CONTINUE`

`6/6 SEM EVIDÊNCIA FRESCA -> CONTINUE`

`IMPLEMENTATION_COMPLETE -> INICIAR CAMPANHA FINAL`

`TODOS OS TESTES/GATES PASS + BASELINE LIMPA + PROVAS FRESCAS -> MISSION_PROVEN`

Esta baseline não autoriza declarar sucesso apenas porque a implementação terminou.
