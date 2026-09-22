# SMART-MEGA — MISSÃO DETALHADA DE EXECUÇÃO

**Projeto:** SMART-MEGA  
**Project ID:** `smart-mega-v6.3.1`  
**Host-alvo:** `DESKTOP-4T6AS9K`  
**Raiz canônica:** `C:\SMART-MEGA`  
**Versão operacional observada/reconciliada:** `6.3.2`  
**Branch de trabalho observada:** `fix/v6.3.1-portable-restore`  
**Estado científico:** `MISSION_ACTIVE / UNPROVEN` até existir prova prospectiva válida  
**Estado terminal de engenharia:** somente após campanha final comprovada  
**Regra terminal do projeto:** `RESULTADO < 6/6 -> CONTINUAR`; `6/6 SEM EVIDÊNCIA -> CONTINUAR`; `6/6 COM EVIDÊNCIA -> MISSION_PROVEN`.

---

## 1. Endereço oficial desta missão

O documento operacional detalhado desta missão deve permanecer em:

`C:\SMART-MEGA\SMART_MISSION_DETAILED_EXECUTION.md`

Este arquivo é o endereço canônico da missão detalhada. Ele deve ser consultado em toda retomada antes de mutações relevantes, em conjunto com:

- `C:\SMART-MEGA\AI_START_HERE.md`
- `C:\SMART-MEGA\AGENTS.md`
- `C:\SMART-MEGA\SMART_AI_EXECUTION_ENTRYPOINT.md`
- `C:\SMART-MEGA\SMART_CANONICAL_EXECUTION_ROADMAP.md`
- `C:\SMART-MEGA\SMART_EXECUTIVE_PRIORITIZED_PLAN_BASELINE_2026-08-21.md`
- `C:\SMART-MEGA\SMART_CANONICAL_ROOT.json`

---

## 2. Objetivo da missão

Fechar tecnicamente o SMART-MEGA de ponta a ponta, com uma arquitetura operacional e científica coerente, auditável, transacional, recuperável, idempotente, fail-closed e reproduzível, sem confundir prova de engenharia com prova de vantagem preditiva.

A missão deve produzir um sistema em que:

1. exista uma única autoridade operacional para lifecycle, target, epoch, rollover e estado corrente;
2. operações críticas sejam crash-safe, serializadas, idempotentes e recuperáveis;
3. sinais sejam captados, interpretados e convertidos em pesos dinâmicos somente com evidência válida;
4. nenhum resultado conhecido seja reutilizado retroativamente como se fosse informação pré-sorteio;
5. calibração e aprendizado sejam validados fora da amostra usada para ajuste sempre que aplicável;
6. qualquer prova stale, divergente ou falsa-positiva falhe de forma fechada;
7. toda promoção de modelo, peso, regra ou autoridade seja acompanhada de rastreabilidade e não regressão;
8. a baseline final possa ser reproduzida a partir do mesmo commit/tag e dos mesmos artefatos de autoridade;
9. a prova científica prospectiva permaneça independente da prova de construção/engenharia;
10. `MISSION_PROVEN` só seja emitido quando todos os critérios materiais tiverem evidência atual, coerente e vinculada à mesma release.

---

## 3. Regras invioláveis

### 3.1 Regra 6/6

- `0/6 a 4/6`: incompleto; continuar.
- `5/6`: inaceitável; identificar o critério faltante, corrigir e retestar.
- `6/6 sem comprovação`: não aprovado; continuar.
- `6/6 comprovado`: aprovado.

### 3.2 Separação engenharia x ciência

O fechamento da construção não prova vantagem preditiva. O estado científico deve continuar como `UNPROVEN` enquanto não existir uma sequência prospectiva, pré-registrada e livre de vazamento temporal que satisfaça o contrato científico.

### 3.3 Não retroatividade

É proibido:

- recalibrar uma previsão já congelada usando o resultado conhecido;
- reconstruir uma autoridade pré-sorteio depois do resultado;
- selecionar sinais retroativamente para fazer um concurso histórico parecer prospectivo;
- alterar histórico arquivado para melhorar métricas posteriores.

### 3.4 Não regressão

Toda alteração material segue:

`MEDIR ANTES -> ALTERAR -> MEDIR DEPOIS -> COMPARAR -> ACEITAR OU REVERTER/CORRIGIR`.

### 3.5 Fail-closed

Qualquer inconsistência material entre lifecycle, authority, epoch, transaction journal, fingerprint, certificação, governance, deficiency registry, Git ou artefatos científicos deve impedir emissão de estado verde terminal.

---

# 4. FASE P0 — FUNDAÇÃO DE AUTORIDADE, LIFECYCLE E TRANSAÇÃO

**Objetivo:** eliminar ambiguidade operacional e construir uma única linha de autoridade antes de evoluir contratos superiores.

## P0.1 — Identidade canônica

Confirmar que a execução ocorre no host e root corretos; rejeitar raiz concorrente; vincular versão, branch, HEAD e manifesto canônico.

**Saída exigida:** identidade única e verificável do alvo.

## P0.2 — Lifecycle operacional único

Lifecycle canônico:

`IDLE -> AUTHORIZED -> PREPARING -> PREPARED -> FREEZING -> FROZEN -> ADJUDICATED -> REVIEWED -> HOLD`

Somente o writer autorizado pode alterar o lifecycle.

**Saída exigida:** `SMART_OPERATIONAL_LIFECYCLE.json` coerente, versionado e validável.

## P0.3 — Arquivamento imutável de epoch adjudicada

Arquivar o epoch concluído, preservar hashes e impedir que um estado histórico encerrado permaneça concorrendo como epoch ativo.

**Saída exigida:** histórico imutável e ausência de colisão entre epoch concluído e estado atual.

## P0.4 — Rollover canônico

Implementar uma única operação de rollover que valide revisão, sequência de concurso, binding com histórico e archive o epoch antes da transição para HOLD do próximo target.

## P0.5 — Transaction journal

Journal obrigatório:

`BEGIN -> PREPARED -> COMMITTING -> COMMITTED`

ou, antes de `COMMITTING`, `ROLLED_BACK` quando a reversão ainda é segura.

O journal deve ser hash-chained e persistido de forma durável.

## P0.6 — Reserva e consumo de authority

Authority deve seguir:

`AUTHORIZED -> RESERVED(transaction_id) -> CONSUMED`

A authority não pode ser consumida antes de o ACTIVE correspondente existir e ser validado.

## P0.7 — Lock interprocesso

Operações mutáveis críticas devem possuir exclusão mútua interprocesso, com metadados de host, PID, target, epoch, transaction e recovery.

## P0.8 — CAS/revision

Documentos de estado críticos devem exigir revisão/hash esperado antes de sobrescrita, impedindo lost updates e writers concorrentes silenciosos.

## P0.9 — Separação de superfícies

Separar explicitamente:

- código;
- runtime;
- evidência;
- archive;
- contratos;
- autoridade.

Evitar discovery por globs amplos em produção.

## P0.10 — Portfolio como artefato de primeira classe

O portfolio final deve existir como artefato versionado, com binding de origem, geração e freeze.

## P0.11 — Adjudicação multicard

Adjudicação e métricas pós-resultado devem operar sobre todos os cartões/jogos do portfolio, e não apenas sobre um top-6 isolado.

## P0.12 — Eliminação de false-green por freshness

Autoridades armazenadas não podem permanecer verdes quando código, fingerprints, upstream proofs ou certificações mudarem.

## P0.13 — Deficiência D037 no root

Resolver semanticamente o defeito de sincronização no root; estados `OPEN/REOPENED` devem invalidar autoridades incompatíveis.

## P0.14 — Manifesto unificado de fingerprint

Criar uma autoridade única de fingerprints do código crítico usada pelos verificadores superiores.

### Critério de saída P0

P0 só é considerado implementado quando todos os itens P0.1–P0.14 possuírem prova estrutural corrente, sem promover o sistema para estado terminal e sem executar prematuramente a campanha final.

---

# 5. FASE P1 — DURABILIDADE, IDEMPOTÊNCIA, CONTRATOS E RECOVERY

**Objetivo:** tornar cada operação crítica repetível com segurança, recuperável após falha e governada por contratos versionados.

## P1.15 — Crash-safe writes

Todas as gravações críticas devem usar padrão durável:

1. criar arquivo temporário na mesma superfície;
2. escrever bytes completos;
3. flush;
4. `fsync`;
5. replace atômico;
6. limpar temporário residual.

Também devem ser revisados os writers de lock metadata para garantir que falha de persistência não deixe lock lógico/OS em condição incorreta.

**Estado conhecido:** implementação principal concluída; endurecimento específico do lock deve ser novamente verificado no P1.19.

## P1.16 — Eliminar/confinar globals mutáveis

Nenhum estado operacional mutável deve viver implicitamente em globals de módulo. Constantes declarativas e tabelas de transição podem permanecer quando imutáveis por contrato.

**Estado conhecido:** concluído estruturalmente.

## P1.17 — Idempotency keys

Cobrir obrigatoriamente:

- authorize;
- prepare;
- freeze;
- adjudicate;
- review;
- rollover/hold;
- terminal.

Semântica exigida:

`VALIDAR CHAVE -> VERIFICAR REPLAY -> EXECUTAR -> COMMITAR RESULTADO APÓS SUCESSO`

Conflito de uma mesma chave com payload diferente deve falhar fechado.

**Estado conhecido:** implementação estrutural das sete operações concluída; comportamento será validado na campanha final.

## P1.18 — Consolidar e versionar schemas/contracts

Criar um registro canônico que enumere:

- schema ID;
- versão;
- owner/writer;
- arquivo/superfície;
- consumidores;
- compatibilidade;
- política de migração;
- autoridade atual.

Remover ambiguidade entre versões concorrentes do mesmo contrato crítico.

**Critério de saída:** não existir schema operacional crítico sem owner/version explícitos.

## P1.19 — Startup invariants e reconciliation

Implementar verificação de inicialização antes de qualquer mutação relevante.

Verificar, no mínimo:

- root e host canônicos;
- lifecycle válido;
- compatibilidade entre lifecycle e ACTIVE;
- HOLD e próximo target;
- authority target/status;
- transações abertas;
- lock metadata e recuperação;
- archive do último epoch concluído;
- fingerprints críticos;
- colisões entre superfícies.

Resultado permitido:

- `READY`; ou
- `RECOVERY_REQUIRED`.

Não reparar destrutivamente inconsistências de maneira silenciosa.

## P1.20 — Separar estado científico do operacional

Definir fronteira formal:

**Operacional:** lifecycle, authority, transaction, lock, active epoch, freeze, rollover, release.  
**Científico:** sinais, pesos, calibração, ablação, holdout, métricas, evidência prospectiva, promoção challenger/champion.

Nenhum estado operacional pode ser interpretado como prova científica.

## P1.21 — Consolidar histórico 3060 sem retroatividade

Verificar que a reconciliação do concurso 3060:

- preserva source/result original;
- mantém hashes do archive;
- não reescreve previsão;
- não cria tentativa prospectiva retroativa;
- registra métricas multicard exatamente como observadas.

## P1.22 — Atualizar documentação executável e CLI

Atualizar entrypoints e documentação para refletir:

- lifecycle novo;
- journal;
- reservation/consumption;
- idempotência;
- startup reconciliation;
- recovery;
- rollover;
- diferença entre construction proof e scientific proof.

Nenhuma flag CLI deve ser inventada sem inspeção do source/argparse/tests.

## P1.23 — Full preflight

Criar preflight somente leitura/fail-closed que reúna os invariantes necessários antes de uma operação real.

O preflight deve apontar exatamente qual contrato falhou e não deve mascarar erro como warning verde.

## P1.24 — Invalidation/regeneration ordenada

Definir DAG explícito de dependências para invalidação e regeneração. Exemplo conceitual:

`critical code fingerprint -> regression evidence -> product certification -> governance -> global integrity -> release attestation -> terminal authority`

Durante P1, implementar o grafo e os verificadores, mas não regenerar prematuramente a cadeia final usando provas de teste antigas.

### Critério de saída P1

P1 encerra somente quando P1.15–P1.24 estiverem implementados e estruturalmente comprovados, sem executar ainda a campanha completa de testes finais. Estado esperado:

`P1_IMPLEMENTATION_COMPLETE_NO_FINAL_TESTS`.

---

# 6. FASE P2 — CONSOLIDAÇÃO DA CONSTRUÇÃO

## P2.25 — Higiene de repositório e superfícies

Classificar cada arquivo modificado/untracked como:

- source legítimo;
- test legítimo;
- authority gerada;
- runtime/state;
- archive;
- resíduo comprovadamente descartável.

Não executar `git add .` cegamente.

## P2.26 — Dependências e ambiente

Consolidar:

- Python/venv;
- requirements/lock;
- `pip check`;
- SBOM quando aplicável;
- fingerprints de dependência;
- comandos canônicos;
- configuração reproduzível.

## P2.27 — Arquitetura, migração, schema, recovery, docs e entrypoint

Revisar o conjunto completo como uma única arquitetura:

- caminhos;
- lifecycle;
- writers;
- locks;
- journal;
- CAS;
- idempotência;
- schemas;
- recovery;
- preflight;
- authority chain;
- documentação executável.

Resolver lacunas antes da campanha final.

## P2.28 — Marco de implementação

Emitir apenas:

`IMPLEMENTATION_COMPLETE / READY_FOR_FINAL_TESTS`

Este estado significa que a construção está pronta para ser provada; não significa `MISSION_PROVEN`.

---

# 7. CAMPANHA FINAL DE PROVA — PASSOS 29 A 40

A partir deste ponto os testes deixam de ser diferidos. Toda prova precisa ser produzida sobre a mesma baseline candidata.

## 29 — Unit e contract tests

Executar testes unitários e contratuais para lifecycle, CAS, journal, authority, idempotência, schemas, recovery e preflight.

**PASS:** zero falhas materiais.

## 30 — Full regression

Executar regressão completa em ambiente canônico e gerar JUnit atual ligado ao código corrente.

**PASS:** `0 failed / 0 errors`; nenhuma falha escondida, pulada ou reinterpretada.

## 31 — Concorrência

Exercitar writers concorrentes, locks, CAS e idempotência.

**PASS:** nenhum double-commit, lost update, duplicate freeze/adjudication/rollover ou authority race.

## 32 — Crash/recovery

Injetar interrupções seguras nas fronteiras transacionais:

- antes/depois de BEGIN;
- depois de PREPARED;
- em COMMITTING;
- antes/depois de replace atômico;
- reservation/consumption;
- lock acquisition/release.

**PASS:** recuperação determinística ou `RECOVERY_REQUIRED`, nunca falso sucesso.

## 33 — Restart

Reiniciar processo/sessão em estados intermediários conhecidos e provar que startup reconciliation identifica corretamente estado e ação permitida.

## 34 — Contaminação e stale proof

Alterar de forma controlada fingerprints/evidence em sandbox e confirmar que:

- certification invalida;
- governance invalida;
- global integrity invalida;
- deficiency abre/reabre quando material;
- terminal permanece bloqueado.

## 35 — E2E multicard

Executar o fluxo completo controlado:

`AUTHORIZE -> PREPARE -> FREEZE -> ADJUDICATE -> REVIEW -> ROLLOVER/HOLD`

incluindo portfolio multicard, sem usar o lifecycle live 3061 para testes destrutivos.

## 36 — Reprodutibilidade

Provar que a mesma release produz os mesmos contratos, fingerprints e artefatos determinísticos onde o contrato exigir determinismo.

## 37 — Regenerar cadeia de autoridades

Somente após os testes atuais passarem, regenerar em ordem:

1. JUnit atual;
2. canonical root binding;
3. critical code fingerprint;
4. product certification;
5. deficiency registry coerente;
6. governance;
7. global integrity;
8. continuity;
9. release attestation;
10. terminal engineering authority.

Todos os hashes devem apontar para a mesma baseline/HEAD.

## 38 — Git, commit, tag e baseline limpa

Após classificação:

1. stage somente arquivos aprovados;
2. commit técnico;
3. verificar commit;
4. criar tag coerente;
5. comprovar `git status` limpo;
6. assegurar que attestation aponta para o mesmo commit/tag;
7. se necessário, repetir regressão a partir do commit/tag final.

## 39 — Gate 6/6

Avaliar os seis critérios obrigatórios:

1. **Captação e qualidade** — sinais relevantes, atuais, íntegros e confiáveis;
2. **Interpretação** — contexto, intensidade, direção e ruído tratados corretamente;
3. **Conversão em pesos** — pesos dinâmicos proporcionais à utilidade comprovada;
4. **Calibração e adaptação** — ajustes por resultado com não regressão e holdout;
5. **Aprendizado e robustez** — aprendizado sem leakage, overfitting ou repetição de erro conhecido;
6. **Resultado comprovado** — melhor resultado global atingível dentro dos critérios, sem deficiência material conhecida.

Qualquer critério < 6/6 obriga nova rodada de correção e reteste.

## 40 — Estado terminal

`MISSION_PROVEN` somente quando:

- P0 completo;
- P1 completo;
- P2 completo;
- campanha 29–39 PASS;
- zero deficiência material aberta;
- authority chain atual e coerente;
- Git limpo e release reproduzível;
- nenhuma prova stale;
- nenhum falso-green;
- evidências ligadas à mesma baseline final.

Se qualquer condição falhar, permanecer em `MISSION_ACTIVE` e continuar.

---

# 8. Mapeamento com o roadmap canônico G00–G09

O roadmap original organiza o fechamento final em gates G00–G09. A execução P0/P1/P2 refina a construção necessária para esses gates.

| Gate canônico | Correspondência principal nesta missão |
|---|---|
| G00 TARGET IDENTITY | P0.1 + campanha final de identidade |
| G01 FORENSIC SNAPSHOT | início da campanha final antes de mutações de release |
| G02 FRESH REGRESSION | passos 29–30 |
| G03 BASELINE CLEAN | P2.25 + passo 38 |
| G04 AUTHORITY CHAIN | P1.24 + passo 37 |
| G05 DEFICIENCY TRUTH | P0.12–P0.13 + passo 34 |
| G06 RUNTIME CONSISTENCY | P0.2–P0.8 + P1.19–P1.21 |
| G07 SECURITY DR | P2.26 + campanha final de segurança/restore |
| G08 RELEASE REPRODUCIBLE | passos 36–38 |
| G09 CONSTRUCTION PROVEN | passos 39–40 |

O estado `CONSTRUCTION_PROVEN` do roadmap e o estado terminal `MISSION_PROVEN` deste plano não devem ser usados para elevar automaticamente `scientific_predictive_status` para PROVEN. A prova científica prospectiva permanece separada.

---

# 9. Estado atual conhecido da execução

## P0

P0.1–P0.14: implementação concluída com provas estruturais existentes.  
Lifecycle atual preservado em `HOLD`, target `3061`.  
A cadeia superior de certificação permanece propositalmente stale/fail-closed durante a construção.

## P1

- P1.15 crash-safe writes: concluído no núcleo; verificar endurecimento específico do lock em P1.19.
- P1.16 mutable globals: concluído.
- P1.17 idempotency: sete entrypoints críticos integrados estruturalmente.
- P1.18–P1.24: ainda devem ser executados e comprovados.

## P2

Não iniciado como fase formal nesta sequência.

## Campanha final

Não iniciada. Testes históricos anteriores não substituem prova da baseline atual.

**Estado correto neste ponto:** `MISSION_ACTIVE`.

---

# 10. Próxima sequência executiva obrigatória

1. Executar P1.18 — registry canônico de schemas/contracts.
2. Executar P1.19 — startup reconciliation + recovery, incluindo lock metadata.
3. Executar P1.20 — fronteira formal científico x operacional.
4. Executar P1.21 — prova não retroativa do histórico 3060.
5. Executar P1.22 — docs/CLI executáveis atualizados.
6. Executar P1.23 — preflight unificado fail-closed.
7. Executar P1.24 — DAG de invalidação/regeneração.
8. Emitir fechamento P1 sem testes finais.
9. Executar P2.25–P2.28.
10. Emitir `IMPLEMENTATION_COMPLETE / READY_FOR_FINAL_TESTS`.
11. Executar campanha 29–40 integralmente.
12. Se qualquer gate falhar: diagnosticar, corrigir, retestar e repetir até 6/6 comprovado.
13. Só então emitir `MISSION_PROVEN`.

---

# 11. Evidências finais mínimas

A missão terminal deve possuir, no mínimo:

- release attestation atual;
- JUnit atual ligado ao mesmo HEAD;
- canonical root atual;
- critical code fingerprint atual;
- product certification atual;
- global integrity atual;
- governance PASS;
- deficiency registry coerente, sem deficiência material aberta;
- continuity atual;
- secret scan atual;
- dependency/SBOM proof;
- backup externo e restore proof quando exigido pelo gate de DR;
- Git clean;
- commit e tag coerentes;
- execution log com comandos, timestamps, resultados e hashes;
- relatório final dos seis critérios 6/6;
- separação explícita entre construção comprovada e status científico prospectivo.

---

# 12. Fórmula terminal

```text
MISSION_PROVEN =
    P0_COMPLETE
AND P1_COMPLETE
AND P2_COMPLETE
AND FINAL_TEST_CAMPAIGN_PASS
AND MATERIAL_DEFICIENCIES == 0
AND AUTHORITY_CHAIN_CURRENT_AND_COHERENT
AND GIT_CLEAN_AND_RELEASE_REPRODUCIBLE
AND SIX_OF_SIX_PROVEN_WITH_EVIDENCE
```

Caso contrário:

```text
MISSION_ACTIVE -> DIAGNOSTICAR -> CORRIGIR -> RETESTAR -> REVALIDAR -> CONTINUAR
```

---

## Fonte e reconciliação

Este documento consolida o `SMART_CANONICAL_EXECUTION_ROADMAP.md` com a arquitetura executiva P0/P1/P2 adotada durante a remediação corrente. O roadmap original G00–G09 permanece a referência de gate de fechamento; a decomposição P0/P1/P2 detalha a ordem de implementação necessária antes da campanha final.
