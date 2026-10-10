# SMART-MEGA — Modelo de Aprendizado Visual V2 (projeto GPT-6)

**Data:** 2026-10-10  
**Repositório canônico:** `andrebarros78/SMART-MEGA`  
**Base de evolução:** `learning/video-observation-v131-20261009`  
**Estado científico:** `MISSION_ACTIVE / predictive_evidence=NOT_ESTABLISHED`  
**Autoridade operacional:** nenhuma para alterar dezenas, pesos preditivos, cartões ou freeze.

## Objetivo e distinção essencial

A missão "Continue missão aprendizado" significa **observar os vídeos oficiais dos sorteios, extrair sinais físicos, analisar erros, acumular memória auditável entre concursos e melhorar o próprio método de observação**. Não significa apenas passar testes, nem significa provar previsibilidade dos números sorteados.

GPT-6 é o modelo de análise e revisão deste projeto executivo. O runtime local é Python; **não existe chamada permanente ao GPT-6, servidor GPT-6 ou treino automático de pesos LLM instalado por este documento**. Uma sessão humana/IA pode consumir o estado JSON, revisar evidências e propor hipóteses, mas nunca transformar automaticamente uma hipótese em peso preditivo.

## Descobertas verificadas no código anterior

- `smart_video_observation.py` versão 1.3.1 já possui `learned_motion_prior()` e `persist_visual_learning_state()`, grava `runtime/video_observation/SMART_VISUAL_LEARNING_STATE.json`, e calcula um prior com candidatos de movimento de **concursos anteriores**.
- Esse prior V1 exige `CANDIDATE` com consenso espacial e ignora para sua estatística as observações `INSUFFICIENT_EVIDENCE`, `UNOBSERVABLE` e `STREAM_FAILED`: isto desperdiça informação sobre a qualidade do método de observação.
- O antigo prior pode tornar-se "ativo" com somente três observações elegíveis de movimento, mas o próprio código mantém a autoridade preditiva desabilitada.
- Histórico B2 de 13 vídeos foi relatado anteriormente, porém **os 13 checkpoints não foram relidos nem revalidados na presente evolução**. Eles não são declarados dados de treino V2 até passarem pelo contrato de identidade/proveniência.
- O fluxo v1.3.1 não prova que uma movimentação detectada é de uma bola específica, ou que prediz os números sorteados.

## Arquitetura modular

| Módulo | Nome | Responsabilidade / evidência |
| --- | --- | --- |
| M1 | Aquisição controlada | Localizar vídeo oficial e guardar URL, data, concurso, qualidade e hash; falhar fechado se inacessível. Não persistir mídia bruta por padrão. |
| M2 | Segmentação e autenticidade | Distinguir Mega-Sena de outras loterias, câmera, edição, cortes e marcadores; marcar ambiguidade e rejeitar segmentos não confirmados. |
| M3 | Observador físico | Medir movimento localizado/global em duas grades, cadência **apenas nas janelas observadas**, cobertura, estabilidade e incerteza. Eventos são **candidatos**, não bolas confirmadas. |
| M4 | Memória de observação | Validar e registrar checkpoints independentes; incluir negativos e falhas; rejeitar vazamento de resultado, divergência de versão, fonte, fingerprint e dados futuros. |
| M5 | Síntese longitudinal V2 | Acumular estados observacionais e quantitativos por concurso; registrar SHA de cada origem, snapshots imutáveis, taxa de disponibilidade, cobertura e corte temporal. **Sem inferência preditiva**. |
| M6 | Revisão de hipóteses GPT-6 | Outra IA lê `LATEST.json` + snapshot SHA, compara padrões, detecta erros e propõe testes falsificáveis; GPT-6 não recebe autoridade de mudar pesos nem fabricar observações. |
| M7 | Teste temporal e controles | Comparar dados por ordem de concurso; separar treino/holdout quando houver amostras suficientes; incluir controle de movimento global, corte de câmera, vídeo duplicado e degradação de observabilidade. |
| M8 | Consumidor e governança | Entregar JSON com schema estável, status, limitações e provas; impedir promoção ao preditor sem ensaio prospectivo independente e gate específico de liberação. |

**Fases são etapas de construção**, não nomes de módulos do produto. Não alterar a taxonomia modular para confundir M1/M2 com F1/F2.

## Novo armazenamento consumível

### Origem no PC Escola

`C:\SMART-MEGA\runtime\video_observation\contest_<N>.json`

Os arquivos de origem **não** são regravados pela V2. O V1 pode continuar gerando `SMART_VISUAL_LEARNING_STATE.json` no mesmo diretório.

### Memória consolidada V2 no mesmo host

`C:\SMART-MEGA\runtime\video_learning_v2\LATEST.json`  
`C:\SMART-MEGA\runtime\video_learning_v2\snapshots\<SHA256>.json`

- `LATEST.json`: ponteiro para snapshot, hash e concurso-alvo.
- `snapshots/<sha>.json`: síntese do que foi **realmente consumido**, hashes de origem, resultados observacionais, rejeições e razões, e corte temporal de treino/holdout.
- O snapshot é **imutável**; a mudança de dados cria outro snapshot, sem sobrescrever o anterior.
- Não representa um tensor de pesos de rede neural, checkpoint de treinamento LLM ou modelo preditivo treinado.
- Os dois diretórios são **caminhos planejados e suportados pelo código**, não atestação de existência física atual no B2.

### Chamada reproduzível

A partir de `C:\SMART-MEGA` e com o Python ambiente do projeto:

```powershell
.venv\Scripts\python.exe -m research.visual_learning_v2 --checkpoint-dir runtime/video_observation --store runtime/video_learning_v2 --next-contest N
```

Substituir `N` pelo próximo concurso conhecido sem usar seus resultados. O script não baixa vídeo nem lê planilha de dezenas.

**Contrato de consumo por outra IA:** ler `LATEST.json`, abrir a referência relativa `snapshot_file`, conferir SHA-256, conferir `next_contest`, `eligible_observations`, `status_counts`, `rejected_counts`, `training_contests`, `holdout_contests`, `learning_status`, `predictive_weight_authorized=false`. Sem o snapshot íntegro, declarar `NO_VERIFIED_INPUT` / bloquear qualquer afirmação de aprendizado alimentado por dados reais.

## Critérios de aprendizado de verdade

**A. Aprendizado de método:** defeitos como corte de câmera, deslocamento de cenário ou latência viram hipóteses de correção; corrigir em código; testar e comparar a versão anterior; preservar versões e rollback.

**B. Aprendizado estatístico de observabilidade:** manter exemplos negativos, disponibilidade de observações e cobertura; separar coeficientes de **disponibilidade técnica** de qualquer noção de acerto preditivo. O campo `technical_availability_posterior_mean` só aparece com dez ou mais observações verificadas; não é peso para dezenas.

**C. Aprendizado de padrões físicos:** requer semântica/rotulagem adequada, provas de origem física, replicação e validação em vídeos diferentes. Padrões de pixel isolados não são prova de giro de bola ou irregularidade do globo.

**D. Aprendizado preditivo:** exige dados disponíveis **antes** da decisão da aposta, baseline uniforme, congelamento de decisões, repetição prospectiva, métricas de calibração e vantagem reprodutível em dados não usados no ajuste. Os vídeos publicados **depois** do sorteio não podem retroagir como sinal da própria aposta.

## Estágio atual de execução

- M4/M5 possuem **primeira implementação funcional isolada** em `research/visual_learning_v2.py`, com testes em `tests/test_smart_visual_learning_v2.py`.
- A primeira bateria unitária com entradas sintéticas fechou **12/12 PASS**.
- Isso prova parser, validações temporais, bloqueio de vazamento, snapshots e idempotência; **não** prova vídeo real, funcionamento do B2 ou eficácia preditiva.
- M1/M2/M3 permanecem no observador 1.3.1; a V2 não os substitui automaticamente.
- M6 é um contrato para consumo por GPT-6, **não** um agente GPT-6 persistente já conectado.
- A V2 deve permanecer isolada em branch de revisão até reconciliação com B2, CI completa e validação operacional.

## Próximas fases de execução, fora do produto

**F1 — Reconciliação física:** inventariar os 13 registros B2 **sem presumir caminho ou quantidade**, calcular SHA-256, versões, duplicações, fontes e classificações. Material sem fingerprint compatível vai para quarentena lógica, não é descartado nem migra silenciosamente.

**F2 — Testar o V2 no B2:** executar `--next-contest` para um alvo futuro, mostrar `LATEST.json` e um snapshot com hashes checados e contagens reais. Reexecutar e provar idempotência.

**F3 — Auditoria de aprendizagem:** comparar quantitativamente V1×V2 em todos os 13 concursos: quantos entraram, quantos foram recusados, por qual razão; conferir que negativos e falhas contam como qualidade observacional, não como semântica positiva.

**F4 — Rotulagem e estabilidade:** criar pequeno conjunto adjudicado de eventos verdadeiros/artefatos de câmera, sem dezenas vencedoras no recurso de aprendizagem; medir precisão, recall, cobertura, discordância entre grades e sensibilidade ao contexto de vídeo. Não usar resultados futuros.

**F5 — Revisão e atualização:** usar GPT-6 como analista de falhas e propostas; mudanças só entram após testes novos, não regressão e revisão do registro dos sinais. Regra de versão: os snapshots jamais são adulterados.

**F6 — Consumidor externo:** segunda IA consome por contrato somente `LATEST.json` e o snapshot verificado e reproduz exatamente amostras, conclusões e limitações. Uma resposta divergente ou sem hash não passa no gate.

**F7 — CI e segurança:** CI completa, segurança do parser, testes de concorrência, persistência/recuperação, autorização somente read-only no preditor, sem mídia armazenada.

**F8 — Gate 6/6 e publicação:** avaliar captação, interpretação, pesos científicos corretos, adaptação, aprendizado robusto e resultado comprovado. **Nenhum 6/6** pode ser alegado só por sucesso de engenharia ou 12 testes sintéticos.

## Prova 6/6 exigida

1. **Captação:** arquivos oficiais reais verificados, cobertura e digest; sem vídeo, `NO_VERIFIED_INPUT`.
2. **Interpretação:** rastreamento/rotulagem auditável com negativos reais; sem confundir câmera com fenômeno físico.
3. **Peso:** coeficientes de observabilidade distintos de pesos preditivos; estes ficam bloqueados sem validação prospectiva.
4. **Adaptação:** comparar configurações V1/V2 em corte temporal e holdout; corrigir erros sem vazar dados.
5. **Robustez:** persistência imutável e reprodutível, testes de regressão, segurança e não regressão.
6. **Resultado comprovado:** evidência científica prospectiva independente para qualquer alegação de vantagem em previsão. Sem isso `MISSION_ACTIVE`, não `MISSION_PROVEN`.

## Instrução curta para outra IA

> No `andrebarros78/SMART-MEGA`, estudar a branch `learning/visual-learning-v2-gpt6-20261010`. O observador legado está em `smart_video_observation.py`; o consumidor V2 está em `research/visual_learning_v2.py`. No PC Escola os checkpoints devem estar em `C:\SMART-MEGA\runtime\video_observation`. A memória V2 consumível deve estar em `C:\SMART-MEGA\runtime\video_learning_v2\LATEST.json` e snapshots referenciados. **Só afirmar aprendizagem real consumida ao verificar SHA e quantidade dos checkpoints.** Nunca alegar vantagem preditiva nem que GPT-6 corre em background.
