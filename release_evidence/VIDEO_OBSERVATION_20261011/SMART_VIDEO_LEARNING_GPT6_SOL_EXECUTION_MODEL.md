# SMART-MEGA — Modelo executivo GPT-6 para aprendizagem visual acelerada

**Estado:** PROPOSTA DE ENGENHARIA / NAO HOMOLOGADO
**Data:** 2026-10-11, America/Sao_Paulo
**Origem:** `andrebarros78/SMART-MEGA`, branch `learning/video-observation-v131-20261009`, HEAD de base `bd0c0fedf6489293a6c1d5705333af03ad587195`
**Modulo existente:** `smart_video_observation.py` 1.3.1
**Politica:** `SMART_GITHUB_NATIVE_BASELINE_2026-09-28.md`; `main` continua unica autoridade canonica. Este documento nao altera pesos nem a producao.

## 1. Objetivo e verdade observada

Transformar a observacao fisica em servico **consumivel** que: (a) reutilize 13 checkpoints reais, caso validos; (b) processe em lote dezenas de videos acessiveis, com paralelismo limitado; (c) produza corpus visual versionado, rastreavel e de qualidade; (d) entregue features pre-sorteio legalmente disponiveis aos consumidores, apenas em modo observacional/sombra ate prova cientifica.

A referencia operacional relatada pelo usuario e 13 concursos em 10 dias. **Nao ha perfil de latencia por etapa nem confirmacao atual dos 13 arquivos B2.** Dez dias nao podem ser atribuidos somente ao algoritmo: o codigo atual define timeout de concurso de 120 s como verificacao parcial, e existe evidencia de bloqueio do YouTube na VPS. Diferenciar disponibilidade da fonte, tempo manual, fila e tempo real de CPU/GPU.

Inspecao no codigo 1.3.1: `analyze_queue` executa concursos serialmente; `run_samples` paraleliza somente amostras de um concurso; amostras usam abertura independente de `cv2.VideoCapture` e subprocessos `spawn`; o estado de aprendizado e recomputado e publicado por concurso; `--learn-only` ja existe; ha checkpoints imutaveis e revisoes de memoria com SHA. Os registros de evidencia mais recentes reportam testes anteriores, nao benchmark fresco; `predictive_evidence=NOT_ESTABLISHED`.

## 2. Modelo de capacidade: tres trilhas separadas

1. **Observacao:** reconhecer transmissao, trecho da Mega-Sena, regioes visuais, eventos de movimento, tempo, procedencia, qualidade e limitacoes. O resultado e fato visual ou candidato, nunca dezena sorteada confirmada por movimento sozinho.
2. **Aprendizagem visual:** memoria causal por concurso, comparacao entre videos e ajuste de localizacao/amostragem, somente com videos e checkpoints anteriores ao alvo. Usar o esquema existente e preservar a cadeia imutavel. Aprendizado de observacao nao e aprendizado de probabilidade da loteria.
3. **Valor preditivo:** avaliacao *prospectiva* de qualquer sinal realmente disponivel **antes** do sorteio-alvo, em modo sombra; apenas teste preregistrado, fora da amostra, contra baseline uniforme e campeao pode autorizar futuramente peso >0. Observacao do sorteio corrente depois da extracao nao pode influenciar o cartao daquele sorteio. Sem vantagem demonstrada: peso preditivo **0**.

## 3. Arquitetura operacional proposta (sem novo framework obrigatorio)

```text
manifesto de fontes (concurso, URL, instante, procedencia)
       |
       +--> validacao e deduplicacao --> reuso de checkpoint + SHA
       |
       +--> obtencao de metadados/legenda --> localizacao do segmento
       |
       +--> lote de concursos (workers 1/2/4, quota por host)
                 |
                 +--> caminho rapido: stream unico, decodificacao dirigida, ROI, amostragem adaptativa
                 +--> fallback: extrator 1.3.1 fail-closed
                 |
                 +--> checkpoint imutavel por concurso, com status e timings
       |
       +--> barreira unica de consolidacao (sem concorrencia escrevendo estado global)
       |
       +--> memoria visual versionada / hashes / feature manifest
       |
       +--> consumidor somente-leitura com cutoff temporal e status
       |
       +--> avaliacao de qualidade / shadow / validacao prospectiva
```

**Nao assistir o mesmo video novamente se um checkpoint original valido puder ser consumido.** Para arquivos antigos incompativeis, gerar diagnostico de schema; nunca reescrever o original para fabricar compatibilidade.

## 4. Plano executavel por fases

### F01 — Diagnostico e reuso imediato dos 13

- Inventariar exatamente `C:\SMART-MEGA\runtime\video_observation\contest_*.json` no PC Escola, preservando SHA-256, schema, status, tamanho, qualidade, duplicacoes, hora e fonte.
- Comparar 13 checkpoints com o contrato atual de `learned_motion_prior`. Produzir contagens VALID / INCOMPATIBLE / FAIL / MISSING.
- Executar o caminho ja existente `--learn-only` (sem rede, sem replay de video) para a proxima competicao, em ambiente autorizado e com hashes da memoria publicados. Validar arquivos de entrada versus `training_contests` consumidos.
- Registrar tempo real de inventario/reaprendizagem. Nenhuma migracao destrutiva.

### F02 — Lotes concorrentes e custo de rede

- Adicionar `observe_batch(manifest, workers=2, resume=True)` como **nova entrada do modulo existente**, sem substituir o contrato de `analyze_contest` / CLI atual.
- Validar URL e contest_id, deduplicar por fonte, usar cache de metadados autorizado e retentar falhas transitorias com backoff limitado; fonte bloqueada/privada permanece falha, sem burlar controles de acesso.
- Processar concursos independentes com paralelismo adaptativo 1, 2, 4 conforme CPU, RAM e taxa de erro; limitar sessoes por host. Nao usar 32 workers cegamente.
- Cada worker escreve **somente** seu checkpoint individual; memoria e arquivo de historico global sao escritos **uma vez apos a barreira do lote**, com ordenacao deterministica e SHA verificado. Garantir reentrada apos queda e idempotencia.
- Telemetria: tempo de fila, resolucao, legenda/segmento, decodificacao, consolidacao, bytes, FPS efetivo, memoria, retries, videos concluidos e categorias de indisponibilidade.

### F03 — Extracao visual inteligente, evitando full-watch

- Reaproveitar a busca do segmento para eliminar material irrelevante (apresentador, propaganda, outras loterias).
- Priorizar decodificacao **unica por segmento** com FFmpeg/OpenCV, FPS baixo inicial, diferenca de quadros, localizacao espacial e refinamento dos picos. Reaproveitar stream aberto quando suportado e evitar centenas de inicializacoes de decodificador.
- Refinar janela/regiao somente quando ha informacao nova. Manter amostragem sentinela fora das regioes quentes para detectar falsos negativos (nao "aprender" a ignorar eventos).
- Semantica sempre conservadora: `MOTION_EVENT_CANDIDATE` nao e `CONFIRMED_EJECTION`; mudanca de camera, grafismo ou ruido nao vira evidencia fisica.
- Manter o extrator 1.3.1 como fallback ate comparacao nao regressiva em videos reservados.

### F04 — GPT-6 como avaliador semantico, nao decodificador de tudo

- O GPT-6 desta conversa define contratos, hipoteses, auditoria e revisao de amostras. **Nao assumir que "GPT-6 Sol" e identificador de modelo exposto por API, nem que tenha acesso automatico a arquivos da maquina.**
- Se houver provedor multimodal autorizado disponivel, enviar apenas quadros/trechos curtos selecionados e seus carimbos temporais, sobretudo casos ambiguos; exigir JSON com evento, tempo, evidencia visual, contraevidencia, confianca e `unknown` quando nao observavel.
- Registrar modelo real, versao, parametros, hashes dos quadros, uso e custo. Sem API/credencial, a extracao local continua funcional. Nenhum custo externo sem autorizacao.
- Jamais usar o LLM para adivinhar dezenas a partir de motion scores.

### F05 — Corpus consumivel e memoria

- Preservar `contest_XXXX.json` e `SMART_VISUAL_LEARNING_STATE.json` existentes; criar export derivado minimo `SMART_VISUAL_FEATURES_V1.json` ou JSONL versionado e com SHA de fonte.
- Contrato do consumidor: `get_visual_features(target_contest, cutoff_utc, hypothesis_id)` retorna `status`, `as_of_utc`, `source_contests`, `source_sha256`, `observational_features`, `quality`, `limitations`, `predictive_weight_authorized=false`.
- Filtro estrito `source_contest < target_contest` E `created_at_utc <= cutoff_utc`; negar registros com hashes errados, labels de resultado, dados fora do cutoff e origem nao verificavel.
- Se nenhum sinal elegivel, publicar `INSUFFICIENT_EVIDENCE`, nao preencher com defaults inventados.

### F06 — Aprendizado de fato e antissobreajuste

- Preparar dataset de anotacoes com rotulos humanos auditaveis para eventos de camera, grafismo, urna/globo, abertura e saida de bola, com `UNKNOWN` quando nao verificavel.
- Separar treinamento/validacao/teste **por concurso e por data**, nao por quadros aleatorios do mesmo video. Reservar eventos de canais/edicoes diferentes, para nao confundir identidade de video com mecanismo fisico.
- Medir recall de eventos, precisao, falsos positivos por hora, taxa de nao-observavel, calibracao de confianca, cobertura do corpus e custo/tempo. Comparar ao extrator 1.3.1 na mesma amostra.
- O valor para o cartao e gate separado: backtest temporal sem vazamento + prospectivo com congelamento antes do resultado; caso contrario peso preditivo zero, independentemente do desempenho de visao.

### F07 — Homologacao operacional e promocao

- Fazer teste A/B no PC Escola com os mesmos videos **acessiveis**: versao 1.3.1 (fila serial) contra lote novo, 1 / 2 / 4 workers, incluindo indisponibilidades. Relatar tempo total e por fase, casos descartados e CPU/RAM/rede. Comparar por vídeo concluido, nao por tentativa.
- Critério de desempenho proposto: reduzir em >=4 vezes o tempo **tecnico medido** por 13 videos acessiveis sem perda material de deteccao; meta operacional exploratoria: 13 videos acessiveis no mesmo dia. **Metas, nao promessas nem benchmark observado.**
- Gates: G1 checkpoints integros e reutilizados; G2 zero corrupcao sob concorrencia/reinicio; G3 precisao/recall nao inferiores no holdout; G4 memoria deterministica + cutoff; G5 API de consumo exercitada; G6 regressao focada PASS com evidencia do commit atual.
- Quando G1..G6 PASS: promover a parte de **engenharia de observacao** via PR para `main`, com prova e hash. Qualquer peso preditivo continua bloqueado ate prova cientifica separada 6/6.

## 5. Riscos e decisoes

| Risco | Tratamento |
| --- | --- |
| Video inacessivel/YouTube challenge | status STREAM_FAILED; retry limitado; nunca contornar desafio |
| Multiplos workers alterando memoria global | unica fase de consolidacao serial, atomica, depois dos workers |
| Videos com mesmo segmento diferente | identidade de fonte + duracao + timestamp + hash, sem duplicar treino |
| Reducao de amostras criando falsos negativos | amostragem sentinela e teste holdout |
| Dados historicos contaminando previsao | cutoff temporal + fonte anterior + status shadow |
| Custo de chamadas multimodais | triagem visual local, LLM somente nos casos informativos |
| Confundir ciencia com prova preditiva | `NOT_ESTABLISHED` e peso 0 ate evidencia prospectiva |

## 6. Estado de evidencia na criacao deste plano

- Verificados via GitHub: branch de origem, codigo 1.3.1, testes, `EVIDENCE.json`, `LEARNING_MEMORY_RECOVERY.json`, `LEARNING_QUALITY_CORRECTION_V2.json`, `LEARNING_IMMUTABLE_HISTORY_V3.json`.
- 13 arquivos fisicos do PC Escola: **NAO VERIFICADOS**. Uma tentativa de inventario remoto pela malha LMCP em 2026-10-11 foi recusada em `REJECTED_OPERATION`, com razao `federated_external_operation_requires_modern_transport`; nenhuma leitura ocorreu.
- Nenhum novo benchmark, decodificacao de video real, teste de concorrencia, modelo/API multimodal nem consumidor em producao foi executado por este documento.
- Estado terminal: `MISSION_ACTIVE / DESIGN_ONLY`. Nao declarar `MISSION_PROVEN`.
