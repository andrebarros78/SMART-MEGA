# SMART-MEGA V6 — Integração agente/skill/SDK ao consumidor de cartões

Data: 2026-10-13 (America/Sao_Paulo). Repositório canônico: `andrebarros78/SMART-MEGA`. Este documento é um **registro de engenharia**, não autorização de produção preditiva, alteração de congelamento ou declaração de superioridade estatística.

## Estado canônico confirmado

- Baseline de produção após reconciliação: `main` no commit `34cf2761a047646ddb8824fbf0f7ec81a3fc869f`.
- Autoridades: `product_certification=current`, `governance=current`, `global_integrity=current`; `smart_authority_freshness.audit` = **PASS** no checkout federado autenticado.
- Preflight do concurso 3070: **ALREADY_FROZEN**, sem mutação nem uso de resultado, epoch `operator-3070-ee1bc13734e4-20261013T225858165681Z`.
- As seis dezenas anteriormente congeladas permanecem 10, 11, 27, 38, 43, 53. Este documento não modifica a previsão.
- O registro de deficiências materiais foi restaurado **em bytes exatos** ao documento vinculado pelas provas `SMART_GLOBAL_INTEGRITY_PROOF.json` e `SMART_P14_INDEPENDENT_AUDIT_CURRENT.json`; alteração do registro isoladamente torna o operador `STALE_OR_BLOCKED`.

## Matriz de consumo e fronteiras comprovadas

| Superfície | Inventário | Consumo/autoridade comprovada |
|---|---:|---|
| Agentes determinísticos nativos | 9 | Executam sondas de validação nos gates pré/pós-freeze, sem autoridade direta para alterar pesos |
| Agentes supervisores | 2 | Verificam arquitetura/aquisições; governança separada, não são LLMs autônomos |
| Capacidades de metodologia/skills | 41 | 37 invocações de adaptadores de sondas nativas; 4 somente referência |
| Skills/fontes externas | 21 | Quarentena: zero execuções diretas comprovadas; não promover indiscriminadamente |
| Referências metodológicas externas | 3 | Adquiridas e hashes reconciliados; sem dependência de runtime |
| Dependências diretas `requirements.txt` | 15 | As 15 versões fixadas foram encontradas no venv Linux federado; **instalação não é prova de participação na decisão** |
| SDKs verificados no gate experimental | 5 | Pandas (histórico), River (drift/challenger), OR-Tools (portfólio), Pydantic (handoff), pypdf (cronograma) |
| Provedor externo LLM | 0 | Nenhum contrato aprovado nem ganho causal validado; não supor on-line |

## Caminho de cartão efetivamente observado

`history≤3069 → pre-freeze gate → fine-tuning → champion/challenger → champion.aggregate_scores → rescue condicional → seletor de cartão único → freeze/portfólio → post-freeze gate → artefato do cartão`.

O `challenger` registra 12 pesos dinâmicos, mas **esses pesos não entram diretamente na escolha do cartão** sem uma promoção comprovada. As 37 skills nativas são *aliases para sondas*, não 37 serviços externos operacionais. As metodologias e os SDKs não podem receber autoridade preditiva por mera presença no registro.

## Integração experimental já construída

Branch isolada: `integration/card-consumer-evidence-20261013`.

- `smart_consumer_integration.py`: valida de forma fail-closed linhagem congelada, 9 agentes, 37 skills, 4 referências, 12 pesos de challenger, SDKs, corte temporal e escolha real pelo champion.
- `smart_full_process_pipeline.py`: hook experimental após geração do cartão para escrever `SMART_CARD_CONSUMER_INTEGRATION.json` e vincular ao relatório.
- `test_smart_consumer_integration.py`: **4/4 testes PASS**, incluindo detecção de adulterações.
- Prova do cartão 3070 real no executor federado: checks do gate **PASS**, sem adulteração dos arquivos congelados.
- **Regressão integral da branch: 1.212 testes, 13 falhas, 0 erros. NÃO APROVADA.** Inclui incompatibilidades com registros de alcance/componentes, adaptadores e os contratos de identidade histórica F11/F12, além de artefatos legados. Não atribuir todas as falhas a uma única causa sem análise.
- Por regra de não regressão, **a branch NÃO foi promovida a `main`**, e a certificação produtiva não foi renovada com esse código.

## Gates restantes para integração ponta a ponta

1. Resolver os 13 testes da branch **sem reescrever ou falsear provas F11/F12, hashes históricos, epoch 3070 ou regressão científica**; quando o pipeline versionado for necessário, formalizar sucessão e novos contratos de evidência sem invalidar o código histórico.
2. Refazer a auditoria estática de alcance/componentes e dos adaptadores sem autodeclarações de PASS.
3. Executar regressão completa e independente no commit exato a certificar e gerar JUnit limpo, sem GitHub Actions; validar integridade global, Red Team e material deficiencies.
4. Certificar através do caminho federado aprovado com commit-fonte, código e JUnit vinculados; provar `preflight`, Git limpo e `origin/main` idêntico ao commit.
5. Demonstrar consumo causal por **cada** sinal/SDK na decisão, avaliando remoção/adicionamento, ablação, calibração e comparação fora da amostra. Não confundir disponibilização com influência real.
6. Promover fonte externa somente com contrato de proveniência, isolamento, autorização, teste causal, reversão, limites de recursos e ausência de ganho negativo. Fontes inaplicáveis devem continuar QUARANTINED/REFERENCE_ONLY.
7. Somente declarar 6/6 científico com provas prospectivas independentes suficientes. O status permanece `MISSION_ACTIVE / UNPROVEN`.

**Regra:** não executar códigos de terceiros em quarentena, não inventar canais LLM ou métricas, não reabrir cartão congelado nem fazer alterações retrospectivas com aparência prospectiva.
