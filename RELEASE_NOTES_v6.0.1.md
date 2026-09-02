# SMART-MEGA v6.0.1

Data: 2026-09-01

## CorreÃ§Ã£o

- Meta-governador passa a operar fail-closed: `quality_dynamic` Ã© a Ã¢ncora padrÃ£o; outras polÃ­ticas permanecem em shadow atÃ© autorizaÃ§Ã£o prospectiva explÃ­cita.
- Defeito corrigido: o meta-governador anterior produzia 1.260 acertos no replay causal 1001â€“3051 contra 1.272 da polÃ­tica Ã¢ncora, regressÃ£o de 12 acertos e de 27 para 25 eventos 3+.
- ApÃ³s a correÃ§Ã£o: 1.272 acertos, 27 eventos 3+, 1 evento 4+, sem regressÃ£o contra a Ã¢ncora.

## HipÃ³teses rejeitadas

- ReduÃ§Ã£o arbitrÃ¡ria do teto individual de 42% para 35/30/25/20/15%: rejeitada por piorar o resultado causal global.
- Uso direto da utilidade marginal no peso: candidatos testados nÃ£o satisfizeram a regra de promoÃ§Ã£o e foram rejeitados.

## ValidaÃ§Ã£o

- 321/321 testes PASS.
- Red Team: 10/10 cenÃ¡rios PASS.
- Integridade global: PASS.
- 3052 adjudicado causalmente: Champion 1/6, Challenger 1/6, vantagem 0, e-value 1,0, KEEP_CHAMPION.
- Freeze original do 3052 preservado sem reescrita retrospectiva.

## Limite cientÃ­fico

Esta versÃ£o prova a correÃ§Ã£o de arquitetura/governanÃ§a e nÃ£o prova vantagem preditiva da Mega-Sena.
