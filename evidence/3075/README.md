# SMART Mega V6 — concurso 3075: comprovante de geração

**Cartão:** `10 – 11 – 27 – 38 – 43 – 53`  
**Status do leitor independente:** `FROZEN_MODEL_CARD_VERIFIED` (`EXIT=0`)  
**Resultado do processo integral e do consumidor:** `PASS` / `PASS`  
**Histórico utilizado:** até o concurso **3074**, SHA-256 `c87bde2b81af2a4c24800236b323711e7a96184ea7122b8cd958e7b78985caa6`  
**Geração UTC:** 2026-10-26T08:51:01.914116+00:00  
**Código GitHub executado:** `4223265a9b9b6d342a0e9c5e9615880ddbb5db21`  
**Epoch:** `operator-3075-ebc8e8bdb7a0-20261026T084409851147Z`

## Evidências

- `SMART_3075_PRIMARY_CARD.json` — cartão primário efetivamente produzido, SHA-256 `b17a0dfc86736336c7f0ed3ec3f24c4dd4240b4d7291e554950e757ce3631608`
- `FULL_PROCESS_PROOF.json` — prova da cadeia completa, SHA-256 `2049e5d98e49ec29c5ac262f12d813c7282d8797c42df9e423dc72e20da9676f`
- `SMART_3075_CHAMPION_CHALLENGER_FREEZE.json` — congelamento do modelo, SHA-256 `f5609dd6c1210c5dd6f0fd971ee44496e869db708001d687885c63caeff59d11`
- `SMART_3075_CHAMPION_CHALLENGER_FREEZE_PORTFOLIO.json` — composição do portfólio, SHA-256 `233f5dac59039cb303005b485bdd53782533e80aa32b26c9200f9aab555dd2ae`
- `SMART_3075_GITHUB_EXECUTION_RECEIPT.json` — verificação independente, hashes e contexto da execução.

Os bytes de cada um dos quatro artefatos da execução foram comparados ao SHA dos blobs Git criados remotamente, com igualdade completa.

## Limites e proveniência

Execução real pelo comando `smart_operator.py generate-card --target 3075` em executor Windows governado que utiliza o checkout do commit acima obtido do GitHub. **Não ocorreu execução de GitHub Actions.** Os dados operacionais foram mantidos no executor, e a evidência é publicada aqui em branch separada. **A branch `main` não foi modificada.**

O resultado do concurso 3075 não foi usado para gerar o cartão. O modelo campeão foi mantido: a alternativa perdeu dois acertos no holdout em relação à referência. A PR #80, ainda não incorporada ao commit da execução, adiciona um filtro estatístico de promoção, não uma troca forçada de dezenas.

**As seis dezenas são idênticas às dos concursos anteriores.** Isto não prova qualidade preditiva, e nenhuma superioridade prospectiva foi certificada. Nenhuma aposta foi realizada pelo pipeline.
