# SMART-MEGA V6 — Aquisição oficial de vídeo B2 e proveniência temporal

## Inspeção governada (21/10/2026)

Ambiente `PC-ESCOLA`, nó `B2-LEARNING-NODE-01`. Transporte
`shell.exec` assinado `TAILSCALE_SIGNED_LONG_POLL`. Todos os comandos
foram somente leitura. A fila oficial continha 50 concursos pendentes,
com hashes canônicos válidos tanto para a fila quanto para o bloqueio
persistente da fonte; o histórico físico do bloqueio coincide byte a byte.
Recibo `netcmd_fb1b17a5b3f44242b58b755cccfc5511`.

**Amostra autorizada pública:** concurso 3013, vídeo
`ZP3mCk4_ku0`, mesma identidade URL do catálogo da CAIXA.
A página `www.youtube.com/watch?v=ZP3mCk4_ku0` respondeu
**HTTP 429**; `oEmbed` respondeu **HTTP 200** com
`author_name=CAIXA`, `author_url=https://www.youtube.com/@caixa`,
título `Loterias CAIXA | 30/05/2026`. Metadados possuem SHA-256,
identidades de operações diferentes para a página e o oEmbed.
Recibos `netcmd_6487f2b37c2347d2a5614bc9f4993ce9` e
`netcmd_25161a92732b40f5a44258d8faa785a3`.
Evidência: `B2_CAIXA_PUBLIC_MEDIA_PROBE_20261021.json`.

Esse HTTP 200 não é acesso ao vídeo, não são quadros decodificados e não
libera a trava persistida, cujo último motivo era
`YOUTUBE_SIGN_IN_REQUIRED`. Nada foi baixado, nenhum cookie foi
utilizado, nenhum 429 foi contornado, e nenhum dado de aposta foi visto.

## Correção técnica implementada

- Novo `smart_video_official_media_admission.py`, diagnóstico de fonte
  que exige fila oficial hash-válida, identidade exata de concurso,
  vídeo e canal oficial, ausência de resultados sorteados no registro,
  fonte bloqueada com histórico byte a byte, e recibos separados para
  acesso à página e metadados.
- `smart_b2_physical_learning_gate.py` agora aceita
  `--official-queue-dir` e `--official-probe-json`: **antes**
  de inspecionar checkpoints, passa pela trava de aquisição. Com
  fonte bloqueada ou ausente não lê checkpoints nem executa o consumidor.
  Nenhuma informação de oEmbed autoriza quadro real ou peso positivo.
- O novo diagnóstico é `VALIDATION_ONLY` em F08: não substitui o
  operador, não promove código ao gerador de cartões e não cria
  release produtiva.
- Fail-closed em falsa autenticação, registro contaminado com resultado,
  hash e histórico divergentes, caminho `SYNTHETIC_ONLY*`, symlinks,
  recibo de origem da página ausente e metadata HTML 200 sem frames.
  CLI do diagnóstico retorna código de saída não zero enquanto a
  mídia não está autorizada.

## Condições objetivas para abrir o próximo gate

1. Acesso explícito e permitido pelo provedor para **decodificar**
   o vídeo oficial selecionado, com comprovante de procedência e
   autorização de uso; requer revisão própria do source gate bloqueado.
2. Gerar checkpoint com consumidor existente do SMART-MEGA a partir
   de quadros realmente lidos, registrar SHA-256 da mídia ou do
   segmento original, frame count, id do vídeo e do concurso,
   data de observação e proveniência do executor.
3. Preservar prova independente de existência/disponibilidade de
   cada sinal **antes do cutoff do alvo a prever**. Não inferir
   preexistência a partir da data de publicação, do `mtime` ou do
   `created_at_utc` escrito pelo próprio checkpoint.
4. Validar a cadeia fonte → frames → checkpoint → memória → consumidor,
   usando holdout prospectivo para quaisquer ganhos de previsão.
   Mesmo com quadros reais, peso preditivo continua **zero** até
   evidência independente e aprovação de outra autoridade.

**Status deste gate:** fonte pública de **metadados** verificada;
aquisição de **quadros oficiais** bloqueada (HTTP 429, gate persistente).
Não foram criados checkpoints de vídeo real, nem atestada utilidade
observacional real; declarar qualquer uma dessas etapas como PASS
seria falso. B2 e `main` preservados.

## Revisão de prova do recibo

A classificação do código foi endurecida para
`REPORTED_METADATA_ONLY`: apesar do recibo real do B2 ter sido
observado através da ferramenta governada, o **arquivo JSON de probe**
só contém um identificador `netcmd_...`, sem verificar sua assinatura
contra a autoridade de execução. O validador local declara
`receipt_cryptographically_verified=false` e não equipara hash
autodeclarado a atestação independente. Uma versão futura só poderá
promover tal atributo com consulta e validação do recibo na autoridade
autenticada. O bloqueio da fonte, o consumidor e os pesos permanecem
inalterados.
