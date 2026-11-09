# SMART-MEGA V6 — Contrato de contribuição experimental de LLM

## Objetivo e limite verificável

Este fluxo admite uma **proposta gerada fora do processo Python**, inclusive pelo ChatGPT sem API paga, como um sexto candidato prospectivo `llm_shadow_v1`. O mecanismo original mantém cinco candidatos nativos. O candidato LLM é consumido pela mesma rotina de congelamento prospectivo, registro de 60 probabilidades e adjudicação após o resultado oficial.

**Não é um conector de inferência automática.** O código não executa chamada a OpenAI, não autentica o provedor declarado e não demonstra que o conteúdo foi realmente gerado por uma LLM. A alegação de provedor é rotulada como não verificada. A ponte exige um artefato externo, versionado e preparado *antes* do sorteio. Testes com dados sintéticos comprovam o contrato, não um ganho científico.

## Entrada operacional

Antes do `freeze` de um concurso `N`, o operador coloca na raiz do checkout canônico um arquivo `SMART_LLM_SHADOW_CANDIDATE_N.json`, com:

- `schema = SMART_LLM_SHADOW_PROPOSAL_1`;
- `target_contest = N` e `cutoff_contest = N - 1`, inteiros;
- `history_sha256` igual ao SHA-256 **dos bytes do histórico exato** usados pelo congelamento, já cortado em `N-1`;
- `generated_utc` com fuso horário, anterior ao congelamento e ao sorteio;
- `provider_claim`, `model_claim` e `prompt_sha256`: identificação **declarada**, sem comprovação automática da chamada;
- `scores`: objeto com exatamente as chaves string `"1"` a `"60"`, cada uma com pontuação numérica finita entre 0 e 1; não são probabilidades calibradas;
- `result_used = false` e `production_authority = false`;
- `sha256` da versão JSON canônica de todos os demais campos, ordenados por chave, codificados em UTF-8 sem escapes ASCII.

A função `smart_signal_llm_shadow.load_proposal` valida esse contrato, bloqueia campos extras, hashes inválidos, números booleanos, dados futuros e propostas de outro concurso.

## Consumo, rastreamento e avaliação

O comando já existente `smart_full_process_pipeline.run_full_process` procura esse nome específico de arquivo e o passa ao `smart_frontier_signal_lab.freeze_shadow`. Se não houver arquivo, preserva os cinco candidatos originais. Se houver arquivo inválido, falha sem aceitar o candidato.

O congelamento registra `llm_shadow_v1` na governança `SMART_SIGNAL_EXPANSION_REGISTRY`, guarda o hash do arquivo de entrada, converte as 60 pontuações em probabilidades de inclusão que somam seis e conserva o candidato com `material_weight = 0` e `production_authority = false`. `smart_prospective_cycle.build_registration` registra sua previsão e compara a sobreposição com o cartão `champion`, sem alterá-lo.

Depois que um resultado oficial é disponibilizado, `smart_frontier_adjudicator.adjudicate_frontier` avalia o sexto candidato na mesma rotina usada para os demais, registra acertos, diferença de acertos, Brier e novidade, e atualiza a governança causal. Nunca reutilizar resultados passados para afirmar que uma previsão foi congelada antes do sorteio.

## Critério de promoção e honestidade científica

Nenhum teste de integração, divergência de cartões ou resultado retrospectivo autoriza afirmar melhora na probabilidade de seis acertos. O regime existente `smart_signal_expansion_governance` exige dados prospectivos fora da amostra, partições independentes, ganho marginal estatisticamente sustentado e autorização explícita, com limite de 5% do Challenger. Esse gate não concede peso ao champion nem implementa promoção operacional automática.

Em uma loteria justa, a probabilidade de acertar seis dezenas com uma aposta simples é 1/50.063.860. Uma LLM pode elaborar hipóteses e contribuir para teste de robustez, validação dos dados e explicabilidade, mas não possui capacidade preditiva superior comprovada por simplesmente examinar sorteios anteriores.

## Evidências exigidas

1. Arquivo da LLM registrado no GitHub antes do encerramento e associado ao histórico `N-1`.
2. Hash do arquivo de entrada preservado no congelamento prospectivo e no registro.
3. Adjudicação posteriormente vinculada ao resultado oficial de `N`.
4. Comparação pareada e avaliação fora da amostra, incluindo resultados desfavoráveis e múltiplos testes.
5. Somente após comprovação científica e autorização explícita, gate separado para avaliar peso limitado no Challenger.

Nenhum campo `PASS` determinístico deve ser interpretado como demonstração de uma chamada LLM real ou vantagem preditiva.
