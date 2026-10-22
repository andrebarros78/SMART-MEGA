# SMART-MEGA V6 — Memória Observacional PIT (Gate técnico)

**Escopo:** integração nativa, somente leitura de evidências históricas, em
`feature/learning-vendor-native-production-20261021`. Não concede execução de
modelos multimodais, acesso à fonte CAIXA nem autoridade de resultado/predição.

## Contrato implementado

- `smart_video_learning.get_visual_learning_memory(target_contest, cutoff_utc,
  checkpoint_dir, hypothesis_id=None, source_url=None)` usa
  `get_visual_features` para revalidar fonte, identidade, hash, cronologia e
  hipótese antes de qualquer leitura da memória.
- Camadas independentes: `episodic` (por concurso anterior e SHA-256 da fonte),
  `semantic` (histograma numérico dos movimentos observados) e `graph`
  (arestas somente `OBSERVED_MOTION_ONLY`). Nenhuma camada usa resultados
  oficiais, dezenas sorteadas ou classificação preditiva.
- Índice SQLite persistente `.visual_learning_memory.sqlite`, chave derivada
  do contrato de consulta e dos hashes verificáveis da fonte; retorno quente
  exige revalidação do consumidor histórico e consistência cruzada de episódio,
  resumo e grafo.
- Cache pré-existente `.checkpoint_cache.sqlite` agora autentica
  **integridade acidental do payload** por SHA-256 local, migra esquema legível
  antigo e jamais reutiliza linhas legadas sem digest.
- Interface CLI `python smart_video_learning.py --target-contest 1200
  --cutoff-utc 2026-10-11T00:00:00Z --checkpoint-dir DIR --memory-readonly`.
  A operação é local/offline, sem rede ou inferência de modelos.

## Ensaios e limitações

- Testes incluem PIT futuro/alvo, troca de conteúdo após aquecimento,
  corrupção do payload SQLite, forjamento de resumos internos, índice em
  symlink, migração de cache legado e contrato CLI.
- Benchmark de **200 checkpoints sintéticos** na VPS: primeira construção
  2.211,535 ms; mediana quente 65,347 ms; leitor canônico quente 72,164 ms;
  cinco hits de índice, alteração temporal 200→199 elegíveis.
- O tempo mede somente leitura e índice; contém efeitos de page cache.
  Não há medição com checkpoints físicos da B2 nem comprovação de ganho na
  análise de vídeo, no consumo completo do produto ou nos acertos da Mega.
- Snapshot de memória é **descritivo, não autoridade criptográfica externa**:
  a consistência é checada contra o leitor histórico e hashes da fonte, mas
  não substitui testemunho assinado e datado de proveniência.
- Pacotes adquiridos completos permanecem versionados e não executados:
  os modelos pesados M3-Agent/TaskMem e o servidor MCP de vídeo exigem
  dependências/autorizações específicas. A arquitetura episódica e de grafo
  aqui é implementação nativa inspirada nesses projetos, não execução
  integral dos motores externos.
- A política canônica atual é
  `SMART_GITHUB_CANONICAL_EXTERNAL_EXECUTION_NO_ACTIONS_20261021`:
  GitHub permanece repositório, execução governada em conector externo
  é autorizada e GitHub Actions é proibido.
- A regressão integral ainda requer ambiente isolado com as
  dependências reais da `requirements.lock.txt`; os erros de ambiente
  não podem ser reclassificados como testes aprovados.
- **Gates invariantes**: CAIXA BLOQUEADA, peso preditivo 0.0,
  `main` preservada. Sem declaração de publicação produtiva.

## Homologação governada após atualização da política canônica

- Política `SMART_GITHUB_CANONICAL_EXTERNAL_EXECUTION_NO_ACTIONS_20261021`
  confirmada como `PASS`, sem GitHub Actions ou dependência de runner hospedado.
- Integração alinhada ao commit canônico `8a97289b0fe8b207a394c52292ed9580e478cea8`.
  PR #68 utiliza uma branch derivada dessa revisão e não altera `main`.
- Executor independente SentinelX (`wmcp-cloud-01`): **41/41 testes
  focais `unittest` PASS**, incluindo PIT, adulteração de memória, migração
  de esquema, CLI e rejeição de symlinks no banco e na origem dos checkpoints.
- Benchmark de referência `visual_memory_gate_benchmark_20261021.json` na
  área isolada LMCP, SHA-256
  `50e30973e6f23f2efafdf982914dfc97fd97c896288c5cd5616ffeccef55c703`.
- **Bloqueio F01 pré-existente na nova `main`:** o registro de
  alcançabilidade ainda busca roots em `.github/workflows`. O novo contrato
  proibiu/removou esses arquivos, logo os roots são zero e nove módulos
  produtivos são marcados inalcançáveis. Resultado `F01_GATE=FAIL` idêntico
  tanto no checkout `main` `8a97289` quanto no candidato; não é regressão
  causada pela memória. Adaptar F01/F10 ao **verdadeiro ponto de entrada
  externo, comprovado e autorizado**, sem inventar execução, constitui gate
  arquitetural separado para homologação integral.
- A suíte completa com dependências em conformidade e checkpoints físicos
  ainda não foi certificada. Não tratar a regressão focal como aprovação
  científica ou autorização de promoção produtiva.
