# SMART Mega V6 â€” Correcao auditada do seletor (31/10/2026)

## Identidade e integridade
Repositorio: andrebarros78/SMART-MEGA.
Branch local de pesquisa: research/mega-v6-selector-exact-20261031.
Branch publicada: research/mega-v6-selector-exact-published-20261031.
Base do experimento local: 657bb41e3f6238746ef6ae20775b6f58645f1172.
Base da publicacao: 7834adea0a06541dc53f93953b1f83d49e726a1e (main com historico ate 3077).
A observacao 3078 e incorporada em memoria a partir da captura oficial (SHA-256 a395eefaf733f7ad132babc7bffd010836309a545697b34c4d805a9221e626ee).
Nenhum arquivo produtivo existente foi editado; seletor, pesos, historico e contratos originais foram preservados.
O concurso 3079 permanece adjudicado e arquivado na branch operacional, sem cartao retroativo.

## Defeito reproduzido
O seletor original enumera todas as combinacoes de 6 dezenas do conjunto de candidatos.
Para 60 candidatos isso corresponderia a 50.063.860 combinacoes potenciais.
No sorteio 3079, o cartao congelado 10-11-14-27-38-43 teve 0/6 contra 05-09-16-40-41-59.
Apenas duas dezenas reais pertenciam ao pool18; nenhuma pertencia ao top3 obrigatorio.
O resgate de falsos negativos estava em DEGRADED_SHADOW_ONLY com quatro observacoes.
O peso efetivo freq1000 do congelamento era 0,4624, e a familia de frequencia somava 0,70.
Nenhum desses fatos demonstra por si que os sorteios sejam previsiveis.

## Correcao executada
Arquivo de pesquisa: smart_primary_card_selector_research.py.
Metodo: programacao dinamica exata por bandas, cardinalidade e presenÃ§a de top3.
Preserva validacao de entrada, objetivo, politicas e desempate do algoritmo existente.
Permite testar 18/30/60 candidatas, top3 obrigatorio ou opcional, sem alterar o motor produtivo.
No replay real do 3079, o pool60 foi avaliado em 498 transicoes/estados contra
50.063.860 combinacoes teoricas, com resultado otimo exato.
Nenhum valor futuro integra a entrada da selecao; promocao de modelo explicitamente proibida.

## Testes
- RED confirmado: a capacidade nao existia (ModuleNotFoundError).
- GREEN: 24 testes passaram, zero falhas, sobre novo e antigo seletor.
- Equivalencia validada contra enumeracao exaustiva para 16 previsoes historicas adicionais.
- Teste de tempo, validacao de pool60 e modo top3 opcional foram aprovados.
- Evidencias: SMART_MEGA_SELECTOR_EXACT_COMPARATIVE_EVIDENCE_20261031.json e
  SMART_MEGA_3079_SHADOW_SELECTOR_COMPARISON_20261031.json.

## Comparacao cronologica retrospectiva
Historico com corte em 3078; pesos reproduzidos por walk-forward causal.
A hipotese foi formulada apos o 3079: portanto nao ha holdout cientifico independente.

| Variante | Desenvolvimento (251) | Selecao (100) | Avaliacao (128) |
|---|---:|---:|---:|
| Campeao pool18 com top3 | 171 | 56 | 77 |
| Pool18 sem top3 | 171 | 56 | 77 |
| Pool30 sem top3 | 170 | 57 | 77 |
| Pool60 sem top3 | 170 | 57 | 77 |
| Pool60 sem top3, freq1000 limitado a 20% | 164 | 53 | 72 |
| Pool60 com top3 | 170 | 57 | 77 |

### Replay posterior do congelamento 3079
| Pool | Top3 necessario? | Estados avaliados | Dezenas reais no pool | Acertos finais |
|---|---|---:|---:|---:|
| 18 | Sim | 117 | 2/6 | 0/6 |
| 18 | Nao | 124 | 2/6 | 0/6 |
| 30 | Nao | 218 | 4/6 | 0/6 |
| 60 | Nao | 498 | 6/6 | 0/6 |
| 60 | Sim | 491 | 6/6 | 0/6 |

6/6 dentro do pool60 significa apenas que todas as dezenas possiveis estavam presentes.
Nao significa 6/6 na selecao final, que permaneceu 10-11-14-27-38-43 nas cinco variantes.

## Decisao
- PASS ENGENHARIA DE PESQUISA: solver exato, limitado e testado.
- FAIL PROMOCAO PREDITIVA: nenhuma variante superou o campeao em avaliacao;
  limitar freq1000 a 20% piorou a metrica.
- 6/6 NAO COMPROVADO. Com sorteios uniformes, a chance de um unico jogo simples
  acertar seis dezenas e 1 em 50.063.860. Nenhuma previsao anterior foi alterada.
- Proximas evidencias: preregistro de hipoteses, previsoes prospectivas congeladas,
  comparacao pareada com controle uniforme, intervalos e gate de promocao estatistica.
- Nao foi feito merge na main, mudanca de pesos, promocao de modelo ou aposta.
## Reproducao na branch de publicacao
python -I research/SMART_MEGA_SELECTOR_RESEARCH_BACKTEST_20261031.py --data Mega-Sena.xlsx --extra-result research/CAIXA_MEGA_SENA_3078_CAUSAL_REPLAY_20261031.json --out pesquisa_replay_novo.json
Esperado: metricas identicas ao arquivo research/SMART_MEGA_SELECTOR_EXACT_REMOTE_REPLAY_20261031.json e SHA de conteudo 5ec523f29d6177102b4a92006071379f000d63fd2c40b93ec70a4df3b7aadf47.
