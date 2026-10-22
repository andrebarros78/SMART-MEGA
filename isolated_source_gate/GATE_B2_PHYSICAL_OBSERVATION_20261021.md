# SMART-MEGA V6 — Gate B2 de checkpoints físicos e proveniência temporal

## Autoridade e situação da origem

- Fonte relatada no handoff: `PC Escola / DESKTOP-4T6AS9K`,
  `C:\SMART-MEGA\runtime\video_observation\contest_*.json`, 13 arquivos
  **declarados, não autenticados** no `SMART_VIDEO_LEARNING_SOURCE_HANDOFF_20261009.json`.
- Binding da Fabric resolvido para o nó
  `f9d3fc77-3bc3-470b-9808-51eaf2ac3b2f` (B2-LEARNING-NODE-01).
- Tentativa real de inventário PowerShell exclusivamente de leitura:
  `netcmd_398cce6915a34d8ca0f6d4528ae1aed2`,
  missão `netmission_0e096f17d01c481c9ce6188939382e50`.
  Resultado devolvido por GOV-WINDOWS:
  `REJECTED_OPERATION` /
  `federated_external_operation_requires_modern_transport`.
  **Zero arquivos físicos do B2 foram abertos nessa execução.**
  Não reinterpretar `READY` no registro de nós como execução remota comprovada.
- Não foram contornados a recusa do transporte, controles administrativos
  nem a autoridade da `main`.

## Contrato implementado

`smart_b2_physical_learning_gate.py` faz auditoria por origem acessível,
em modo leitura, com as opções `--checkpoint-dir`,
`--target-contest`, `--cutoff-utc`, `--expected-count`.

1. Reutiliza o inventário oficial `audit_checkpoint_inventory`: exige
   contagem integral, identidade de concurso, SHA-256 dos bytes, HTTPS,
   fingerprint/config/extractor, status, ausência de rótulos de resultado,
   integridade dos movimentos e limites do trecho de vídeo.
2. Se a origem estiver inacessível, número de arquivos divergir ou uma
   integridade falhar, não executa o consumidor, retorna status explícito,
   utilidade `null` e peso preditivo 0.
3. Copia os bytes dos checkpoints validados **somente para diretório
   temporário**, confere hashes antes da cópia e não grava SQLite, modelos
   nem histórico na pasta de origem. O consumidor oficial recebe a cópia,
   sob um mesmo alvo e corte temporal explícito.
4. Registra `created_at_utc` como **autodeclaração do checkpoint**,
   separando registros anteriores/posteriores ao corte informado.
   Nem esse campo, nem `LastWriteTimeUtc` do Windows provam
   captura ou disponibilidade anterior ao fechamento da aposta.
   `pit_independently_attested=false` enquanto não houver atestado
   histórico externo e verificável.
5. Mede **utilidade observacional descritiva**: episódios elegíveis,
   checkpoints candidatos, registros excluídos, movimentos identificados,
   mediana de movimentos por episódio e arestas do grafo. Não inventa
   acertos, impacto nos cartões, superioridade de previsão ou ganho futuro.

## Ensaio reproduzível isolado (não é dado real do B2)

Teste com 13 arquivos sintéticos de estrutura idêntica ao contrato de
checkpoint, usando `test_smart_visual_memory_gate` como gerador:

- 13 arquivos encontrados, 13 aceitos pelo inventário, 13 episódios,
  39 eventos de movimento, integridade SHA-256 inalterada e nenhum
  SQLite gravado na fonte.
- Corte temporal declarado não atestado externamente.
- Testes negativos para caminho indisponível, symlink, vazamento de
  resultado, arquivo posterior ao corte, contagem divergente e
  referência de concurso inválida.
- Esses valores são métricas de fixture **e não representam o PC Escola**.

## Critério operacional de homologação B2 real

- Usar um transporte **moderno e autorizado** capaz de devolver recibos
  de leitura governada no PC Escola, ou cópia de evidências autorizada
  com hashes verificáveis e relação ao mesmo diretório físico.
- Validar os 13 arquivos reais, calcular hashes, preservar os originais,
  conferir alvo temporal legítimo documentado e rodar o consumidor em
  cópia isolada. Sem esses pré-requisitos: `PHYSICAL_SOURCE_UNAVAILABLE`
  ou `PIT_NOT_INDEPENDENTLY_ATTESTED`, sem autorização preditiva.
- Antes de alegar utilidade para previsão, exigir evidência externa
  prospectiva datada, consumo downstream rastreado e ganho validado
  fora da amostra. Esses gates **não são implementados nem autorizados**
  pelo auditor observacional.

**Estado:** código e testes de engenharia disponíveis; acesso físico B2 e
validação temporal independente continuam bloqueados. Nunca promover
inferências a cartões nem alterar `main` por estes números.

## Atualização verificável — retomada do transporte moderno no B2 (21/10)

A recusa anterior foi causada pela escolha de operação:
`powershell.exec` está ausente de
`governor_windows.network_dispatch.MODERN_PC_TRANSPORT_OPS` para
executores externos. Não era uma indisponibilidade física total da máquina.
Sem alterar o governador, a operação já implementada e autorizada
`shell.exec` foi executada com `hostname` e `python --version`;
ambas retornaram `exit_code=0`, hostname `PC-ESCOLA`,
autenticação, identidade física e vínculo de execução comprovados.
Transporte: `TAILSCALE_SIGNED_LONG_POLL`.
Recibos: `netcmd_891de83dccab434fb8beeef1e3612faf`,
`netcmd_7c64f796eed34ca5b31c1b78f82eb940`.

**A reconciliação da fonte real contradiz a localização histórica declarada.**
O diretório `C:\SMART-MEGA\runtime\video_observation` não existe
(`netcmd_ea8ff422e0344152a3fddca4d8939405`).
O diretório `real_video_checkpoints` declarado pelo queue também não
existe (`netcmd_fee4cad077034a2189e76523cdf49d45`).
Uma busca completa, sem truncamento, nas subárvores SMART-MEGA
autorizadas localizou somente 26 `contest_*.json` em dois conjuntos
explicitamente nomeados `SYNTHETIC_ONLY_13` e
`SYNTHETIC_ONLY_OFFICIAL_QUEUE_13`, 13 cada
(`netcmd_5dae1aad45d342ff95b5b553ef4e33d0`).

**Disponibilidade de vídeo real também está bloqueada:**
`SMART_CAIXA_MEDIA_SOURCE_CURRENT.json` informa
`YOUTUBE_SIGN_IN_REQUIRED`; `SMART_CAIXA_OBSERVATIONAL_QUALITY_CURRENT.json`
registra 50 concursos na fila, 50 `SOURCE_ACCESS_BLOCKED`,
`real_media_verified=false`, **zero quadros decodificados** e peso
preditivo zero
(`netcmd_ba8e67d9bba04157b39fd49bc85cb0bb`).
O ZIP de migração SMART-MEGA inspecionado não contém
`contest_*.json`. Não existe prova de que 13 checkpoints de vídeo
reais estejam disponíveis na fonte anterior.

**Regressão de proteção:** duas falhas reproduzidas RED demonstraram
que o auditor anterior aceitava pastas `SYNTHETIC_ONLY*` como observação
física; o novo auditor as classifica
`SYNTHETIC_SOURCE_QUARANTINED`, sem episódios nem métricas de
utilidade real, preservando `predictive_weight=0`.
Essa classificação nominal é uma defesa contra fontes rotuladas
explicitamente sintéticas, não uma certificação independente de que
outra origem é real.

A execução do consumidor em vídeos reais permanece
`BLOCKED_SOURCE_ABSENT`. Requer fornecimento dos vídeos por
acesso autorizado e geração de checkpoints reais com evidência
temporal independente. Não burlar `YOUTUBE_SIGN_IN_REQUIRED`.
O estado atual auditado permanece registrado em
`B2_MODERN_TRANSPORT_AND_REAL_MEDIA_20261021.json`.

**Frescor do relatório:** a fonte e a qualidade da fila foram atualizadas pela última vez em 17/10/2026 UTC e a lista de concursos em 14/10/2026 UTC, conforme metadados do próprio B2 (recibo `netcmd_c30aec7c65244ac09d3bbd3729f64848`). `YOUTUBE_SIGN_IN_REQUIRED` é a **última situação registrada**, não um novo teste de login executado em 21/10.

## Gate posterior — evidência de quadros e cobertura da qualidade (21/10/2026)

A auditoria física aceitava episódios de movimento como métricas
observacionais quando o checkpoint não informava se algum quadro havia
sido decodificado. Essa ausência não pode ser interpretada como quadros
vistos, especialmente porque fixtures sem vídeo podem conter eventos
de movimento preenchidos diretamente no JSON.

O resultado `observational_utility.decoder_quality` agora classifica
**somente os episódios elegíveis após filtros de concurso e cutoff PIT**:

- `with_consistent_decoder_counters`: há ao menos uma janela `coarse`
  e uma `analyzed_windows` com status `OK`, contadores inteiros
  (não booleanos), no limite 2 <= analyzed_frames <= read_frames
  <= 1.000.000; limites por conjunto: 1 a 64 janelas;
- `without_decoder_counters`: os dois conjuntos estão ausentes;
- `invalid_decoder_counters`: as janelas são incompletas,
  inconsistentes ou usam contadores inválidos;
- `motion_events_with_decoder_counter_support`: eventos associados
  somente a episódios com os dois conjuntos consistentes;
- `candidate_counter_coverage_ratio` e
  `motion_event_counter_coverage_ratio`: cobertura descritiva com
  denominadores dos episódios de fato elegíveis; `null` quando
  não houver denominador adequado;
- `independently_verified_decoded_frames=null` e
  `frame_content_authenticity_established=false`: os contadores
  continuam **autodeclarações do checkpoint**, não identidade da
  mídia nem prova de pixels, tempo ou acerto.

Esse gate não muda o peso preditivo (permanece 0.0), não ativa M3-Agent,
TaskMem ou fonte externa, não escreve no diretório da origem B2 e não
certifica retrospectivamente que um sinal existia antes da aposta.
Os testes RED/ GREEN cobrem falta de contadores, contadores válidos,
inversão read/analyzed, booleanos, números exorbitantes e exclusão
temporal de checkpoints posteriores ao cutoff. Toda alteração permanece
fora da main até homologação do commit correspondente.


**Ensaio remoto B2 (somente leitura):** o comando
`netcmd_6f8f768089e349968b705a3e0155641c` constatou os 26
`contest_*.json` nos dois conjuntos `SYNTHETIC_ONLY*`. Todos os
26 possuem `status=CANDIDATE`, mas **nenhum** apresenta as duas
coleções de janelas com contadores de frames suficientes para esta
auditoria. Consequentemente, a cobertura de suporte de decodificação
observada nos conjuntos sintéticos é 0/26; **isso não é um resultado
sobre vídeos reais**, nem prova valor preditivo.
