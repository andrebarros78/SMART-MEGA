# SMART-MEGA V6 — ECC Full, calibração em shadow (15/10/2026)

**Fonte:** commit `fc13475442f4c1e059eb7ba583fa6bd4ed84a746`, branch isolada `ecc/finetuning-shadow-20261015`. **Produção main não alterada.** A missão ECC durável está em `smartmega-v6-ecc-finetune-20261015`.

## Defeito reproduzido e ajuste candidato
`freeze_next_research.py` projetava o peso por especialista antes da penalização por redundância, mas normalizava novamente depois, permitindo ultrapassar o teto efetivo de 60%. Teste adversarial: 90,91% antes / 60,00% depois. Três testes com `smart_v2_engine.py` real no PC Casa passaram.

## Comparação histórica prequential (sem informação futura)
Planilha fornecida: SHA-256 `7c8fe0c2f06ebf07118809758454169a755a9e91885cb47624387eeb236e9d81`, concursos 1–3070. O replay reproduziu, na baseline, o Top-6 e os pesos `freq1000` do freeze real 3071.

| Período | Baseline | Teto corrigido | Diferença |
|---|---:|---:|---:|
| 1001–3070 (2.070 concursos) | 1.274 | 1.268 | −6 |
| Calibração 1500–2499 | 607 | 597 | −10 |
| Validação 2500–2850 | 244 | 244 | 0 |
| Holdout retrospectivo 2851–3070 | 128 | 131 | +3 |

716 concursos tinham ultrapassagem do limite na baseline; 0 no candidato. O candidato mudou 151 cartões históricos, mas o conjunto de seis dezenas para 3071 permaneceu idêntico. O resultado **não** autoriza promoção: regressão global e ganho sem validação prospectiva.

## Seletor e duques
Em 220 concursos (2851–3070), benchmark exploratório sem o módulo de resgate: Top-6 simples 128 acertos; seletor com restrições 130; forçar dois números do sorteio anterior 137. Ambos intervalos bootstrap 95% de ganho médio contêm zero. Esperança uniforme: 132 acertos. Resultados não provam vantagem preditiva, e nada foi integrado ao cartão.

## Integridade de aprendizado
Os relatórios assinados 3060, 3061, 3062 e 3068 referenciam snapshots de ledger imutável não presentes no catálogo `SMART_STATE_ARCHIVE/hash-bound-learning` inspecionado. Manter quarentena; não inventar hashes, não aprovar pesos de resgate com fonte parcial.

## Limite operacional
O checkout local `C:\New Projet\SMART-MEGA-V6-E2E` possui HEAD inválido, e Git CLI no PC Casa não conseguiu consultar o repositório privado. Regressão **integral atual não executada** nesta missão. O teste específico passou; o registro de regressão anterior não substitui nova regressão. Necessária execução completa em checkout canônico válido antes de qualquer merge ou promoção.

**Decisão: NO_PROMOTION, MISSION_ACTIVE.** Preservar baseline e monitorar evidência prospectiva.
