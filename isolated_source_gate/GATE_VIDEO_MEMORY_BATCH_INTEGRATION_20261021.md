# SMART-MEGA V6 — Conexão da memória observacional ao processamento em lote

**Gate:** integração do índice persistente com o consumidor oficial de
`observe_batch`, sem ativar inferência externa nem direitos de previsão.

## Contratos implementados

- `observe_batch` congela um único `as_of` após concluir os workers e
  solicita `get_visual_features` e `get_visual_learning_memory` para o
  mesmo concurso, hipótese, origem e cutoff PIT.
- Compara todos os concursos e hashes entre os dois leitores antes de
  publicar `SMART_VISUAL_STUDY_CURRENT.json`. Divergência de origem,
  contagem episódica, resumo/grafo ou sinal de autoridade inexistente
  provoca `MEMORY_SOURCE_MANIFEST_MISMATCH`.
- Em sucesso, o relatório `SMART_VISUAL_BATCH_V1` inclui o resumo
  `observational_memory` (schema `SMART_BATCH_MEMORY_RECEIPT_V1`):
  digest de proveniência, digest do manifesto, episódios, eventos,
  arestas, hit/miss, bloqueio de fonte e peso preditivo **0.0**.
  Não inclui resultados de concursos nem torna o vídeo preditor.
- A memória SQLite só aceita hit depois de comparar posições de
  eventos e data UTC dos episódios com os **bytes atuais e seu SHA-256**
  dos checkpoints de origem. Não admite falsificar a própria memória
  e recalcular o digest SQLite para alterar movimentos.
- O cache de checkpoints também não confia em `payload_sha256` isolado:
  persiste o JSON de origem em sua representação exata e verifica
  igualdade byte a byte antes de reutilizar linhas históricas.
  Formatos antigos são invalidados/reconstruídos, sem alterar checkpoints.
- Checkpoints sincrônicos, ensaios com adulteração de conteúdo/data e
  origem, leitor PIT e CLI continuam sem promover pesos ou modelos.

## Ciclo de qualidade

1. RED: teste de adulteração consistente de episódio/grafo falhou: a
   versão antiga aceitava o payload modificado como `index_hit=True`.
2. GREEN: validação contra bytes de origem e retorno ao episódio
   autêntico, com invalidação de índice.
3. RED: adulteração da alegação `predictive_evidence` era aceita com
   digest recomputado. GREEN: somente `NOT_ESTABLISHED`.
4. RED: `observe_batch` não retornava recibo da memória. GREEN: saída
   conectada, validada com checkpoint de origem e mesmo PIT.
5. RED: checkpoint cache retornava JSON forjado no SQLite com digest
   recomputado. GREEN: exigida igualdade de bytes com fonte.
6. Testes verificam reutilização em duas execuções com cutoff idêntico,
   injeções negativas e compatibilidade com contratos existentes.

## Limitações e promoção

- A validação suplementar dos arquivos torna o caminho aquecido mais
  caro. No ensaio anterior de 200 checkpoints sintéticos, a memória
  aquecida com verificação de origem registrou mediana de **125,150 ms**
  contra **97,696 ms** do leitor isolado. A segurança prevalece sobre
  uma aceleração não demonstrada. A comparação não inclui aquisição,
  decodificação ou inferência de vídeos reais.
- O M3-Agent e TaskMem completos ainda são fontes versionadas, não
  motores multimodais ativos; componentes puros e o índice observacional
  não são prova de vantagem preditiva.
- A política do repositório permite executores externos governados,
  proíbe GitHub Actions e conserva `main` como autoridade.
- Gate presente na branch do PR #68. Suíte integral e validação
  prospectiva com dados físicos reais permanecem separadas; **sem
  promoção de `main` nem fonte CAIXA habilitada**.

## Portabilidade dos registros de governança

A instalação canônica inclui uma regra `.gitattributes` com
`eol=crlf` para diversos arquivos Python. Sem normalização, o Git
armazena blobs LF, mas F01 produz SHA-256 distintos nos checkouts CRLF,
invalidando registros F01/F05/F10 de um commit perfeitamente limpo.
Corrigido o cálculo da identidade dos **arquivos Python** para
normalizar CRLF → LF antes de gerar hashes de componentes e inventário.
O SHA-256 de checkpoint JSON de vídeo não é normalizado: sua proteção
permanece estritamente byte a byte. Adicionado teste de igualdade de
inventário para duas árvores Python semanticamente idênticas, uma LF
e outra CRLF. Os registros F01/F05/F10 são reconstruídos com o novo
contrato. Essa correção não declara execução dinâmica de ferramentas.
